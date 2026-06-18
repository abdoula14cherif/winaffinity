"""
Commission basée sur le minimum entre niveau parrain et niveau filleul
"""
import logging
from supabase import Client

logger = logging.getLogger(__name__)

COMMISSION_BY_LEVEL = {
    "starter":  {1: 500,  2: 240, 3: 120},
    "standard": {1: 1250, 2: 600, 3: 300},
    "premium":  {1: 2500, 2: 1200, 3: 600},
}

LEVEL_RANK = {"starter": 1, "standard": 2, "premium": 3}

def get_effective_level(sponsor_level: str, referral_level: str) -> str:
    """Retourne le niveau effectif = minimum entre parrain et filleul."""
    s_rank = LEVEL_RANK.get(sponsor_level or "standard", 2)
    r_rank = LEVEL_RANK.get(referral_level or "standard", 2)
    effective_rank = min(s_rank, r_rank)
    for lvl, rank in LEVEL_RANK.items():
        if rank == effective_rank:
            return lvl
    return "standard"

async def _add_commission(db: Client, sponsor_id: str, new_user_id: str, tier: int, amount: int):
    try:
        wallet = db.table("wallets").select("*").eq("user_id", sponsor_id).execute().data
        if wallet:
            w = wallet[0]
            db.table("wallets").update({
                "balance": w["balance"] + amount,
                "total_earned": w["total_earned"] + amount
            }).eq("user_id", sponsor_id).execute()
        else:
            db.table("wallets").insert({
                "user_id": sponsor_id,
                "balance": amount,
                "total_earned": amount
            }).execute()
        db.table("commissions").insert({
            "sponsor_id": sponsor_id,
            "user_id": new_user_id,
            "tier": tier,
            "amount": amount,
        }).execute()
        logger.info("[COMMISSION] N%s → %s : +%s FCFA", tier, sponsor_id, amount)
    except Exception as e:
        logger.error("[COMMISSION] Erreur _add_commission : %s", e)

async def process_commissions(db: Client, new_user_id: str):
    """
    Commission = min(niveau parrain, niveau filleul)
    - Parrain Starter + Filleul Premium → Starter rates
    - Parrain Premium + Filleul Starter → Starter rates
    - Parrain Premium + Filleul Premium → Premium rates
    """
    try:
        # Récupérer le filleul et son niveau
        user_res = db.table("users").select("id,sponsor_id,level").eq("id", new_user_id).execute().data
        if not user_res: return
        user = user_res[0]
        referral_level = user.get("level") or "standard"
        sponsor1_id = user.get("sponsor_id")
        if not sponsor1_id: return

        # N1 - commission selon min(parrain1, filleul)
        s1_res = db.table("users").select("sponsor_id,level").eq("id", sponsor1_id).execute().data
        if not s1_res: return
        s1 = s1_res[0]
        effective1 = get_effective_level(s1.get("level") or "standard", referral_level)
        amount1 = COMMISSION_BY_LEVEL[effective1][1]
        await _add_commission(db, sponsor1_id, new_user_id, 1, amount1)

        sponsor2_id = s1.get("sponsor_id")
        if not sponsor2_id: return

        # N2 - commission selon min(parrain2, filleul)
        s2_res = db.table("users").select("sponsor_id,level").eq("id", sponsor2_id).execute().data
        if not s2_res: return
        s2 = s2_res[0]
        effective2 = get_effective_level(s2.get("level") or "standard", referral_level)
        amount2 = COMMISSION_BY_LEVEL[effective2][2]
        await _add_commission(db, sponsor2_id, new_user_id, 2, amount2)

        sponsor3_id = s2.get("sponsor_id")
        if not sponsor3_id: return

        # N3 - commission selon min(parrain3, filleul)
        s3_res = db.table("users").select("level").eq("id", sponsor3_id).execute().data
        if not s3_res: return
        s3 = s3_res[0]
        effective3 = get_effective_level(s3.get("level") or "standard", referral_level)
        amount3 = COMMISSION_BY_LEVEL[effective3][3]
        await _add_commission(db, sponsor3_id, new_user_id, 3, amount3)

    except Exception as e:
        logger.error("[COMMISSION] Erreur process_commissions : %s", e)

async def get_wallet(db: Client, user_id: str) -> dict:
    try:
        res = db.table("wallets").select("*").eq("user_id", user_id).execute().data
        if res:
            return res[0]
        return {"user_id": user_id, "balance": 0, "total_earned": 0}
    except Exception as e:
        logger.error("[WALLET] Erreur : %s", e)
        return {"user_id": user_id, "balance": 0, "total_earned": 0}

async def get_commissions(db: Client, user_id: str) -> list:
    try:
        res = db.table("commissions").select("*").eq("sponsor_id", user_id).order("created_at", desc=True).execute().data
        return res or []
    except Exception as e:
        logger.error("[COMMISSIONS] Erreur : %s", e)
        return []
