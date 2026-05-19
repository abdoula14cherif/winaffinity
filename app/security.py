"""
win_affinity/app/security.py
────────────────────────────
Utilitaires de sécurité centralisés :
  - Hachage bcrypt des mots de passe (avec pepper)
  - Génération / vérification des tokens JWT (access + refresh)
  - Validation robuste du mot de passe (force requise)
  - Génération de codes de parrainage uniques
  - Protection CSRF via itsdangerous
"""

import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.config import get_settings

settings = get_settings()

# ── Hachage ──────────────────────────────────────────────────────────────────

# bcrypt avec un coût de 12 (bon équilibre sécurité / performance)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pepper statique : ajoute une couche de sécurité côté application
# (même si la DB est compromise, les hashes restent inutilisables sans le pepper)
_PEPPER = settings.secret_key[:32]  # 32 premiers caractères du secret global


def hash_password(plain: str) -> str:
    """
    Hache le mot de passe avec bcrypt + pepper.
    Le pepper est concaténé AVANT le hachage.
    """
    peppered = (plain + _PEPPER)[:72]
    return _pwd_context.hash(peppered)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Vérifie un mot de passe en clair contre son hash bcrypt + pepper.
    Retourne False silencieusement en cas d'échec (pas d'exception).
    """
    try:
        peppered = (plain + _PEPPER)[:72]
        return _pwd_context.verify(peppered, hashed)
    except Exception:
        # Ne jamais faire fuiter d'informations sur la raison de l'échec
        return False


# ── Validation du mot de passe ────────────────────────────────────────────────

_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()\-_=+{};:,<.>]).{8,72}$"
)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Valide la force du mot de passe.
    Retourne (True, "") si valide, (False, "message d'erreur") sinon.

    Règles :
      - 8 à 72 caractères (limite bcrypt)
      - Au moins 1 minuscule, 1 majuscule, 1 chiffre, 1 caractère spécial
    """
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères."
    if len(password) > 72:
        return False, "Le mot de passe ne peut pas dépasser 72 caractères."
    if not _PASSWORD_PATTERN.match(password):
        return (
            False,
            "Le mot de passe doit contenir au moins : "
            "1 majuscule, 1 minuscule, 1 chiffre, 1 caractère spécial (!@#$%…).",
        )
    return True, ""


# ── JWT ───────────────────────────────────────────────────────────────────────

def _create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    """
    Crée un JWT signé avec HS256.
    Ajoute automatiquement : exp, iat, type.
    """
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, email: str) -> str:
    """Génère un access token JWT (courte durée)."""
    return _create_token(
        {"sub": user_id, "email": email},
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(user_id: str) -> str:
    """Génère un refresh token JWT (longue durée)."""
    return _create_token(
        {"sub": user_id},
        timedelta(days=settings.refresh_token_expire_days),
        "refresh",
    )


def decode_access_token(token: str) -> Optional[dict]:
    """
    Décode et valide un access token.
    Retourne le payload ou None si invalide / expiré.
    Ne lève jamais d'exception vers l'appelant.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        # Vérification du type de token
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        # Token invalide, expiré ou falsifié
        return None


def decode_refresh_token(token: str) -> Optional[str]:
    """
    Décode un refresh token et retourne le user_id ou None.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ── Code de parrainage ────────────────────────────────────────────────────────

_REFERRAL_ALPHABET = string.ascii_uppercase + string.digits


def generate_referral_code(length: int = 8) -> str:
    """
    Génère un code de parrainage aléatoire cryptographiquement sûr.
    Format : 8 caractères alphanumériques majuscules (ex: A3BX7KQ2).
    """
    return "".join(secrets.choice(_REFERRAL_ALPHABET) for _ in range(length))


# ── CSRF ─────────────────────────────────────────────────────────────────────

_csrf_serializer = URLSafeTimedSerializer(settings.secret_key, salt="csrf-token")


def generate_csrf_token(session_id: str) -> str:
    """Génère un token CSRF lié à la session."""
    return _csrf_serializer.dumps(session_id)


def verify_csrf_token(token: str, session_id: str, max_age: int = 3600) -> bool:
    """
    Vérifie le token CSRF.
    Retourne False si invalide, expiré ou si la session ne correspond pas.
    """
    try:
        value = _csrf_serializer.loads(token, max_age=max_age)
        return value == session_id
    except (BadSignature, SignatureExpired):
        return False


# ── Nettoyage des entrées ─────────────────────────────────────────────────────

def sanitize_input(value: str, max_length: int = 255) -> str:
    """
    Nettoie une chaîne :
      - Supprime les espaces en début / fin
      - Tronque à max_length
      - Supprime les caractères de contrôle
    """
    cleaned = value.strip()[:max_length]
    # Supprimer les caractères de contrôle (sauf espace = 0x20)
    return "".join(c for c in cleaned if ord(c) >= 0x20 or c == "\n")
