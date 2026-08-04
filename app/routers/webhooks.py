import hmac
import hashlib
import json

from fastapi import APIRouter, Request, HTTPException, Header
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import supabase_admin
from app.config import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/leekpay")
@limiter.limit("60/minute")
async def leekpay_webhook(request: Request, x_leekpay_signature: str = Header(None)):
    raw_body = await request.body()

    expected_signature = hmac.new(
        settings.leekpay_public_key.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not x_leekpay_signature or not hmac.compare_digest(expected_signature, x_leekpay_signature):
        raise HTTPException(status_code=401, detail="Signature invalide")

    payload = json.loads(raw_body)
    event = payload.get("event")
    data = payload.get("data", {})
    checkout_id = data.get("checkout_id")
    status = data.get("status")

    if not checkout_id:
        raise HTTPException(status_code=400, detail="checkout_id manquant")

    transaction_result = supabase_admin.table("transactions").select("*").eq("checkout_id", checkout_id).execute()
    if not transaction_result.data:
        return {"ok": True, "note": "Transaction inconnue, ignorée"}

    transaction = transaction_result.data[0]

    if transaction["statut"] == "paid":
        return {"ok": True, "note": "Déjà traité"}

    if event == "payment.completed" and status == "paid":
        supabase_admin.table("transactions").update({
            "statut": "paid",
            "paid_at": data.get("paid_at"),
        }).eq("checkout_id", checkout_id).execute()
    elif event in ("payment.failed", "payment.cancelled"):
        supabase_admin.table("transactions").update({"statut": status}).eq("checkout_id", checkout_id).execute()

    return {"ok": True}
