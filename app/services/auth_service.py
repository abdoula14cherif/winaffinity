"""
win_affinity/app/services/auth_service.py
─────────────────────────────────────────
Logique métier de l'authentification :
  - Inscription avec vérification de l'email/téléphone uniques
  - Connexion avec protection contre le timing attack
  - Vérification du code de parrainage
"""

import logging
from typing import Optional

from supabase import Client

from app.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    generate_referral_code,
    sanitize_input,
)
from app.models.user import RegisterRequest, LoginRequest

logger = logging.getLogger(__name__)


# ── Inscription ───────────────────────────────────────────────────────────────

async def register_user(db: Client, data: RegisterRequest) -> dict:
    """
    Crée un nouveau compte utilisateur.

    Étapes :
      1. Valide la force du mot de passe
      2. Vérifie l'unicité de l'email
      3. Vérifie l'unicité du téléphone
      4. Valide le code de parrainage (si fourni)
      5. Hache le mot de passe
      6. Insère en base
      7. Incrémente le compteur de filleuls du parrain (si applicable)

    Raises:
      ValueError  – données invalides ou conflit
      RuntimeError – erreur base de données
    """

    # 1. Validation de la force du mot de passe (côté serveur – ne jamais faire
    #    confiance uniquement au frontend)
    is_strong, msg = validate_password_strength(data.password)
    if not is_strong:
        raise ValueError(msg)

    # Nettoyage des entrées
    full_name = sanitize_input(data.full_name)
    phone = sanitize_input(data.phone)

    # 2. Unicité de l'email
    try:
        existing_email = (
            db.table("users")
            .select("id")
            .eq("email", data.email.lower())
            .execute()
        )
        if existing_email.data:
            raise ValueError("Cette adresse e-mail est déjà utilisée.")
    except ValueError:
        raise
    except Exception as e:
        logger.error("[AUTH] Erreur vérification email : %s", e)
        raise RuntimeError("Erreur lors de la vérification de l'email.") from e

    # 3. Unicité du téléphone
    try:
        existing_phone = (
            db.table("users")
            .select("id")
            .eq("phone", phone)
            .execute()
        )
        if existing_phone.data:
            raise ValueError("Ce numéro de téléphone est déjà utilisé.")
    except ValueError:
        raise
    except Exception as e:
        logger.error("[AUTH] Erreur vérification téléphone : %s", e)
        raise RuntimeError("Erreur lors de la vérification du téléphone.") from e

    # 4. Validation du code de parrainage (facultatif)
    sponsor_id: Optional[str] = None
    if data.referral_code:
        ref_code = sanitize_input(data.referral_code, max_length=20).upper()
        try:
            sponsor_result = (
                db.table("users")
                .select("id")
                .eq("referral_code", ref_code)
                .execute()
            )
            if not sponsor_result.data:
                raise ValueError("Code de parrainage invalide ou inexistant.")
            sponsor_id = sponsor_result.data[0]["id"]
        except ValueError:
            raise
        except Exception as e:
            logger.error("[AUTH] Erreur vérification parrainage : %s", e)
            raise RuntimeError("Erreur lors de la vérification du parrainage.") from e

    # 5. Hachage sécurisé du mot de passe
    hashed_pw = hash_password(data.password)

    # Génération d'un code de parrainage unique pour le nouvel utilisateur
    new_referral_code = await _generate_unique_referral_code(db)

    # 6. Insertion en base
    user_payload = {
        "full_name": full_name,
        "email": data.email.lower(),
        "phone": phone,
        "password_hash": hashed_pw,
        "referral_code": new_referral_code,
        "sponsor_id": sponsor_id,
        "is_active": False,        # Activé après paiement
        "is_verified": False,
        "role": "user",
    }

    try:
        result = db.table("users").insert(user_payload).execute()
        if not result.data:
            raise RuntimeError("L'insertion en base n'a retourné aucune donnée.")
        new_user = result.data[0]
    except RuntimeError:
        raise
    except Exception as e:
        logger.error("[AUTH] Erreur insertion utilisateur : %s", e)
        raise RuntimeError("Impossible de créer le compte. Veuillez réessayer.") from e

    # 7. Incrémentation du compteur de filleuls du parrain
    if sponsor_id:
        try:
            db.rpc("increment_referral_count", {"sponsor": sponsor_id}).execute()
        except Exception as e:
            # Non critique – on log sans bloquer l'inscription
            logger.warning("[AUTH] Impossible d'incrémenter le compteur parrain : %s", e)

    logger.info("[AUTH] Nouveau compte créé : %s", new_user["id"])
    return new_user


# ── Connexion ─────────────────────────────────────────────────────────────────

async def authenticate_user(db: Client, data: LoginRequest) -> Optional[dict]:
    """
    Authentifie un utilisateur.

    Retourne le dict utilisateur si valide, None sinon.
    La comparaison de timing est constante pour éviter les timing attacks :
    on calcule toujours verify_password même si l'utilisateur n'existe pas.
    """
    # Récupération de l'utilisateur
    try:
        result = (
            db.table("users")
            .select("*")
            .eq("email", data.email.lower())
            .execute()
        )
    except Exception as e:
        logger.error("[AUTH] Erreur récupération utilisateur : %s", e)
        return None

    if not result.data:
        # Utilisateur introuvable : on fait quand même un hash pour éviter
        # les timing attacks (un attaquant ne doit pas savoir si l'email existe)
        verify_password("Dummy@1234", "$2b$12$" + "x" * 53)
        return None

    user = result.data[0]

    # Vérification du mot de passe
    if not verify_password(data.password, user["password_hash"]):
        logger.warning("[AUTH] Tentative de connexion échouée pour : %s", data.email)
        return None

    logger.info("[AUTH] Connexion réussie : %s", user["id"])
    return user


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _generate_unique_referral_code(db: Client, max_attempts: int = 10) -> str:
    """
    Génère un code de parrainage garanti unique en base.
    Réessaie jusqu'à max_attempts fois en cas de collision.
    """
    for attempt in range(max_attempts):
        code = generate_referral_code()
        try:
            result = db.table("users").select("id").eq("referral_code", code).execute()
            if not result.data:
                return code
        except Exception as e:
            logger.warning("[AUTH] Erreur vérification unicité code (tentative %d) : %s", attempt + 1, e)

    # Cas extrêmement improbable : toutes les tentatives ont échoué
    raise RuntimeError("Impossible de générer un code de parrainage unique.")


async def get_user_by_id(db: Client, user_id: str) -> Optional[dict]:
    """Récupère un utilisateur par son ID."""
    try:
        result = db.table("users").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("[AUTH] Erreur récupération par ID : %s", e)
        return None
