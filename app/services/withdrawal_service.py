"""
Système de retrait
Minimum : 1000 FCFA
Frais : 10%
"""
import logging
from supabase import Client

logger = logging.getLogger(__name__)

MINIMUM_WITHDRAWAL = 1000
FEE_RATE = 0.10


async def request_withdrawal(db: Client, user_id: str, amount: int, phone: str, operator: str) -> dict:
    if amount < MINIMUM_WITHDRAWAL:
        raise ValueError(f"Montant minimum de retrait : {MINIMUM_WITHDRAWAL} FCFA.")

    fee = int(amount * FEE_RATE)
    net_amount = amount - fee

    wallet_res = db.table("wallets").select("*").eq("user_id", user_id).execute()
    if not wallet_res.data:
        raise ValueError("Portefeuille introuvable.")
    wallet = wallet_res.data[0]

    if wallet["balance"] < amount:
        raise ValueError(f"Solde insuffisant. Votre solde : {wallet['balance']} FCFA.")

    # Vérifier qu'il a au moins 1 filleul actif
    referrals = db.table("users").select("id").eq("sponsor_id", user_id).eq("is_active", True).execute().data or []
    if len(referrals) < 1:
        raise ValueError("Vous devez avoir au moins 1 filleul actif pour effectuer un retrait.")

    pending = db.table("withdrawals").select("id").eq("user_id", user_id).eq("status", "pending").execute()
    if pending.data:
        raise ValueError("Vous avez déjà une demande de retrait en cours.")

    db.table("wallets").update({
        "balance": wallet["balance"] - amount
    }).eq("user_id", user_id).execute()

    result = db.table("withdrawals").insert({
        "user_id": user_id,
        "amount": amount,
        "fee": fee,
        "net_amount": net_amount,
        "phone": phone,
        "operator": operator,
        "status": "pending"
    }).execute()

    logger.info("[WITHDRAWAL] Demande créée : %s FCFA pour user %s", amount, user_id)

    try:
        user_res = db.table("users").select("email,full_name").eq("id", user_id).execute()
        if user_res.data:
            u = user_res.data[0]
            from app.services.email_service import send_withdrawal_requested
            await send_withdrawal_requested(u["email"], u["full_name"], amount, net_amount, operator)
    except Exception:
        pass

    return result.data[0]


async def get_withdrawals(db: Client, user_id: str) -> list:
    try:
        res = db.table("withdrawals").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.error("[WITHDRAWAL] Erreur historique : %s", e)
        return []
