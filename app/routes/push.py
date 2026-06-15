"""
Routes pour notifications push
"""
import os
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.push_service import save_subscription

router = APIRouter(prefix="/push", tags=["Push"])
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("/vapid-key")
async def get_vapid_key():
    return JSONResponse({"key": os.environ.get("VAPID_PUBLIC_KEY", "")})

@router.post("/subscribe")
async def subscribe(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    body = await request.json()
    ok = await save_subscription(db, user["id"], body)
    return JSONResponse({"success": ok})
