"""
Routes formations et groupes
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id

router = APIRouter(tags=["Learning"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("/formations", response_class=HTMLResponse)
async def get_formations(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    try:
        formations = db.table("formations").select("*").eq("is_active", True).order("created_at").execute().data or []
    except:
        formations = []
    return templates.TemplateResponse("formations.html", {"request": request, "user": user, "formations": formations})

@router.get("/groupes", response_class=HTMLResponse)
async def get_groupes(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    try:
        groups = db.table("groups").select("*").eq("is_active", True).order("created_at").execute().data or []
    except:
        groups = []
    return templates.TemplateResponse("groupes.html", {"request": request, "user": user, "groups": groups})
