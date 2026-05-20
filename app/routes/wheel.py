"""
Routes roue de la chance
GET  /wheel      → Page roue
POST /wheel/spin → Tourner la roue
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.wheel_service import can_spin, do_spin, get_spin_history, SEGMENTS

router = APIRouter(prefix="/wheel", tags=["Wheel"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_wheel(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    can = await can_spin(db, user["id"])
    history = await get_spin_history(db, user["id"])
    segments_data = [{"label": s[2], "color": s[3], "amount": s[0]} for s in SEGMENTS]
    return templates.TemplateResponse("wheel.html", {
        "request": request,
        "user": user,
        "can_spin": can,
        "history": history,
        "segments": segments_data,
    })

@router.post("/spin")
async def spin(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    try:
        result = await do_spin(db, user["id"])
        return JSONResponse({"success": True, **result})
    except ValueError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)
