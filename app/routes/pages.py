"""
Routes pages statiques : profil, faq, support, contact
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
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
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    referrals = db.table("users").select("id").eq("sponsor_id", user["id"]).eq("is_active", True).execute().data or []
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "wallet": wallet, "referrals_count": len(referrals)})

@router.get("/faq", response_class=HTMLResponse)
async def get_faq(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse("faq.html", {"request": request, "user": user})


@router.post("/winbot/chat")
async def winbot_chat(request: Request):
    import os
    import httpx
    body = await request.json()
    messages = body.get("messages", [])
    system = body.get("system", "")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return JSONResponse({"error": "Clé API manquante"}, status_code=500)
    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "system": system,
                "messages": messages
            },
            timeout=30
        )
        return JSONResponse({"status": r.status_code, "data": r.json()})
    except Exception as e:
        return JSONResponse({"error": str(e), "type": type(e).__name__}, status_code=500)

@router.get("/winbot", response_class=HTMLResponse)
async def get_winbot(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    referrals = db.table("users").select("id").eq("sponsor_id", user["id"]).eq("is_active", True).execute().data or []
    return templates.TemplateResponse("winbot.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "referrals_count": len(referrals)
    })

@router.get("/share", response_class=HTMLResponse)
async def get_share(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    referrals = db.table("users").select("id").eq("sponsor_id", user["id"]).eq("is_active", True).execute().data or []
    return templates.TemplateResponse("share.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "referrals_count": len(referrals)
    })

@router.get("/legal", response_class=HTMLResponse)
async def get_legal(request: Request):
    user = await _get_user(request)
    return templates.TemplateResponse("legal.html", {"request": request, "user": user})

@router.get("/contact", response_class=HTMLResponse)
async def get_contact(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse("contact.html", {"request": request, "user": user})
