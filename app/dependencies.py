from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.security import decode_access_token

bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )
    return payload["sub"]


async def get_current_admin_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    from app.database import supabase_admin

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")

    user_id = payload["sub"]
    result = supabase_admin.table("users").select("is_admin").eq("id", user_id).execute()
    if not result.data or not result.data[0].get("is_admin"):
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")

    return user_id
