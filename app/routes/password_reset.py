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
        reset_url = f"https://www.winaffinity.vip/auth/reset-password?token={token}"
        try:
            from app.services.email_service import send_reset_password_email
            await send_reset_password_email(user["email"], user["full_name"], reset_url)
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
