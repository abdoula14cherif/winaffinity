"""
win_affinity/app/routes/dashboard.py
──────────────────────────────────────
Endpoints du dashboard utilisateur :
  GET  /dashboard          → Page principale (HTML)
  GET  /dashboard/network  → Arbre de parrainage (JSON)
  GET  /dashboard/referral-link → Lien de parrainage (JSON)
"""

import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.dashboard_service import get_dashboard_stats, get_user_referral_tree

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


# ── Helper : utilisateur courant ──────────────────────────────────────────────
async def _get_current_user(request: Request) -> dict | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    db = get_supabase()
    return await get_user_by_id(db, payload["sub"])


# ── Page principale ───────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse, name="dashboard_page")
async def get_dashboard(request: Request):
    """
    Page dashboard principale.
    Redirige vers /auth/login si non connecté.
    Redirige vers /payment si compte non activé.
    """
    user = await _get_current_user(request)

    if not user:
        return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"):
        return RedirectResponse("/payment", status_code=302)

    db = get_supabase()
    try:
        data = await get_dashboard_stats(db, user["id"])
    except Exception as e:
        logger.error("[DASHBOARD] Erreur chargement stats : %s", e)
        data = {
            "user": user,
            "stats": {
                "total_balance_fcfa": 0,
                "total_referrals": 0,
                "active_referrals": 0,
                "inactive_referrals": 0,
                "gain_n1_fcfa": 0,
                "referral_link": "",
                "commission_rate_n1": 30,
            },
            "referrals": [],
            "transactions": [],
        }

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, **data},
    )


# ── Arbre réseau (JSON) ───────────────────────────────────────────────────────
@router.get("/network", name="dashboard_network")
async def get_network(request: Request):
    """Retourne l'arbre de parrainage en JSON pour le graphe interactif."""
    user = await _get_current_user(request)
    if not user:
        return JSONResponse({"error": "Non authentifié."}, status_code=401)
    if not user.get("is_active"):
        return JSONResponse({"error": "Compte non activé."}, status_code=403)

    db = get_supabase()
    tree = await get_user_referral_tree(db, user["id"], depth=2)
    return JSONResponse({"tree": tree, "total": len(tree)})
