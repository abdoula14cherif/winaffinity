"""
Routes de retrait
GET  /withdrawal      → Page retrait (HTML)
POST /withdrawal      → Soumettre demande
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.commission_service import get_wallet
from app.services.withdrawal_service import request_withdrawal, get_withdrawals

router = APIRouter(prefix="/withdrawal", tags=["Withdrawal"])
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
async def get_withdrawal(request: Request):
    user = await _get_user(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"):
        return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    withdrawals = await get_withdrawals(db, user["id"])
    return templates.TemplateResponse("withdrawal.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "withdrawals": withdrawals,
        "min_amount": 1000,
        "fee_rate": 10,
        "error": None,
        "success": None,
    })

@router.post("", response_class=HTMLResponse)
async def post_withdrawal(
    request: Request,
    amount: Annotated[int, Form()],
    phone: Annotated[str, Form()],
    operator: Annotated[str, Form()],
    country: Annotated[str, Form()] = "SN",
    account_name: Annotated[str, Form()] = "",
):
    user = await _get_user(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)
    
    db = get_supabase()
    
    try:
        # 1. Vérifier le solde avant la demande
        current_wallet = await get_wallet(db, user["id"])
        if current_wallet["balance"] < amount:
            # Récupérer les données pour rafraîchir la page
            wallet = await get_wallet(db, user["id"])
            withdrawals = await get_withdrawals(db, user["id"])
            return templates.TemplateResponse("withdrawal.html", {
                "request": request, "user": user,
                "wallet": wallet, "withdrawals": withdrawals,
                "min_amount": 1000, "fee_rate": 10,
                "error": f"Solde insuffisant. Votre solde est de {current_wallet['balance']} FCFA",
                "success": None,
            })
        
        # 2. Exécuter la demande de retrait
        await request_withdrawal(db, user["id"], amount, phone, operator, country, account_name)
        
        # 3. Récupérer le NOUVEAU solde après retrait
        new_wallet = await get_wallet(db, user["id"])
        new_withdrawals = await get_withdrawals(db, user["id"])
        
        return templates.TemplateResponse("withdrawal.html", {
            "request": request, "user": user,
            "wallet": new_wallet,  # ← Correction: nouveau solde
            "withdrawals": new_withdrawals,  # ← Correction: historique mis à jour
            "min_amount": 1000, "fee_rate": 10,
            "error": None,
            "success": f"Demande de {amount} FCFA envoyée ! Vous recevrez {int(amount*0.9)} FCFA.",
        })
        
    except ValueError as e:
        # En cas d'erreur, rafraîchir les données
        wallet = await get_wallet(db, user["id"])
        withdrawals = await get_withdrawals(db, user["id"])
        return templates.TemplateResponse("withdrawal.html", {
            "request": request, "user": user,
            "wallet": wallet, "withdrawals": withdrawals,
            "min_amount": 1000, "fee_rate": 10,
            "error": str(e), "success": None,
        })
        
    except Exception as e:
        logger.error(f"Erreur inattendue lors du retrait: {str(e)}")
        wallet = await get_wallet(db, user["id"])
        withdrawals = await get_withdrawals(db, user["id"])
        return templates.TemplateResponse("withdrawal.html", {
            "request": request, "user": user,
            "wallet": wallet, "withdrawals": withdrawals,
            "min_amount": 1000, "fee_rate": 10,
            "error": "Erreur interne. Veuillez réessayer plus tard.",
            "success": None,
        })