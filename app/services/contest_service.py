"""
Grand concours WIN AFFINITY
Paliers basés sur le nombre de filleuls ACTIFS
"""
import logging
from supabase import Client

logger = logging.getLogger(__name__)

CONTEST_TIERS = [
    {"tier": 1, "target": 20,  "cash": 5000,  "item": None},
    {"tier": 2, "target": 50,  "cash": 15000, "item": "T-shirt WIN AFFINITY"},
    {"tier": 3, "target": 100, "cash": 30000, "item": "iPhone 15 + T-shirt WIN AFFINITY"},
]

async def get_contest_progress(db: Client, user_id: str) -> dict:
    """Retourne la progression de l'utilisateur dans le concours."""
    try:
        active_referrals = db.table("users").select("id").eq("sponsor_id", user_id).eq("is_active", True).execute().data or []
        count = len(active_referrals)

        claimed = db.table("contest_rewards").select("tier").eq("user_id", user_id).execute().data or []
        claimed_tiers = {c["tier"] for c in claimed}

        tiers = []
        for t in CONTEST_TIERS:
            progress_pct = min(100, round((count / t["target"]) * 100))
            unlocked = count >= t["target"]
            tiers.append({
                "tier": t["tier"],
                "target": t["target"],
                "cash": t["cash"],
                "item": t["item"],
                "progress": progress_pct,
                "unlocked": unlocked,
                "claimed": t["tier"] in claimed_tiers,
                "remaining": max(0, t["target"] - count),
            })

        return {"active_referrals": count, "tiers": tiers}
    except Exception as e:
        logger.error("[CONTEST] Erreur progression : %s", e)
        return {"active_referrals": 0, "tiers": []}


async def claim_reward(db: Client, user_id: str, tier: int) -> dict:
    """Marque un palier comme réclamé (l'admin traite manuellement le paiement)."""
    try:
        progress = await get_contest_progress(db, user_id)
        tier_data = next((t for t in progress["tiers"] if t["tier"] == tier), None)
        if not tier_data:
            return {"success": False, "error": "Palier invalide."}
        if not tier_data["unlocked"]:
            return {"success": False, "error": "Objectif non atteint."}
        if tier_data["claimed"]:
            return {"success": False, "error": "Déjà réclamé."}

        db.table("contest_rewards").insert({
            "user_id": user_id,
            "tier": tier,
            "reward_cash": tier_data["cash"],
            "reward_item": tier_data["item"],
            "claimed": True,
        }).execute()

        # Notification admin / utilisateur
        from app.services.notification_service import send_notification
        msg = f"Félicitations ! Vous avez atteint le palier {tier} ({tier_data['target']} filleuls actifs). Récompense : {tier_data['cash']} FCFA"
        if tier_data["item"]:
            msg += f" + {tier_data['item']}"
        msg += ". Notre équipe va vous contacter pour la remise du prix."
        await send_notification(db, user_id, "🏆 Concours - Palier atteint !", msg, "success")

        return {"success": True}
    except Exception as e:
        logger.error("[CONTEST] Erreur claim : %s", e)
        return {"success": False, "error": str(e)}
