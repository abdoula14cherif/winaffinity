"""
win_affinity/app/models/user.py
───────────────────────────────
Schémas Pydantic pour la validation des données utilisateur.
Séparation stricte entrée / sortie pour ne jamais exposer le hash.
"""

import re
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Schémas d'entrée (formulaires) ───────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Données reçues lors de l'inscription."""

    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=8, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    password_confirm: str = Field(..., min_length=8, max_length=72)
    referral_code: Optional[str] = Field(None, max_length=20)

    @field_validator("full_name")
    @classmethod
    def name_no_special_chars(cls, v: str) -> str:
        """Autorise lettres, espaces, tirets et apostrophes uniquement."""
        if not re.match(r"^[\w\s\-'àâäéèêëîïôöùûüç]+$", v, re.UNICODE):
            raise ValueError("Le nom contient des caractères non autorisés.")
        return v.strip()

    @field_validator("phone")
    @classmethod
    def phone_digits_only(cls, v: str) -> str:
        """Accepte +, chiffres, espaces, tirets."""
        cleaned = re.sub(r"[\s\-]", "", v)
        if not re.match(r"^\+?\d{8,15}$", cleaned):
            raise ValueError("Numéro de téléphone invalide.")
        return cleaned

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.password_confirm:
            raise ValueError("Les mots de passe ne correspondent pas.")
        return self


class LoginRequest(BaseModel):
    """Données reçues lors de la connexion."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)


# ── Schémas de sortie (réponses API) ─────────────────────────────────────────

class UserPublic(BaseModel):
    """Représentation publique d'un utilisateur (jamais le mot de passe)."""

    id: str
    full_name: str
    email: str
    phone: str
    referral_code: str
    is_active: bool
    created_at: str


class AuthResponse(BaseModel):
    """Réponse après connexion réussie."""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic
