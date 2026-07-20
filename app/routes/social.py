"""
Routes Réseau Social WIN AFFINITY
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.social_service import get_posts, create_post, toggle_like, add_comment, get_comments, get_user_likes
from app.services.commission_service import get_wallet

router = APIRouter(prefix="/social", tags=["Social"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_social(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    posts = await get_posts(db)
    post_ids = [p["id"] for p in posts]
    user_likes = await get_user_likes(db, user["id"], post_ids)
    wallet = await get_wallet(db, user["id"])
    return templates.TemplateResponse("social.html", {
        "request": request,
        "user": user,
        "posts": posts,
        "user_likes": user_likes,
        "wallet": wallet,
    })

@router.post("/post")
async def post_create(request: Request, content: Annotated[str, Form()], image_url: Annotated[str, Form()] = ""):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    result = await create_post(db, user["id"], content, image_url or None)
    return JSONResponse(result)

@router.post("/like")
async def like_post(request: Request, post_id: Annotated[str, Form()]):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    result = await toggle_like(db, user["id"], post_id)
    return JSONResponse(result)

@router.post("/comment")
async def comment_post(request: Request, post_id: Annotated[str, Form()], content: Annotated[str, Form()]):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    result = await add_comment(db, user["id"], post_id, content)
    return JSONResponse(result)

@router.get("/comments/{post_id}")
async def get_post_comments(request: Request, post_id: str):
    user = await _get_user(request)
    if not user: return JSONResponse({"comments": []})
    db = get_supabase()
    comments = await get_comments(db, post_id)
    return JSONResponse({"comments": comments})

@router.post("/delete")
async def delete_post(request: Request, post_id: Annotated[str, Form()]):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    post = db.table("posts").select("user_id").eq("id", post_id).execute().data
    if not post: return JSONResponse({"error": "Post introuvable"})
    if post[0]["user_id"] != user["id"] and user.get("role") != "admin":
        return JSONResponse({"error": "Non autorisé"})
    db.table("posts").update({"is_active": False}).eq("id", post_id).execute()
    return JSONResponse({"success": True})
