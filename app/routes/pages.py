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
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
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
                }
            )
        return JSONResponse({"status": r.status_code, "data": r.json()})
    except Exception as e:
        return JSONResponse({"error": str(e), "type": type(e).__name__}, status_code=500)

@router.get("/recharge", response_class=HTMLResponse)
async def get_recharge(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    recharges = db.table("recharges").select("*").eq("user_id", user["id"]).order("created_at", desc=True).limit(10).execute().data or []
    cashback_total = sum(r.get("cashback", 0) for r in recharges if r.get("status") == "success")
    return templates.TemplateResponse("recharge.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "recharges": recharges,
        "cashback_total": cashback_total
    })

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

@router.get("/test-email")
async def test_email(request: Request):
    import os, httpx
    key = os.environ.get("BREVO_API_KEY", "")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": key, "Content-Type": "application/json"},
                json={
                    "sender": {"name": "WIN AFFINITY", "email": "winaffinitysupport@gmail.com"},
                    "to": [{"email": "abdoula13cherif@gmail.com", "name": "Test"}],
                    "subject": "Test Brevo",
                    "htmlContent": "<h1>Test OK</h1>"
                },
                timeout=10
            )
        return JSONResponse({"status": r.status_code, "response": r.text})
    except Exception as e:
        return JSONResponse({"error": str(e)})

@router.get("/legal", response_class=HTMLResponse)
async def get_legal(request: Request):
    user = await _get_user(request)
    return templates.TemplateResponse("legal.html", {"request": request, "user": user})

@router.get("/contact", response_class=HTMLResponse)
async def get_contact(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse("contact.html", {"request": request, "user": user})
