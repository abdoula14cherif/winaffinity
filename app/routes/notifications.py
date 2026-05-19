"""
Routes notifications
GET  /notifications       → Page notifications
POST /notifications/read  → Marquer tout lu
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.notification_service import get_notifications, mark_all_read, get_unread_count

router = APIRouter(prefix="/notifications", tags=["Notifications"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_notifs(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    db = get_supabase()
    notifs = await get_notifications(db, user["id"])
    await mark_all_read(db, user["id"])
    return templates.TemplateResponse("notifications.html", {
        "request": request,
        "user": user,
        "notifications": notifs,
    })

@router.get("/count")
async def notif_count(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"count": 0})
    count = await get_unread_count(get_supabase(), user["id"])
    return JSONResponse({"count": count})
