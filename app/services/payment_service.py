"""
win_affinity/app/services/payment_service.py
─────────────────────────────────────────────
Service de paiement LeekPay :
  - Création d'un checkout via API REST (serveur → LeekPay)
  - Vérification de la signature HMAC des webhooks
  - Activation du compte utilisateur après paiement confirmé
  - Vérification du statut d'un paiement
"""

import hashlib
import hmac
import logging
from typing import Optional

import httpx
from supabase import Client

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# ── Création d'un checkout REST (option serveur) ──────────────────────────────

async def create_checkout(
    user_id: str,
    user_email: str,
    user_name: str,
) -> dict:
    """
    Crée un lien de paiement LeekPay via l'API REST.
    Utilisé comme fallback ou pour les intégrations sans JS.

    Retourne : { payment_url, payment_id, status, amount, currency }
    Raises   : RuntimeError si la requête échoue.
    """
    if not settings.leekpay_secret_key:
        # En développement sans clé secrète, on retourne un mock
        logger.warning("[PAYMENT] LEEKPAY_SECRET_KEY absent – mode mock activé")
        return {
            "payment_url": f"/payment/mock?user={user_id}",
            "payment_id": f"mock_{user_id[:8]}",
            "status": "pending",
            "amount": settings.activation_amount,
            "currency": settings.activation_currency,
        }

    payload = {
        "amount": settings.activation_amount,
        "currency": settings.activation_currency,
        "description": f"Activation compte WIN AFFINITY – {user_name}",
        "return_url": f"{settings.base_url}/payment/success",
        "customer_email": user_email,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.leekpay_api_url}/checkout",
                headers={
                    "Authorization": f"Bearer {settings.leekpay_secret_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error("[PAYMENT] Erreur HTTP LeekPay : %s – %s", e.response.status_code, e.response.text)
        raise RuntimeError(f"Erreur LeekPay ({e.response.status_code}). Veuillez réessayer.") from e
    except httpx.RequestError as e:
        logger.error("[PAYMENT] Erreur réseau LeekPay : %s", e)
        raise RuntimeError("Service de paiement temporairement indisponible.") from e

    if not data.get("success"):
        logger.error("[PAYMENT] Réponse inattendue LeekPay : %s", data)
        raise RuntimeError("Impossible de créer le lien de paiement.")

    return data["data"]


# ── Vérification du statut d'un paiement ─────────────────────────────────────

async def verify_payment_status(payment_id: str) -> Optional[dict]:
    """
    Interroge LeekPay pour vérifier le statut d'un paiement.
    Retourne les données du paiement ou None en cas d'erreur.
    """
    if not settings.leekpay_secret_key:
        logger.warning("[PAYMENT] LEEKPAY_SECRET_KEY absent – statut mock")
        return {"status": "completed", "payment_id": payment_id}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.leekpay_api_url}/checkout/{payment_id}",
                headers={"Authorization": f"Bearer {settings.leekpay_secret_key}"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data")
    except Exception as e:
        logger.error("[PAYMENT] Erreur vérification statut %s : %s", payment_id, e)
        return None


# ── Vérification de la signature webhook ─────────────────────────────────────

def verify_webhook_signature(payload_bytes: bytes, signature: str) -> bool:
    """
    Vérifie la signature HMAC-SHA256 envoyée par LeekPay dans
    l'en-tête X-LeekPay-Signature.

    LeekPay signe le payload JSON brut avec la clé PUBLIQUE.
    Utilise hmac.compare_digest pour éviter les timing attacks.

    Retourne True si valide, False sinon.
    """
    if not signature:
        logger.warning("[WEBHOOK] Signature absente")
        return False

    try:
        expected = hmac.new(
            settings.leekpay_public_key.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        # compare_digest : comparaison en temps constant (anti timing-attack)
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error("[WEBHOOK] Erreur vérification signature : %s", e)
        return False


# ── Enregistrement du paiement en base ───────────────────────────────────────

async def record_payment(
    db: Client,
    user_id: str,
    payment_id: str,
    amount: int,
    currency: str,
    status: str = "pending",
) -> dict:
    """
    Insère ou met à jour un enregistrement de paiement dans Supabase.
    Utilise un upsert sur payment_id pour éviter les doublons.
    """
    payload = {
        "user_id": user_id,
        "payment_id": payment_id,
        "amount": amount,
        "currency": currency,
        "status": status,
    }

    try:
        # Upsert : crée ou met à jour selon payment_id
        result = (
            db.table("payments")
            .upsert(payload, on_conflict="payment_id")
            .execute()
        )
        if not result.data:
            raise RuntimeError("Upsert paiement sans retour de données.")
        return result.data[0]
    except RuntimeError:
        raise
    except Exception as e:
        logger.error("[PAYMENT] Erreur enregistrement paiement : %s", e)
        raise RuntimeError("Impossible d'enregistrer le paiement.") from e


# ── Activation du compte utilisateur ─────────────────────────────────────────

async def activate_user_account(db: Client, user_id: str) -> bool:
    """
    Passe is_active=True pour l'utilisateur indiqué.
    Appelé après confirmation du paiement (webhook ou onSuccess JS).

    Retourne True si succès, False sinon.
    """
    try:
        result = (
            db.table("users")
            .update({"is_active": True})
            .eq("id", user_id)
            .execute()
        )
        if result.data:
            logger.info("[PAYMENT] Compte activé : %s", user_id)
            return True
        logger.warning("[PAYMENT] Aucune ligne mise à jour pour user %s", user_id)
        return False
    except Exception as e:
        logger.error("[PAYMENT] Erreur activation compte %s : %s", user_id, e)
        return False


# ── Récupère le paiement en attente d'un utilisateur ─────────────────────────

async def get_pending_payment(db: Client, user_id: str) -> Optional[dict]:
    """
    Retourne le dernier paiement pending pour un utilisateur,
    ou None s'il n'en existe pas.
    """
    try:
        result = (
            db.table("payments")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("[PAYMENT] Erreur récupération paiement pending : %s", e)
        return None
