"""
Chat support en temps réel
"""
import logging
from supabase import Client

logger = logging.getLogger(__name__)

async def get_messages(db: Client, user_id: str) -> list:
    try:
        res = db.table("support_messages").select("*").eq("user_id", user_id).order("created_at").execute()
        return res.data or []
    except Exception as e:
        logger.error("[SUPPORT] Erreur : %s", e)
        return []

async def send_message(db: Client, user_id: str, sender: str, message: str):
    try:
        db.table("support_messages").insert({
            "user_id": user_id,
            "sender": sender,
            "message": message,
        }).execute()
        if sender == "user":
            from app.services.notification_service import send_to_admins
        return True
    except Exception as e:
        logger.error("[SUPPORT] Erreur envoi : %s", e)
        return False

async def get_all_conversations(db: Client) -> list:
    """Pour l'admin : liste des conversations avec dernier message."""
    try:
        msgs = db.table("support_messages").select("*").order("created_at", desc=True).execute().data or []
        conversations = {}
        for m in msgs:
            uid = m["user_id"]
            if uid not in conversations:
                conversations[uid] = {
                    "user_id": uid,
                    "last_message": m["message"],
                    "last_sender": m["sender"],
                    "last_date": m["created_at"],
                    "unread": 0,
                }
            if m["sender"] == "user" and not m["is_read"]:
                conversations[uid]["unread"] += 1
        # Ajouter infos utilisateur
        for uid, conv in conversations.items():
            u = db.table("users").select("full_name,email").eq("id", uid).execute().data
            if u:
                conv["full_name"] = u[0]["full_name"]
                conv["email"] = u[0]["email"]
            else:
                conv["full_name"] = "Inconnu"
                conv["email"] = ""
        return sorted(conversations.values(), key=lambda x: x["last_date"], reverse=True)
    except Exception as e:
        logger.error("[SUPPORT] Erreur conversations : %s", e)
        return []

async def mark_read(db: Client, user_id: str, sender_to_mark: str):
    try:
        db.table("support_messages").update({"is_read": True}).eq("user_id", user_id).eq("sender", sender_to_mark).execute()
    except Exception as e:
        logger.error("[SUPPORT] Erreur mark_read : %s", e)
