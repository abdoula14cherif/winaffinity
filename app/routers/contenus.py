from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import supabase_public, supabase_admin

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


from pydantic import BaseModel

class AchatPayload(BaseModel):
    contenu_id: str
    referral_code: str | None = None


@router.post("/achat")
@limiter.limit("10/minute")
async def enregistrer_achat(request: Request, payload: AchatPayload):
    contenu_result = supabase_admin.table("contenus").select("*").eq("id", payload.contenu_id).execute()
    if not contenu_result.data:
        raise HTTPException(status_code=404, detail="Contenu introuvable")

    contenu = contenu_result.data[0]
    montant = contenu["prix"]

    referrer_id = None
    commission = 0

    if payload.referral_code:
        referrer_result = supabase_admin.table("users").select("id").eq("referral_code", payload.referral_code).execute()
        if referrer_result.data:
            referrer_id = referrer_result.data[0]["id"]
            commission = round(montant * 0.5)

    transaction = {
        "contenu_id": payload.contenu_id,
        "montant": montant,
        "referrer_id": referrer_id,
        "commission": commission,
        "statut": "confirme",
    }

    result = supabase_admin.table("transactions").insert(transaction).execute()
    return {
        "transaction": result.data[0] if result.data else None,
        "lien_acces": contenu.get("lien_acces"),
    }


from app.dependencies import get_current_admin_id
from fastapi import UploadFile, File
import uuid
from app.config import settings


class ContenuCreate(BaseModel):
    titre: str
    type: str
    categorie: str
    prix: int
    description: str | None = None
    description_longue: str | None = None
    image_url: str | None = None
    points_forts: str | None = None
    lien_acces: str | None = None


class ContenuUpdate(BaseModel):
    titre: str | None = None
    type: str | None = None
    categorie: str | None = None
    prix: int | None = None
    description: str | None = None
    description_longue: str | None = None
    image_url: str | None = None
    points_forts: str | None = None
    lien_acces: str | None = None


@router.post("/admin/create", status_code=201)
@limiter.limit("20/minute")
async def create_contenu(request: Request, payload: ContenuCreate, admin_id: str = Depends(get_current_admin_id)):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    result = supabase_admin.table("contenus").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création")
    return result.data[0]


@router.put("/admin/{contenu_id}")
@limiter.limit("20/minute")
async def update_contenu(request: Request, contenu_id: str, payload: ContenuUpdate, admin_id: str = Depends(get_current_admin_id)):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")
    result = supabase_admin.table("contenus").update(data).eq("id", contenu_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contenu introuvable")
    return result.data[0]


@router.delete("/admin/{contenu_id}")
@limiter.limit("20/minute")
async def delete_contenu(request: Request, contenu_id: str, admin_id: str = Depends(get_current_admin_id)):
    result = supabase_admin.table("contenus").delete().eq("id", contenu_id).execute()
    return {"deleted": True}


@router.post("/admin/upload-image")
@limiter.limit("20/minute")
async def upload_image(request: Request, file: UploadFile = File(...), admin_id: str = Depends(get_current_admin_id)):
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    path = f"{uuid.uuid4()}.{ext}"
    content = await file.read()

    supabase_admin.storage.from_("contenus-images").upload(
        path, content, {"content-type": file.content_type}
    )

    url = f"{settings.supabase_url}/storage/v1/object/public/contenus-images/{path}"
    return {"url": url}
