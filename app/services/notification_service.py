"""
Système de notifications
"""
import logging
from supabase import Client

logger = logging.getLogger(__name__)

async def get_notifications(db: Client, user_id: str) -> list:
    try:
        res = db.table("notifications").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()
        return res.data or []
    except Exception as e:
        logger.error("[NOTIF] Erreur : %s", e)
        return []

async def get_unread_count(db: Client, user_id: str) -> int:
    try:
        res = db.table("notifications").select("id").eq("user_id", user_id).eq("is_read", False).execute()
        return len(res.data or [])
    except Exception as e:
        return 0

async def mark_all_read(db: Client, user_id: str):
    try:
        db.table("notifications").update({"is_read": True}).eq("user_id", user_id).execute()
    except Exception as e:
        logger.error("[NOTIF] Erreur mark_read : %s", e)

async def send_notification(db: Client, user_id: str, title: str, message: str, type: str = "info"):
    try:
        from app.services.push_service import send_push_to_user
        await send_push_to_user(db, user_id, title, message)
    except Exception:
        pass
    try:
        db.table("notifications").insert({
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": type,
        }).execute()
    except Exception as e:
        logger.error("[NOTIF] Erreur envoi : %s", e)

async def send_to_all(db: Client, title: str, message: str, type: str = "info"):
    try:
        users = db.table("users").select("id").eq("is_active", True).execute().data or []
        for u in users:
            await send_notification(db, u["id"], title, message, type)
        logger.info("[NOTIF] Envoyé à %d utilisateurs", len(users))
    except Exception as e:
        logger.error("[NOTIF] Erreur send_all : %s", e)
