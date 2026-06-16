"""
Routes gains et tâches
GET  /gains           → Page gains (HTML)
POST /gains/complete  → Compléter une tâche
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.commission_service import get_wallet
from app.services.task_service import get_tasks_with_status, complete_task

router = APIRouter(prefix="/gains", tags=["Gains"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_gains(request: Request):
    user = await _get_user(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"):
        return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    tasks = await get_tasks_with_status(db, user["id"])
    return templates.TemplateResponse("gains.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "tasks": tasks,
    })

@router.post("/complete")
async def post_complete_task(request: Request, task_id: Annotated[str, Form()]):
    user = await _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Non authentifié."}, status_code=401)
    db = get_supabase()
    try:
        result = await complete_task(db, user["id"], task_id)
        return JSONResponse({"success": True, "reward": result["reward"]})
    except ValueError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)

@router.get("/ad/count")
async def get_ad_count(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"count": 0})
    db = get_supabase()
    from datetime import date
    today = str(date.today())
    try:
        res = db.table("ad_views").select("id").eq("user_id", user["id"]).eq("viewed_at", today).execute()
        return JSONResponse({"count": len(res.data or [])})
    except:
        return JSONResponse({"count": 0})

@router.post("/ad/view")
async def view_ad(request: Request):
    user = await _get_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Non authentifie"}, status_code=401)
    db = get_supabase()
    from datetime import date
    today = str(date.today())
    try:
        # Verifier limite 10 vues/jour
        views_today = db.table("ad_views").select("id").eq("user_id", user["id"]).eq("viewed_at", today).execute().data or []
        if len(views_today) >= 10:
            return JSONResponse({"success": False, "error": "Limite de 10 pubs atteinte aujourd hui"})
        # Enregistrer la vue
        db.table("ad_views").insert({"user_id": user["id"], "ad_id": "monetag", "reward": 25, "viewed_at": today}).execute()
        # Crediter le wallet
        wallet = db.table("wallets").select("*").eq("user_id", user["id"]).execute().data
        if wallet:
            w = wallet[0]
            db.table("wallets").update({"balance": w["balance"]+25, "total_earned": w["total_earned"]+25}).eq("user_id", user["id"]).execute()
        else:
            db.table("wallets").insert({"user_id": user["id"], "balance": 25, "total_earned": 25}).execute()
        return JSONResponse({"success": True, "reward": 25})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
