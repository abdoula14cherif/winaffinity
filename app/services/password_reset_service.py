"""
Service de réinitialisation de mot de passe
"""
import secrets
import logging
from datetime import datetime, timezone, timedelta
from supabase import Client

logger = logging.getLogger(__name__)

async def create_reset_token(db: Client, email: str) -> dict:
    try:
        user = db.table("users").select("id,email,full_name").eq("email", email).execute().data
        if not user:
            return {"success": True}  # Ne pas révéler si l'email existe
        user = user[0]
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        db.table("password_resets").insert({
            "user_id": user["id"],
            "token": token,
            "expires_at": expires,
        }).execute()
        return {"success": True, "token": token, "user": user}
    except Exception as e:
        logger.error("[RESET] Erreur : %s", e)
        return {"success": False, "error": str(e)}

async def verify_reset_token(db: Client, token: str) -> dict:
    try:
        now = datetime.now(timezone.utc).isoformat()
        res = db.table("password_resets").select("*").eq("token", token).eq("used", False).gte("expires_at", now).execute().data
        if not res:
            return {"valid": False}
        return {"valid": True, "reset": res[0]}
    except Exception as e:
        logger.error("[RESET] Erreur verify : %s", e)
        return {"valid": False}

async def reset_password(db: Client, token: str, new_password: str) -> dict:
    try:
        verify = await verify_reset_token(db, token)
        if not verify["valid"]:
            return {"success": False, "error": "Lien invalide ou expiré."}
        reset = verify["reset"]
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = pwd_context.hash(new_password)
        db.table("users").update({"hashed_password": hashed}).eq("id", reset["user_id"]).execute()
        db.table("password_resets").update({"used": True}).eq("id", reset["id"]).execute()
        return {"success": True}
    except Exception as e:
        logger.error("[RESET] Erreur reset : %s", e)
        return {"success": False, "error": str(e)}
