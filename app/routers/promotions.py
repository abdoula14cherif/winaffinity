from fastapi import APIRouter, Request, Depends, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel

from app.database import supabase_public, supabase_admin
from app.dependencies import get_current_admin_id

router = APIRouter(prefix="/promotions", tags=["promotions"])
limiter = Limiter(key_func=get_remote_address)


class PromotionCreate(BaseModel):
    titre: str
    description: str | None = None
    badge: str | None = None
    date_fin: str | None = None
    actif: bool = True


class PromotionUpdate(BaseModel):
    titre: str | None = None
    description: str | None = None
    badge: str | None = None
    date_fin: str | None = None
    actif: bool | None = None


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


@router.get("/admin/all")
@limiter.limit("30/minute")
async def list_all_promotions(request: Request, admin_id: str = Depends(get_current_admin_id)):
    result = supabase_admin.table("promotions").select("*").order("created_at", desc=True).execute()
    return result.data


@router.post("/admin/create", status_code=201)
@limiter.limit("20/minute")
async def create_promotion(request: Request, payload: PromotionCreate, admin_id: str = Depends(get_current_admin_id)):
    result = supabase_admin.table("promotions").insert(payload.model_dump()).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")
    return result.data[0]


@router.put("/admin/{promo_id}")
@limiter.limit("20/minute")
async def update_promotion(request: Request, promo_id: str, payload: PromotionUpdate, admin_id: str = Depends(get_current_admin_id)):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = supabase_admin.table("promotions").update(data).eq("id", promo_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Promotion introuvable")
    return result.data[0]


@router.delete("/admin/{promo_id}")
@limiter.limit("20/minute")
async def delete_promotion(request: Request, promo_id: str, admin_id: str = Depends(get_current_admin_id)):
    supabase_admin.table("promotions").delete().eq("id", promo_id).execute()
    return {"deleted": True}
