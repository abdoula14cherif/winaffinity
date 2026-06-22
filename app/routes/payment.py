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


# ── Helper : récupérer l'utilisateur depuis le cookie JWT ────────────────────

async def get_current_user_from_cookie(request: Request) -> dict | None:
    """
    Extrait et valide le JWT depuis le cookie HTTP-only.
    Retourne le dict utilisateur ou None.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    db = get_supabase()
    return await get_user_by_id(db, payload["sub"])


# ── Page de paiement ─────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse, name="payment_page")
async def get_payment(request: Request):
    """
    Affiche la page d'activation.
    Redirige vers /auth/login si non connecté.
    Redirige vers /dashboard si déjà actif.
    """
    user = await get_current_user_from_cookie(request)

    if not user:
        # Non connecté → retour au login
        return RedirectResponse("/auth/login", status_code=302)

    if user.get("is_active"):
        # Déjà activé → dashboard directement
        return RedirectResponse("/dashboard", status_code=302)

    # Montant en dollars (converti depuis XOF pour l'affichage)
    # 1 USD ≈ 600 XOF (taux approximatif)
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


# ── Confirmation JS (appelé par LeekPay.checkout onSuccess) ──────────────────

@router.post("/confirm", name="payment_confirm")
async def confirm_payment(request: Request, body: PaymentConfirmRequest):
    """
    Endpoint appelé par le frontend après le callback onSuccess de LeekPay.
    Double-vérification côté serveur du statut du paiement.
    Active le compte si paiement confirmé.
    """
    user = await get_current_user_from_cookie(request)
    if not user:
        return JSONResponse({"success": False, "error": "Non authentifié."}, status_code=401)

    db = get_supabase()

    # 1. Double-vérification du statut via l'API LeekPay (ne jamais faire
    #    confiance uniquement au client JS)
    payment_data = await verify_payment_status(body.payment_id)

    if not payment_data:
        logger.warning("[PAYMENT] Impossible de vérifier %s", body.payment_id)
        return JSONResponse({"success": False, "error": "Vérification du paiement impossible."}, status_code=400)

    real_status = payment_data.get("status", "unknown")

    # 2. Enregistrement en base (upsert)
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
        # Non bloquant : on continue même si l'enregistrement échoue

    # 3. Activation du compte si statut = completed
    if real_status == "completed":
        activated = await activate_user_account(db, user["id"])
        from app.services.commission_service import process_commissions
        await process_commissions(db, user["id"])
        if activated:
            return JSONResponse({"success": True, "redirect": "/dashboard"})
        return JSONResponse({"success": False, "error": "Activation impossible."}, status_code=500)

    # Paiement non complété (pending, failed, etc.)
    logger.warning("[PAYMENT] Statut non-completed pour %s : %s", body.payment_id, real_status)
    return JSONResponse(
        {"success": False, "error": f"Statut du paiement : {real_status}."},
        status_code=400,
    )


# ── Webhook LeekPay ────────────────────────────────────────────────────────

@router.post("/webhook", name="payment_webhook")
async def leekpay_webhook(request: Request):
    """
    Reçoit les notifications asynchrones de LeekPay.
    Vérifie la signature HMAC avant tout traitement.
    Répond 200 rapidement (LeekPay retentera si ≠ 200).
    """
    # 1. Lire le corps brut AVANT parsing (nécessaire pour la vérification HMAC)
    raw_body = await request.body()

    # 2. Vérification de la signature HMAC
    signature = request.headers.get("X-LeekPay-Signature", "")
    if not verify_webhook_signature(raw_body, signature):
        logger.warning("[WEBHOOK] Signature invalide – requête rejetée")
        return JSONResponse({"error": "Invalid signature"}, status_code=401)

    # 3. Parsing du payload
    try:
        payload_dict = json.loads(raw_body)
        payload = LeekPayWebhookPayload(**payload_dict)
    except Exception as e:
        logger.error("[WEBHOOK] Payload invalide : %s", e)
        return JSONResponse({"error": "Invalid payload"}, status_code=400)

    logger.info("[WEBHOOK] Événement reçu : %s – transaction %s",
                payload.event, payload.transaction.id)

    # 4. Traitement selon le type d'événement
    if payload.event == "payment.success" and payload.transaction.status == "completed":
        db = get_supabase()

        # Retrouver l'utilisateur via son email (LeekPay nous envoie l'email du client)
        try:
            result = (
                db.table("users")
                .select("id")
                .eq("email", payload.transaction.customer_email.lower())
                .execute()
            )
            if not result.data:
                logger.warning("[WEBHOOK] Utilisateur introuvable pour email %s",
                               payload.transaction.customer_email)
                return JSONResponse({"status": "user_not_found"}, status_code=200)

            user_id = result.data[0]["id"]

            # Enregistrement du paiement
            await record_payment(
                db,
                user_id=user_id,
                payment_id=str(payload.transaction.id),
                amount=payload.transaction.amount,
                currency=payload.transaction.currency,
                status="completed",
            )

            # Déterminer le niveau selon le montant
            amount_paid = payload.transaction.amount
            if amount_paid <= 1000:
                level = "starter"
            elif amount_paid <= 2500:
                level = "standard"
            else:
                level = "premium"

            # Sauvegarder le niveau
            db.table("users").update({
                "level": level,
                "activation_amount": amount_paid
            }).eq("id", user_id).execute()

            # Activation du compte
            await activate_user_account(db, user_id)

            # Distribuer les commissions
            try:
                from app.services.commission_service import process_commissions
                await process_commissions(db, user_id)
            except Exception as ce:
                logger.error("[WEBHOOK] Erreur commissions : %s", ce)

            # Notification push à l utilisateur
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

            # Email de confirmation activation
            try:
                user_data = db.table("users").select("email,full_name,referral_code").eq("id", user_id).execute().data
                if user_data:
                    u = user_data[0]
                    from app.services.email_service import send_activation_email
                    await send_activation_email(u["email"], u["full_name"], level, u.get("referral_code",""))
            except Exception as ee:
                logger.error("[WEBHOOK] Erreur email activation : %s", ee)

        except Exception as e:
            logger.error("[WEBHOOK] Erreur traitement webhook : %s", e)
            # On répond 200 quand même pour éviter les re-tentatives en boucle
            return JSONResponse({"status": "error_logged"}, status_code=200)

    # LeekPay attend un 200 pour confirmer la réception
    return JSONResponse({"status": "ok"}, status_code=200)


# ── Page de succès (return_url LeekPay) ──────────────────────────────────────

@router.get("/success", response_class=HTMLResponse, name="payment_success")
async def payment_success(request: Request):
    """
    Page de retour après paiement via l'API REST LeekPay (return_url).
    Le webhook aura déjà activé le compte ; on redirige vers dashboard.
    """
    user = await get_current_user_from_cookie(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=302)
    if user.get("is_active"):
        return RedirectResponse("/dashboard", status_code=302)
    # Compte pas encore activé (webhook peut être en retard)
    return RedirectResponse("/payment?pending=1", status_code=302)
