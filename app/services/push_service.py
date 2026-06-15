"""
Notifications Push Web (style WhatsApp)
"""
import os
import json
import logging
from pywebpush import webpush, WebPushException
from supabase import Client

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_CLAIMS_EMAIL = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:contact@winaffinity.com")


async def save_subscription(db: Client, user_id: str, subscription: dict):
    try:
        db.table("push_subscriptions").upsert({
            "user_id": user_id,
            "endpoint": subscription["endpoint"],
            "p256dh": subscription["keys"]["p256dh"],
            "auth": subscription["keys"]["auth"],
        }, on_conflict="user_id,endpoint").execute()
        return True
    except Exception as e:
        logger.error("[PUSH] Erreur save_subscription : %s", e)
        return False


async def send_push_to_user(db: Client, user_id: str, title: str, body: str, url: str = "/dashboard"):
    if not VAPID_PRIVATE_KEY:
        logger.warning("[PUSH] VAPID_PRIVATE_KEY non configuré")
        return 0
    try:
        subs = db.table("push_subscriptions").select("*").eq("user_id", user_id).execute().data or []
        sent = 0
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                    },
                    data=json.dumps({"title": title, "body": body, "url": url}),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
                )
                sent += 1
            except WebPushException as e:
                logger.warning("[PUSH] Erreur envoi : %s", e)
                if e.response is not None and e.response.status_code in (404, 410):
                    db.table("push_subscriptions").delete().eq("id", sub["id"]).execute()
        return sent
    except Exception as e:
        logger.error("[PUSH] Erreur send_push_to_user : %s", e)
        return 0


async def send_push_to_all(db: Client, title: str, body: str, url: str = "/dashboard", only_active: bool = False):
    try:
        subs = db.table("push_subscriptions").select("*").execute().data or []
        sent = 0
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                    },
                    data=json.dumps({"title": title, "body": body, "url": url}),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
                )
                sent += 1
            except WebPushException as e:
                if e.response is not None and e.response.status_code in (404, 410):
                    db.table("push_subscriptions").delete().eq("id", sub["id"]).execute()
        return sent
    except Exception as e:
        logger.error("[PUSH] Erreur send_push_to_all : %s", e)
        return 0
