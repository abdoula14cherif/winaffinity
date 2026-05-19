"""
Routes pages statiques : profil, faq, support, contact
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.commission_service import get_wallet

router = APIRouter(tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("/profile", response_class=HTMLResponse)
async def get_profile(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    wallet = await get_wallet(get_supabase(), user["id"])
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "wallet": wallet})

@router.get("/faq", response_class=HTMLResponse)
async def get_faq(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse("faq.html", {"request": request, "user": user})

@router.get("/support", response_class=HTMLResponse)
async def get_support(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse("support.html", {"request": request, "user": user})

@router.get("/contact", response_class=HTMLResponse)
async def get_contact(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse("contact.html", {"request": request, "user": user})
