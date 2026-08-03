from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import supabase_admin
from app.dependencies import get_current_user_id
from app.schemas import UserRegister, UserLogin, UserOut, Token
from app.security import hash_password, verify_password, create_access_token
from app.utils import generate_referral_code

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


def _unique_referral_code() -> str:
    for _ in range(10):
        code = generate_referral_code()
        existing = (
            supabase_admin.table("users")
            .select("id")
            .eq("referral_code", code)
            .execute()
        )
        if not existing.data:
            return code
    raise HTTPException(status_code=500, detail="Impossible de générer un code de parrainage")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, payload: UserRegister):
    existing = (
        supabase_admin.table("users")
        .select("id")
        .eq("email", payload.email)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

    referred_by_id = None
    if payload.referred_by_code:
        referrer = (
            supabase_admin.table("users")
            .select("id")
            .eq("referral_code", payload.referred_by_code)
            .execute()
        )
        if referrer.data:
            referred_by_id = referrer.data[0]["id"]

    new_user = {
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name,
        "referral_code": _unique_referral_code(),
        "referred_by": referred_by_id,
    }

    result = supabase_admin.table("users").insert(new_user).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erreur lors de la création du compte")

    user = result.data[0]
    return UserOut(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        referral_code=user["referral_code"],
    )


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, payload: UserLogin):
    result = (
        supabase_admin.table("users")
        .select("*")
        .eq("email", payload.email)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    user = result.data[0]

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Compte désactivé")

    token = create_access_token({"sub": user["id"]})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
@limiter.limit("30/minute")
async def get_me(request: Request, user_id: str = Depends(get_current_user_id)):
    result = (
        supabase_admin.table("users")
        .select("*")
        .eq("id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user = result.data[0]
    return UserOut(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        referral_code=user["referral_code"],
    )


@router.get("/solde")
@limiter.limit("30/minute")
async def get_solde(request: Request, user_id: str = Depends(get_current_user_id)):
    result = (
        supabase_admin.table("transactions")
        .select("commission")
        .eq("referrer_id", user_id)
        .execute()
    )
    total = sum(row["commission"] for row in result.data)
    return {"solde": total, "nombre_ventes": len(result.data)}
