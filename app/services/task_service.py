"""
Système de tâches quotidiennes
Récompenses : 300, 100 ou 55 FCFA
"""
import logging
from datetime import datetime, timezone
from supabase import Client

logger = logging.getLogger(__name__)

async def get_tasks_with_status(db: Client, user_id: str) -> list:
    """Retourne toutes les tâches avec statut complété ou non pour aujourd'hui."""
    try:
        tasks_res = db.table("tasks").select("*").eq("is_active", True).order("created_at").execute()
        tasks = tasks_res.data or []

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        done_res = db.table("task_completions").select("task_id").eq("user_id", user_id).gte("completed_at", today).execute()
        done_ids = [r["task_id"] for r in (done_res.data or [])]

        for t in tasks:
            t["completed_today"] = t["id"] in done_ids
        return tasks
    except Exception as e:
        logger.error("[TASKS] Erreur : %s", e)
        return []


async def complete_task(db: Client, user_id: str, task_id: str) -> dict:
    """
    Marque une tâche comme complétée et crédite le wallet.
    Vérifie qu'elle n'a pas déjà été faite aujourd'hui.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Vérifier si déjà complétée aujourd'hui
    done = db.table("task_completions").select("id").eq("user_id", user_id).eq("task_id", task_id).gte("completed_at", today).execute()
    if done.data:
        raise ValueError("Tâche déjà complétée aujourd'hui.")

    # Récupérer la tâche
    task_res = db.table("tasks").select("*").eq("id", task_id).eq("is_active", True).execute()
    if not task_res.data:
        raise ValueError("Tâche introuvable.")
    task = task_res.data[0]
    reward = task["reward"]

    # Enregistrer la complétion
    db.table("task_completions").insert({
        "user_id": user_id,
        "task_id": task_id,
    }).execute()

    # Créditer le wallet
    wallet_res = db.table("wallets").select("*").eq("user_id", user_id).execute()
    if wallet_res.data:
        w = wallet_res.data[0]
        db.table("wallets").update({
            "balance": w["balance"] + reward,
            "total_earned": w["total_earned"] + reward,
        }).eq("user_id", user_id).execute()
    else:
        db.table("wallets").insert({
            "user_id": user_id,
            "balance": reward,
            "total_earned": reward,
        }).execute()

    logger.info("[TASKS] Tâche complétée : %s FCFA pour %s", reward, user_id)
    return {"reward": reward, "task": task}
