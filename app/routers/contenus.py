from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import supabase_public

router = APIRouter(prefix="/contenus", tags=["contenus"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/")
@limiter.limit("30/minute")
async def list_contenus(request: Request, categorie: str | None = None, type: str | None = None):
    query = supabase_public.table("contenus").select("*").order("created_at", desc=True)

    if categorie:
        query = query.eq("categorie", categorie)
    if type:
        query = query.eq("type", type)

    result = query.execute()
    return result.data


@router.get("/stats")
@limiter.limit("30/minute")
async def contenus_stats(request: Request):
    result = supabase_public.table("contenus").select("categorie").execute()
    counts = {}
    for row in result.data:
        cat = row["categorie"]
        counts[cat] = counts.get(cat, 0) + 1
    return {"total": len(result.data), "par_categorie": counts}


@router.get("/{contenu_id}")
@limiter.limit("30/minute")
async def get_contenu(request: Request, contenu_id: str):
    result = supabase_public.table("contenus").select("*").eq("id", contenu_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contenu introuvable")
    return result.data[0]
