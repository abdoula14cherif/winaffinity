from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import supabase_public

router = APIRouter(prefix="/promotions", tags=["promotions"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/")
@limiter.limit("30/minute")
async def list_promotions(request: Request):
    result = (
        supabase_public.table("promotions")
        .select("*")
        .eq("actif", True)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data
