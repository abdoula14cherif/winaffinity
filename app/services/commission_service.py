"""
Système de commissions 3 niveaux
N1: 1250 FCFA, N2: 600 FCFA, N3: 300 FCFA
"""
import logging
from supabase import Client

logger = logging.getLogger(__name__)

COMMISSIONS = {1: 1250, 2: 600, 3: 300}


async def process_commissions(db: Client, new_user_id: str):
    try:
        user_res = db.table("users").select("id,sponsor_id,full_name").eq("id", new_user_id).execute()
        if not user_res.data:
            return
        user = user_res.data[0]
        sponsor1_id = user.get("sponsor_id")
        if not sponsor1_id:
            return

        await _add_commission(db, sponsor1_id, new_user_id, 1)

        s1_res = db.table("users").select("sponsor_id").eq("id", sponsor1_id).execute()
        if not s1_res.data:
            return
        sponsor2_id = s1_res.data[0].get("sponsor_id")
        if not sponsor2_id:
            return
        await _add_commission(db, sponsor2_id, new_user_id, 2)

        s2_res = db.table("users").select("sponsor_id").eq("id", sponsor2_id).execute()
        if not s2_res.data:
            return
        sponsor3_id = s2_res.data[0].get("sponsor_id")
        if not sponsor3_id:
            return
        await _add_commission(db, sponsor3_id, new_user_id, 3)

    except Exception as e:
        logger.error("[COMMISSION] Erreur : %s", e)


async def _add_commission(db: Client, beneficiary_id: str, from_user_id: str, level: int):
    amount = COMMISSIONS[level]
    try:
        db.table("commissions").insert({
            "beneficiary_id": beneficiary_id,
            "from_user_id": from_user_id,
            "level": level,
            "amount": amount,
            "status": "paid"
        }).execute()

        wallet_res = db.table("wallets").select("*").eq("user_id", beneficiary_id).execute()
        if wallet_res.data:
            old = wallet_res.data[0]
            db.table("wallets").update({
                "balance": old["balance"] + amount,
                "total_earned": old["total_earned"] + amount
            }).eq("user_id", beneficiary_id).execute()
        else:
            db.table("wallets").insert({
                "user_id": beneficiary_id,
                "balance": amount,
                "total_earned": amount
            }).execute()

        logger.info("[COMMISSION] Niveau %d : %s FCFA -> %s", level, amount, beneficiary_id)

        try:
            user_res = db.table("users").select("email,full_name").eq("id", beneficiary_id).execute()
            from_res = db.table("users").select("full_name").eq("id", from_user_id).execute()
            if user_res.data and from_res.data:
                from app.services.email_service import send_commission_received
                await send_commission_received(user_res.data[0]["email"], user_res.data[0]["full_name"], amount, level, from_res.data[0]["full_name"])
        except Exception:
            pass

    except Exception as e:
        logger.error("[COMMISSION] Erreur niveau %d : %s", level, e)


async def get_wallet(db: Client, user_id: str) -> dict:
    try:
        res = db.table("wallets").select("*").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0]
        return {"balance": 0, "total_earned": 0}
    except Exception as e:
        logger.error("[WALLET] Erreur : %s", e)
        return {"balance": 0, "total_earned": 0}


async def get_commissions(db: Client, user_id: str) -> list:
    try:
        res = db.table("commissions").select("*, from_user:from_user_id(full_name)").eq("beneficiary_id", user_id).order("created_at", desc=True).limit(50).execute()
        return res.data or []
    except Exception as e:
        logger.error("[COMMISSION] Erreur historique : %s", e)
        return []
