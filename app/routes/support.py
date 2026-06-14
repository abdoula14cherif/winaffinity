"""
Routes chat support
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.support_service import get_messages, send_message, mark_read

router = APIRouter(prefix="/support", tags=["Support"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_support(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    db = get_supabase()
    messages = await get_messages(db, user["id"])
    await mark_read(db, user["id"], "admin")
    return templates.TemplateResponse("support.html", {
        "request": request,
        "user": user,
        "messages": messages,
    })

@router.post("/send")
async def post_message(request: Request, message: Annotated[str, Form()]):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    ok = await send_message(db, user["id"], "user", message)
    return JSONResponse({"success": ok})

@router.get("/messages")
async def get_new_messages(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"messages": []})
    db = get_supabase()
    messages = await get_messages(db, user["id"])
    return JSONResponse({"messages": messages})
