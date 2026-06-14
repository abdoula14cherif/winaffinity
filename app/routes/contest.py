"""
Route Grand Concours WIN AFFINITY
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.contest_service import get_contest_progress, claim_reward

router = APIRouter(prefix="/contest", tags=["Contest"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_contest(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    progress = await get_contest_progress(db, user["id"])
    return templates.TemplateResponse("contest.html", {
        "request": request,
        "user": user,
        "progress": progress,
    })

@router.post("/claim")
async def post_claim(request: Request, tier: Annotated[int, Form()]):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    result = await claim_reward(db, user["id"], tier)
    return JSONResponse(result)
