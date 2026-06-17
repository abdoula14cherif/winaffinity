"""
Routes réinitialisation mot de passe
"""
import httpx
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.services.password_reset_service import create_reset_token, verify_reset_token, reset_password

router = APIRouter(prefix="/auth", tags=["PasswordReset"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

@router.get("/forgot-password", response_class=HTMLResponse)
async def get_forgot(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@router.post("/forgot-password")
async def post_forgot(request: Request, email: Annotated[str, Form()]):
    db = get_supabase()
    result = await create_reset_token(db, email)
    if result.get("token") and result.get("user"):
        user = result["user"]
        token = result["token"]
        reset_url = f"https://winaffinity.vercel.app/auth/reset-password?token={token}"
        try:
            httpx.post("https://api.emailjs.com/api/v1.0/email/send", json={
                "service_id": "service_ps61bla",
                "template_id": "template_aks186b",
                "user_id": "fNyhiux6zn4u2CtRj",
                "template_params": {
                    "to_email": user["email"],
                    "to_name": user["full_name"],
                    "subject": "Réinitialisation de votre mot de passe WIN AFFINITY",
                    "message": f"Bonjour {user['full_name']},\n\nVous avez demandé à réinitialiser votre mot de passe.\n\nCliquez sur ce lien (valable 1 heure) :\n{reset_url}\n\nSi vous n'avez pas fait cette demande, ignorez cet email.\n\nL'équipe WIN AFFINITY"
                }
            }, timeout=5)
        except Exception as e:
            logger.error("[RESET] Email error: %s", e)
    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "success": "Si cet email existe, un lien de réinitialisation a été envoyé."
    })

@router.get("/reset-password", response_class=HTMLResponse)
async def get_reset(request: Request, token: str = ""):
    db = get_supabase()
    verify = await verify_reset_token(db, token)
    if not verify["valid"]:
        return templates.TemplateResponse("forgot_password.html", {
            "request": request,
            "error": "Lien invalide ou expiré. Faites une nouvelle demande."
        })
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

@router.post("/reset-password")
async def post_reset(request: Request, token: Annotated[str, Form()], new_password: Annotated[str, Form()], confirm_password: Annotated[str, Form()]):
    if new_password != confirm_password:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "error": "Les mots de passe ne correspondent pas."
        })
    if len(new_password) < 6:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "error": "Le mot de passe doit contenir au moins 6 caractères."
        })
    db = get_supabase()
    result = await reset_password(db, token, new_password)
    if result["success"]:
        return RedirectResponse("/auth/login?reset=1", status_code=302)
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token,
        "error": result.get("error", "Erreur lors de la réinitialisation.")
    })
