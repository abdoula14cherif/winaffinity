"""
Service Réseau Social WIN AFFINITY
"""
import logging
from supabase import Client

logger = logging.getLogger(__name__)

async def get_posts(db: Client, limit: int = 20, offset: int = 0) -> list:
    try:
        posts = db.table("posts").select("*").eq("is_active", True).order("created_at", desc=True).limit(limit).offset(offset).execute().data or []
        for p in posts:
            user = db.table("users").select("full_name,level").eq("id", p["user_id"]).execute().data
            if user:
                p["author_name"] = user[0]["full_name"]
                p["author_level"] = user[0].get("level", "standard")
            else:
                p["author_name"] = "Membre"
                p["author_level"] = "standard"
        return posts
    except Exception as e:
        logger.error("[SOCIAL] Erreur get_posts : %s", e)
        return []

async def create_post(db: Client, user_id: str, content: str, image_url: str = None) -> dict:
    try:
        if len(content) < 5:
            return {"success": False, "error": "Message trop court"}
        if len(content) > 500:
            return {"success": False, "error": "Message trop long (max 500 caractères)"}
        post = db.table("posts").insert({
            "user_id": user_id,
            "content": content,
            "image_url": image_url or None
        }).execute().data
        return {"success": True, "post": post[0] if post else {}}
    except Exception as e:
        logger.error("[SOCIAL] Erreur create_post : %s", e)
        return {"success": False, "error": str(e)}

async def toggle_like(db: Client, user_id: str, post_id: str) -> dict:
    try:
        existing = db.table("post_likes").select("id").eq("user_id", user_id).eq("post_id", post_id).execute().data
        if existing:
            db.table("post_likes").delete().eq("user_id", user_id).eq("post_id", post_id).execute()
            post = db.table("posts").select("likes_count").eq("id", post_id).execute().data
            if post:
                new_count = max(0, post[0]["likes_count"] - 1)
                db.table("posts").update({"likes_count": new_count}).eq("id", post_id).execute()
            return {"success": True, "liked": False}
        else:
            db.table("post_likes").insert({"user_id": user_id, "post_id": post_id}).execute()
            post = db.table("posts").select("likes_count").eq("id", post_id).execute().data
            if post:
                db.table("posts").update({"likes_count": post[0]["likes_count"] + 1}).eq("id", post_id).execute()
            return {"success": True, "liked": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def add_comment(db: Client, user_id: str, post_id: str, content: str) -> dict:
    try:
        if len(content) < 2:
            return {"success": False, "error": "Commentaire trop court"}
        db.table("post_comments").insert({"user_id": user_id, "post_id": post_id, "content": content}).execute()
        post = db.table("posts").select("comments_count").eq("id", post_id).execute().data
        if post:
            db.table("posts").update({"comments_count": post[0]["comments_count"] + 1}).eq("id", post_id).execute()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def get_comments(db: Client, post_id: str) -> list:
    try:
        comments = db.table("post_comments").select("*").eq("post_id", post_id).order("created_at").execute().data or []
        for c in comments:
            user = db.table("users").select("full_name").eq("id", c["user_id"]).execute().data
            c["author_name"] = user[0]["full_name"] if user else "Membre"
        return comments
    except Exception as e:
        return []

async def get_user_likes(db: Client, user_id: str, post_ids: list) -> set:
    try:
        if not post_ids: return set()
        likes = db.table("post_likes").select("post_id").eq("user_id", user_id).in_("post_id", post_ids).execute().data or []
        return {l["post_id"] for l in likes}
    except:
        return set()
