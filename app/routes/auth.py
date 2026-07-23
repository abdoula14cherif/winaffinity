"""
win_affinity/app/routes/auth.py
────────────────────────────────
Endpoints HTTP pour l'inscription et la connexion.
Protection : rate limiting, CSRF, validation Pydantic, cookies HTTP-only.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import get_supabase
from app.models.user import RegisterRequest, LoginRequest
from app.security import (
    create_access_token,
    create_refresh_token,
    verify_csrf_token,
    generate_csrf_token,
    sanitize_input,
)
from app.services.auth_service import register_user, authenticate_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  PAGE D'INSCRIPTION
# ─────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse, name="register_page")
async def get_register(
    request: Request,
    ref: str | None = None,  # Code de parrainage depuis l'URL
):
    """
    Affiche la page d'inscription.
    Le code de parrainage (ref=XXX) est capturé depuis l'URL et injecté dans le formulaire.
    """
    # Génération d'un token CSRF pour protéger le formulaire
    session_id = request.cookies.get("session_id", secrets_token())
    csrf_token = generate_csrf_token(session_id)

    response = templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "referral_code": sanitize_input(ref or "", max_length=20),
            "csrf_token": csrf_token,
            "error": None,
        },
    )
    # Pose le cookie de session si absent
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


@router.post("/register", name="register_submit")
async def post_register(
    request: Request,
    full_name: Annotated[str, Form()],
    phone: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_confirm: Annotated[str, Form()],
    referral_code: Annotated[str | None, Form()] = None,
    csrf_token: Annotated[str | None, Form()] = None,
):
    """
    Traite le formulaire d'inscription.
    En cas de succès → redirige vers /auth/login.
    En cas d'erreur → réaffiche le formulaire avec le message.
    """
    db = get_supabase()
    session_id = request.cookies.get("session_id", "")

    # ── Vérification CSRF ──────────────────────────────────────────
    if not csrf_token or not verify_csrf_token(csrf_token, session_id):
        logger.warning("[AUTH] Token CSRF invalide depuis %s", request.client.host)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "referral_code": referral_code or "",
                "csrf_token": generate_csrf_token(session_id),
                "error": "Requête invalide. Veuillez réessayer.",
            },
            status_code=400,
        )

    # ── Validation Pydantic ────────────────────────────────────────
    try:
        data = RegisterRequest(
            full_name=full_name,
            phone=phone,
            email=email,
            password=password,
            password_confirm=password_confirm,
            referral_code=referral_code,
        )
    except Exception as e:
        # Extrait le premier message d'erreur lisible
        error_msg = _extract_validation_error(e)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "referral_code": referral_code or "",
                "csrf_token": generate_csrf_token(session_id),
                "error": error_msg,
            },
            status_code=422,
        )

    # ── Appel du service d'inscription ────────────────────────────
    try:
        await register_user(db, data)
    except ValueError as e:
        # Erreur métier (email existant, parrainage invalide, etc.)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "referral_code": referral_code or "",
                "csrf_token": generate_csrf_token(session_id),
                "error": str(e),
            },
            status_code=400,
        )
    except RuntimeError as e:
        # Erreur technique (DB, etc.)
        logger.error("[AUTH] Erreur inscription : %s", e)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "referral_code": referral_code or "",
                "csrf_token": generate_csrf_token(session_id),
                "error": "Une erreur technique est survenue. Veuillez réessayer.",
            },
            status_code=500,
        )

    # ── Succès → redirection vers login ────────────────────────────
    logger.info("[AUTH] Inscription réussie pour : %s", email)
    return RedirectResponse(
        url="/auth/login?registered=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ─────────────────────────────────────────────
#  PAGE DE CONNEXION
# ─────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse, name="login_page")
async def get_login(
    request: Request,
    registered: int | None = None,  # ?registered=1 après inscription réussie
):
    """Affiche la page de connexion."""
    session_id = request.cookies.get("session_id", secrets_token())
    csrf_token = generate_csrf_token(session_id)

    response = templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "success": "Compte créé avec succès ! Connectez-vous." if registered else None,
            "error": None,
        },
    )
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    return response


async def _check_login_attempts(db, email: str, ip: str) -> dict:
    """Vérifie si l'email ou l'IP n'est pas bloqué."""
    from datetime import datetime, timezone, timedelta
    window = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    # Vérifier tentatives par email
    by_email = db.table("login_attempts").select("id").eq("email", email).eq("success", False).gte("created_at", window).execute().data or []
    if len(by_email) >= 5:
        return {"blocked": True, "reason": "Trop de tentatives échouées. Réessayez dans 15 minutes."}
    # Vérifier tentatives par IP
    by_ip = db.table("login_attempts").select("id").eq("ip", ip).eq("success", False).gte("created_at", window).execute().data or []
    if len(by_ip) >= 10:
        return {"blocked": True, "reason": "Trop de tentatives depuis votre réseau. Réessayez dans 15 minutes."}
    return {"blocked": False}

