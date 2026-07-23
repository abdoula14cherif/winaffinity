"""
win_affinity/app/routes/payment.py
────────────────────────────────────
Endpoints de paiement :
  GET  /payment          → Page d'activation (HTML)
  POST /payment/confirm  → Confirmation après LeekPay.checkout onSuccess
  POST /payment/webhook  → Webhook LeekPay (notification serveur)
  GET  /payment/success  → Page de succès après retour LeekPay
"""

import json
import logging

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import get_supabase
from app.models.payment import LeekPayWebhookPayload, PaymentConfirmRequest
from app.security import decode_access_token
from app.services.payment_service import (
    activate_user_account,
    get_pending_payment,
    record_payment,
    verify_webhook_signature,
    verify_payment_status,
)
from app.services.auth_service import get_user_by_id

router = APIRouter(prefix="/payment", tags=["Payment"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()
logger = logging.getLogger(__name__)


async def get_current_user_from_cookie(request: Request) -> dict | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    db = get_supabase()
    return await get_user_by_id(db, payload["sub"])


@router.get("", response_class=HTMLResponse, name="payment_page")
async def get_payment(request: Request):
    user = await get_current_user_from_cookie(request)

    if not user:
        return RedirectResponse("/auth/login", status_code=302)

    if user.get("is_active"):
        return RedirectResponse("/dashboard", status_code=302)

    amount_xof = settings.activation_amount

    return templates.TemplateResponse(
        "payment.html",
        {
            "request": request,
            "user": user,
            "amount_xof": amount_xof,
            "leekpay_public_key": settings.leekpay_public_key,
            "base_url": settings.base_url,
        },
    )


@router.post("/confirm", name="payment_confirm")
async def confirm_payment(request: Request, body: PaymentConfirmRequest):
    user = await get_current_user_from_cookie(request)
    if not user:
        return JSONResponse({"success": False, "error": "Non authentifié."}, status_code=401)

    db = get_supabase()

    payment_data = await verify_payment_status(body.payment_id)

    if not payment_data:
        logger.warning("[PAYMENT] Impossible de vérifier %s", body.payment_id)
        return JSONResponse({"success": False, "error": "Vérification du paiement impossible."}, status_code=400)

    real_status = payment_data.get("status", "unknown")

    try:
        await record_payment(
            db,
            user_id=user["id"],
            payment_id=body.payment_id,
            amount=body.amount,
            currency=body.currency,
            status=real_status,
        )
    except Exception as e:
        logger.error("[PAYMENT] Erreur enregistrement : %s", e)

    if real_status == "completed":
        activated = await activate_user_account(db, user["id"])
        from app.services.commission_service import process_commissions
        await process_commissions(db, user["id"])
        if activated:
            return JSONResponse({"success": True, "redirect": "/dashboard"})
        return JSONResponse({"success": False, "error": "Activation impossible."}, status_code=500)

    logger.warning("[PAYMENT] Statut non-completed pour %s : %s", body.payment_id, real_status)
    return JSONResponse(
        {"success": False, "error": f"Statut du paiement : {real_status}."},
        status_code=400,
    )


@router.post("/webhook", name="payment_webhook")
async def leekpay_webhook(request: Request):
    raw_body = await request.body()

    signature = request.headers.get("X-LeekPay-Signature", "")
    if not verify_webhook_signature(raw_body, signature):
        logger.warning("[WEBHOOK] Signature invalide – requête rejetée")
        return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        payload_dict = json.loads(raw_body)
        payload = LeekPayWebhookPayload(**payload_dict)
    except Exception as e:
        logger.error("[WEBHOOK] Payload invalide : %s", e)
        return JSONResponse({"error": "Invalid payload"}, status_code=400)

    logger.info("[WEBHOOK] Événement reçu : %s – transaction %s", payload.event, payload.transaction.id)

    if payload.event == "payment.success" and payload.transaction.status == "completed":
        db = get_supabase()

        try:
            result = (
                db.table("users")
                .select("id")
                .eq("email", payload.transaction.customer_email.lower())
                .execute()
            )
            if not result.data:
                logger.warning("[WEBHOOK] Utilisateur introuvable pour email %s", payload.transaction.customer_email)
                return JSONResponse({"status": "user_not_found"}, status_code=200)

            user_id = result.data[0]["id"]

            await record_payment(
                db,
                user_id=user_id,
                payment_id=str(payload.transaction.id),
                amount=payload.transaction.amount,
                currency=payload.transaction.currency,
                status="completed",
            )

            amount_paid = payload.transaction.amount
            if amount_paid <= 2500:
                level = "standard"
            else:
                level = "premium"

            db.table("users").update({
                "level": level,
                "activation_amount": amount_paid
            }).eq("id", user_id).execute()

            await activate_user_account(db, user_id)

            try:
                from app.services.commission_service import process_commissions
                await process_commissions(db, user_id)
            except Exception as ce:
                logger.error("[WEBHOOK] Erreur commissions : %s", ce)

            try:
                from app.services.push_service import send_push_to_user
                await send_push_to_user(
                    db, user_id,
                    "🎉 Compte activé !",
                    "Votre compte WIN AFFINITY est maintenant actif. Commencez à gagner !",
                    "/dashboard"
                )
            except Exception as pe:
                logger.error("[WEBHOOK] Erreur push : %s", pe)

            try:
                user_data = db.table("users").select("email,full_name,referral_code").eq("id", user_id).execute().data
                if user_data:
                    u = user_data[0]
                    from app.services.email_service import send_activation_email
                    await send_activation_email(u["email"], u["full_name"], level, u.get("referral_code", ""))
            except Exception as ee:
                logger.error("[WEBHOOK] Erreur email activation : %s", ee)

        except Exception as e:
            logger.error("[WEBHOOK] Erreur traitement webhook : %s", e)
            return JSONResponse({"status": "error_logged"}, status_code=200)

    return JSONResponse({"status": "ok"}, status_code=200)


@router.get("/success", response_class=HTMLResponse, name="payment_success")
async def payment_success(request: Request):
    user = await get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)
    if user.get("is_active"):
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/payment?pending=1", status_code=302)
