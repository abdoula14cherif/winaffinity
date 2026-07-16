"""
Dashboard service - soldes en FCFA
"""
import logging
from supabase import Client
from app.services.commission_service import get_wallet, get_commissions  # noqa

logger = logging.getLogger(__name__)

async def get_dashboard_stats(db: Client, user_id: str) -> dict:
    try:
        user_res = db.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            raise ValueError("Utilisateur introuvable.")
        user = user_res.data[0]
    except ValueError:
        raise
    except Exception as e:
        logger.error("[DASHBOARD] Erreur user : %s", e)
        raise RuntimeError("Impossible de charger le profil.") from e

    # Filleuls directs
    try:
        ref_res = db.table("users").select("id,full_name,email,is_active,created_at").eq("sponsor_id", user_id).order("created_at", desc=True).execute()
        referrals = ref_res.data or []
    except Exception as e:
        logger.error("[DASHBOARD] Erreur filleuls : %s", e)
        referrals = []

    active_referrals   = [r for r in referrals if r.get("is_active")]
    inactive_referrals = [r for r in referrals if not r.get("is_active")]

    # Wallet réel depuis la base
    wallet = await get_wallet(db, user_id)

    # Commissions reçues
    commissions = await get_commissions(db, user_id)

    # Lien de parrainage
    referral_link = f"https://www.winaffinity.vip/auth/register?ref={user['referral_code']}"

    stats = {
        "total_balance_fcfa"  : wallet["balance"],
        "total_earned_fcfa"   : wallet["total_earned"],
        "total_referrals"     : len(referrals),
        "active_referrals"    : len(active_referrals),
        "inactive_referrals"  : len(inactive_referrals),
        "gain_n1_fcfa"        : len(active_referrals) * 1250,
        "referral_link"       : referral_link,
        "commission_rate_n1"  : 1250,
        "commission_rate_n2"  : 600,
        "commission_rate_n3"  : 300,
    }

    return {
        "user"        : user,
        "stats"       : stats,
        "referrals"   : referrals,
        "transactions": commissions,
    }


async def get_user_referral_tree(db, user_id: str, depth: int = 2) -> list:
    tree = []
    try:
        lvl1 = db.table("users").select("id,full_name,is_active,created_at").eq("sponsor_id", user_id).execute().data or []
        for m in lvl1:
            node = {**m, "level": 1, "children": []}
            if depth >= 2:
                lvl2 = db.table("users").select("id,full_name,is_active,created_at").eq("sponsor_id", m["id"]).execute().data or []
                node["children"] = [{**x, "level": 2} for x in lvl2]
            tree.append(node)
    except Exception as e:
        pass
    return tree