async def _log_attempt(db, email: str, ip: str, success: bool):
    """Enregistre une tentative de connexion."""
    try:
        db.table("login_attempts").insert({"email": email, "ip": ip, "success": success}).execute()
    except Exception:
        pass

@router.post("/login", name="login_submit")
async def post_login(
    request: Request,
    response: Response,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str | None, Form()] = None,
):
    """
    Traite le formulaire de connexion.
    En cas de succès → pose les cookies JWT et redirige vers /payment.
    """
    db = get_supabase()
    session_id = request.cookies.get("session_id", "")

    # ── Vérification CSRF ──────────────────────────────────────────
    if not csrf_token or not verify_csrf_token(csrf_token, session_id):
        logger.warning("[AUTH] Token CSRF invalide (login) depuis %s", request.client.host)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "csrf_token": generate_csrf_token(session_id),
                "error": "Requête invalide. Veuillez réessayer.",
                "success": None,
            },
            status_code=400,
        )

    # ── Validation Pydantic ────────────────────────────────────────
    try:
        data = LoginRequest(email=email, password=password)
    except Exception as e:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "csrf_token": generate_csrf_token(session_id),
                "error": _extract_validation_error(e),
                "success": None,
            },
            status_code=422,
        )

    # ── Vérification tentatives ───────────────────────────────────
    ip = request.client.host or "unknown"
    check = await _check_login_attempts(db, email, ip)
    if check["blocked"]:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "csrf_token": generate_csrf_token(session_id),
            "error": check["reason"],
            "success": None,
        }, status_code=429)

    # ── Authentification ───────────────────────────────────────────
    user = await authenticate_user(db, data)

    if not user:
        await _log_attempt(db, email, ip, False)
        # Message générique intentionnel (ne révèle pas si l'email existe)
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "csrf_token": generate_csrf_token(session_id),
                "error": "Identifiants incorrects.",
                "success": None,
            },
            status_code=401,
        )

    # ── Génération des tokens JWT ──────────────────────────────────
    access_token = create_access_token(user["id"], user["email"])
    refresh_token = create_refresh_token(user["id"])

    # Redirection selon l'état du compte
    redirect_url = "/payment" if not user.get("is_active") else "/dashboard"

    redirect_response = RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )

    # Cookies HTTP-only (inaccessibles au JavaScript → protection XSS)
    cookie_opts = dict(
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        domain=".winaffinity.vip",
    )
    redirect_response.set_cookie("access_token", access_token, max_age=3600, **cookie_opts)
    redirect_response.set_cookie("refresh_token", refresh_token, max_age=604800, **cookie_opts)

    return redirect_response


# ── Déconnexion ───────────────────────────────────────────────────────────────

@router.get("/logout", name="logout")
async def logout():
    """Supprime les cookies de session et redirige vers login."""
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("session_id")
    return response


# ── Helpers internes ──────────────────────────────────────────────────────────

def secrets_token() -> str:
    """Génère un identifiant de session sécurisé."""
    import secrets
    return secrets.token_urlsafe(32)


def _extract_validation_error(exc: Exception) -> str:
    """Extrait un message d'erreur lisible depuis une exception Pydantic."""
    try:
        errors = exc.errors()
        if errors:
            return errors[0].get("msg", "Données invalides.")
        return str(exc)
    except Exception:
        return "Données invalides."
