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

# Valeur unique de la récompense par pub et du délai entre 2 vues.
# Garder ces deux constantes alignées avec AD_REWARD / AD_WAIT_SECONDS côté frontend (gains.html).
AD_REWARD = 1
AD_COOLDOWN_SECONDS = 60
AD_DAILY_LIMIT = 100


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
    try:
        user = await _get_user(request)
        if not user:
            return JSONResponse({"count": 0})
        db = get_supabase()
        from datetime import date
        today = str(date.today())
        res = db.table("ad_views").select("id").eq("user_id", user["id"]).eq("viewed_at", today).execute()
        return JSONResponse({"count": len(res.data or [])})
    except Exception:
        logger.exception("Erreur /gains/ad/count")
        return JSONResponse({"count": 0})


@router.post("/ad/view")
async def view_ad(request: Request):
    # Tout est dans le try/except : la moindre exception (y compris get_supabase())
    # renvoie maintenant une réponse JSON propre au lieu d'une page d'erreur HTML
    # que le frontend ne peut pas parser (= "Erreur réseau" côté utilisateur).
    try:
        user = await _get_user(request)
        if not user:
            return JSONResponse({"success": False, "error": "Non authentifié"}, status_code=401)
        if not user.get("is_active"):
            return JSONResponse({"success": False, "error": "Compte non activé"})

        db = get_supabase()
        from datetime import date, datetime, timezone
        today = str(date.today())

        views_today = (
            db.table("ad_views")
            .select("id,created_at")
            .eq("user_id", user["id"])
            .eq("viewed_at", today)
            .order("created_at", desc=True)
            .execute()
            .data or []
        )

        if len(views_today) >= AD_DAILY_LIMIT:
            return JSONResponse({"success": False, "error": f"Limite de {AD_DAILY_LIMIT} pubs atteinte aujourd'hui"})

        if views_today:
            last = views_today[0]
            last_created = last.get("created_at")
            if last_created:
                try:
                    last_time = datetime.fromisoformat(last_created.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    diff = (now - last_time).total_seconds()
                    if diff < AD_COOLDOWN_SECONDS:
                        wait = int(AD_COOLDOWN_SECONDS - diff)
                        return JSONResponse({"success": False, "error": f"Attendez encore {wait} secondes", "wait": wait})
                except (ValueError, TypeError):
                    logger.warning("created_at invalide dans ad_views: %r", last_created)
                    # on ne bloque pas l'utilisateur si la date est mal formée

        # Enregistrer la vue (created_at fourni explicitement au cas où la colonne
        # n'a pas de valeur par défaut côté Supabase)
        db.table("ad_views").insert({
            "user_id": user["id"],
            "ad_id": "monetag",
            "reward": AD_REWARD,
            "viewed_at": today,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        # Créditer le wallet
        wallet_res = db.table("wallets").select("*").eq("user_id", user["id"]).execute().data
        if wallet_res:
            w = wallet_res[0]
            current_balance = w.get("balance") or 0
            current_total = w.get("total_earned") or 0
            new_balance = current_balance + AD_REWARD
            new_total = current_total + AD_REWARD
            db.table("wallets").update({
                "balance": new_balance,
                "total_earned": new_total,
            }).eq("user_id", user["id"]).execute()
        else:
            new_balance = AD_REWARD
            new_total = AD_REWARD
            db.table("wallets").insert({
                "user_id": user["id"],
                "balance": new_balance,
                "total_earned": new_total,
            }).execute()

        return JSONResponse({
            "success": True,
            "reward": AD_REWARD,
            "balance": new_balance,
            "total_earned": new_total,
        })

    except Exception as e:
        logger.exception("Erreur /gains/ad/view")
        return JSONResponse({"success": False, "error": "Erreur serveur, réessayez."}, status_code=500)
