"""
win_affinity/app/models/payment.py
──────────────────────────────────
Schémas Pydantic pour les paiements LeekPay.
"""

from typing import Optional
from pydantic import BaseModel


class PaymentCreateRequest(BaseModel):
    """Demande de création de checkout côté serveur (optionnel)."""
    user_id: str
    amount: int          # en XOF
    currency: str = "XOF"
    description: str = "Activation compte WIN AFFINITY"


class LeekPayWebhookTransaction(BaseModel):
    """Objet transaction dans le webhook LeekPay."""
    id: int
    amount: int
    currency: str
    status: str
    customer_email: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None


class LeekPayWebhookPayload(BaseModel):
    """Payload complet envoyé par LeekPay sur notre webhook."""
    event: str                             # "payment.success"
    transaction: LeekPayWebhookTransaction


class PaymentConfirmRequest(BaseModel):
    """
    Payload envoyé par le JS LeekPay.checkout onSuccess
    pour confirmer le paiement côté serveur.
    """
    payment_id: str
    amount: int
    currency: str
    status: str
