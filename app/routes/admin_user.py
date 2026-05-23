"""
Admin - Page détail utilisateur
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id

router = APIRouter(prefix="/admin/user", tags=["Admin User"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_admin(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    user = await get_user_by_id(get_supabase(), payload["sub"])
    if not user or user.get("role") != "admin": return None
    return user

@router.get("/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: str):
    admin = await _get_admin(request)
    if not admin: return RedirectResponse("/auth/login", status_code=302)
    db = get_supabase()
    try:
        user = db.table("users").select("*").eq("id", user_id).execute().data
        if not user: return RedirectResponse("/admin", status_code=302)
        user = user[0]
        wallet = db.table("wallets").select("*").eq("user_id", user_id).execute().data
        wallet = wallet[0] if wallet else {"balance": 0, "total_earned": 0}
        referrals = db.table("users").select("id,full_name,email,is_active,created_at,referral_count").eq("sponsor_id", user_id).execute().data or []
        commissions = db.table("commissions").select("*").eq("beneficiary_id", user_id).order("created_at", desc=True).limit(20).execute().data or []
        withdrawals = db.table("withdrawals").select("*").eq("user_id", user_id).order("created_at", desc=True).execute().data or []
        payments = db.table("payments").select("*").eq("user_id", user_id).execute().data or []
        sponsor = None
        if user.get("sponsor_id"):
            s = db.table("users").select("id,full_name,email,referral_code").eq("id", user["sponsor_id"]).execute().data
            if s: sponsor = s[0]
    except Exception as e:
        logger.error("[ADMIN] Erreur detail user : %s", e)
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("admin_user.html", {
        "request": request,
        "target": user,
        "wallet": wallet,
        "referrals": referrals,
        "commissions": commissions,
        "withdrawals": withdrawals,
        "payments": payments,
        "sponsor": sponsor,
    })

@router.post("/{user_id}/update")
async def update_user_detail(
    request: Request, user_id: str,
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    phone: Annotated[str, Form()],
    role: Annotated[str, Form()],
    is_active: Annotated[str, Form()],
    balance: Annotated[int, Form()],
):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        db.table("users").update({
            "full_name": full_name,
            "email": email.lower(),
            "phone": phone,
            "role": role,
            "is_active": is_active == "true"
        }).eq("id", user_id).execute()
        wallet = db.table("wallets").select("id").eq("user_id", user_id).execute().data
        if wallet:
            db.table("wallets").update({"balance": balance}).eq("user_id", user_id).execute()
        else:
            db.table("wallets").insert({"user_id": user_id, "balance": balance, "total_earned": balance}).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
