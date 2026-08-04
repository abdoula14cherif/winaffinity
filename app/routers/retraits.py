from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel

from app.database import supabase_admin
from app.dependencies import get_current_user_id

router = APIRouter(prefix="/retraits", tags=["retraits"])
limiter = Limiter(key_func=get_remote_address)


class RetraitCreate(BaseModel):
    montant: int
    pays: str
    operateur: str
    telephone: str


def _calculer_solde_disponible(user_id: str) -> int:
    transactions = (
        supabase_admin.table("transactions")
        .select("commission")
        .eq("referrer_id", user_id)
        .eq("statut", "paid")
        .execute()
    )
    total_gagne = sum(t["commission"] for t in transactions.data)

    retraits = (
        supabase_admin.table("retraits")
        .select("montant")
        .eq("user_id", user_id)
        .neq("statut", "rejete")
        .execute()
    )
    total_retire = sum(r["montant"] for r in retraits.data)

    return total_gagne - total_retire


@router.post("/demander", status_code=201)
@limiter.limit("5/minute")
async def demander_retrait(request: Request, payload: RetraitCreate, user_id: str = Depends(get_current_user_id)):
    if payload.montant < 1000:
        raise HTTPException(status_code=400, detail="Le montant minimum de retrait est 1000 F CFA")

    solde = _calculer_solde_disponible(user_id)
    if payload.montant > solde:
        raise HTTPException(status_code=400, detail="Solde insuffisant")

    retrait = {
        "user_id": user_id,
        "montant": payload.montant,
        "pays": payload.pays,
        "operateur": payload.operateur,
        "telephone": payload.telephone,
        "statut": "en_attente",
    }
    result = supabase_admin.table("retraits").insert(retrait).execute()
    return result.data[0]


@router.get("/mes")
@limiter.limit("30/minute")
async def mes_retraits(request: Request, user_id: str = Depends(get_current_user_id)):
    result = (
        supabase_admin.table("retraits")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/solde-disponible")
@limiter.limit("30/minute")
async def solde_disponible(request: Request, user_id: str = Depends(get_current_user_id)):
    return {"solde": _calculer_solde_disponible(user_id)}
