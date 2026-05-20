"""
Route page réseau
GET /network → Arbre de parrainage
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.dashboard_service import get_user_referral_tree
from app.services.commission_service import get_wallet

router = APIRouter(prefix="/network", tags=["Network"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_network(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    tree = await get_user_referral_tree(db, user["id"], depth=2)
    wallet = await get_wallet(db, user["id"])
    total_n1 = len(tree)
    total_n2 = sum(len(n.get("children", [])) for n in tree)
    active_n1 = len([n for n in tree if n.get("is_active")])
    active_n2 = sum(1 for n in tree for c in n.get("children", []) if c.get("is_active"))
    return templates.TemplateResponse("network.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "tree": tree,
        "total_n1": total_n1,
        "total_n2": total_n2,
        "active_n1": active_n1,
        "active_n2": active_n2,
        "gains_n1": active_n1 * 1250,
        "gains_n2": active_n2 * 600,
    })
