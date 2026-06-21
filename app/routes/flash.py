"""
Routes Missions Flash
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.flash_service import get_active_missions, get_user_completions, submit_mission, approve_completion
from app.services.commission_service import get_wallet

router = APIRouter(prefix="/missions", tags=["Flash"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_missions(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    missions = await get_active_missions(db)
    completions = await get_user_completions(db, user["id"])
    wallet = await get_wallet(db, user["id"])
    completed_ids = {c["mission_id"]: c["status"] for c in completions}
    return templates.TemplateResponse("flash_missions.html", {
        "request": request,
        "user": user,
        "missions": missions,
        "completed_ids": completed_ids,
        "wallet": wallet,
    })

@router.post("/submit")
async def submit(request: Request, mission_id: Annotated[str, Form()], proof_url: Annotated[str, Form()] = ""):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    result = await submit_mission(db, user["id"], mission_id, proof_url or None)
    return JSONResponse(result)

@router.post("/admin/approve")
async def admin_approve(request: Request, completion_id: Annotated[str, Form()]):
    user = await _get_user(request)
    if not user or user.get("role") != "admin": return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    result = await approve_completion(db, completion_id)
    return JSONResponse(result)

@router.post("/admin/reject")
async def admin_reject(request: Request, completion_id: Annotated[str, Form()]):
    user = await _get_user(request)
    if not user or user.get("role") != "admin": return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("flash_completions").update({"status": "rejected"}).eq("id", completion_id).execute()
    return JSONResponse({"success": True})
