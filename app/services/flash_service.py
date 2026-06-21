"""
Service Missions Flash WIN AFFINITY
"""
import logging
from datetime import datetime, timezone
from supabase import Client

logger = logging.getLogger(__name__)

async def get_active_missions(db: Client) -> list:
    try:
        now = datetime.now(timezone.utc).isoformat()
        res = db.table("flash_missions").select("*").eq("is_active", True).lte("starts_at", now).gte("ends_at", now).order("ends_at").execute()
        return res.data or []
    except Exception as e:
        logger.error("[FLASH] Erreur get_active_missions : %s", e)
        return []

async def get_user_completions(db: Client, user_id: str) -> list:
    try:
        res = db.table("flash_completions").select("mission_id,status").eq("user_id", user_id).execute()
        return res.data or []
    except Exception as e:
        return []

async def submit_mission(db: Client, user_id: str, mission_id: str, proof_url: str = None) -> dict:
    try:
        # Vérifier si mission active
        now = datetime.now(timezone.utc).isoformat()
        mission = db.table("flash_missions").select("*").eq("id", mission_id).eq("is_active", True).lte("starts_at", now).gte("ends_at", now).execute().data
        if not mission:
            return {"success": False, "error": "Mission expirée ou introuvable"}
        mission = mission[0]

        # Vérifier places disponibles
        if mission["winners_count"] >= mission["max_winners"]:
            return {"success": False, "error": "Places épuisées pour cette mission !"}

        # Vérifier si déjà soumis
        existing = db.table("flash_completions").select("id").eq("mission_id", mission_id).eq("user_id", user_id).execute().data
        if existing:
            return {"success": False, "error": "Vous avez déjà soumis cette mission"}

        # Enregistrer la completion
        db.table("flash_completions").insert({
            "mission_id": mission_id,
            "user_id": user_id,
            "proof_url": proof_url,
            "status": "pending" if mission.get("requires_proof") else "approved"
        }).execute()

        # Si pas de preuve requise → créditer directement
        if not mission.get("requires_proof"):
            wallet = db.table("wallets").select("*").eq("user_id", user_id).execute().data
            reward = mission["reward"]
            if wallet:
                db.table("wallets").update({
                    "balance": wallet[0]["balance"] + reward,
                    "total_earned": wallet[0]["total_earned"] + reward
                }).eq("user_id", user_id).execute()
            else:
                db.table("wallets").insert({"user_id": user_id, "balance": reward, "total_earned": reward}).execute()
            db.table("flash_missions").update({"winners_count": mission["winners_count"] + 1}).eq("id", mission_id).execute()
            return {"success": True, "auto_credited": True, "reward": reward}

        return {"success": True, "auto_credited": False, "pending": True}
    except Exception as e:
        logger.error("[FLASH] Erreur submit_mission : %s", e)
        return {"success": False, "error": str(e)}

async def approve_completion(db: Client, completion_id: str) -> dict:
    try:
        comp = db.table("flash_completions").select("*").eq("id", completion_id).execute().data
        if not comp: return {"success": False, "error": "Completion introuvable"}
        comp = comp[0]
        if comp["status"] != "pending": return {"success": False, "error": "Déjà traité"}

        mission = db.table("flash_missions").select("*").eq("id", comp["mission_id"]).execute().data
        if not mission: return {"success": False, "error": "Mission introuvable"}
        mission = mission[0]

        if mission["winners_count"] >= mission["max_winners"]:
            db.table("flash_completions").update({"status": "rejected"}).eq("id", completion_id).execute()
            return {"success": False, "error": "Places épuisées"}

        reward = mission["reward"]
        wallet = db.table("wallets").select("*").eq("user_id", comp["user_id"]).execute().data
        if wallet:
            db.table("wallets").update({
                "balance": wallet[0]["balance"] + reward,
                "total_earned": wallet[0]["total_earned"] + reward
            }).eq("user_id", comp["user_id"]).execute()
        else:
            db.table("wallets").insert({"user_id": comp["user_id"], "balance": reward, "total_earned": reward}).execute()

        db.table("flash_completions").update({"status": "approved"}).eq("id", completion_id).execute()
        db.table("flash_missions").update({"winners_count": mission["winners_count"] + 1}).eq("id", comp["mission_id"]).execute()

        try:
            from app.services.push_service import send_push_to_user
            await send_push_to_user(db, comp["user_id"], "⚡ Mission validée !", f"Vous recevez +{reward} FCFA pour votre mission flash !", "/missions")
        except: pass

        return {"success": True}
    except Exception as e:
        logger.error("[FLASH] Erreur approve : %s", e)
        return {"success": False, "error": str(e)}
