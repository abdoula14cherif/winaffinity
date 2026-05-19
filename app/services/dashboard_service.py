"""
win_affinity/app/services/dashboard_service.py
───────────────────────────────────────────────
Logique métier du dashboard :
  - Statistiques globales de l'utilisateur
  - Liste des filleuls avec statuts
  - Historique des gains / transactions
  - Calcul des commissions (en FCFA)
"""

import logging
from typing import Optional

from supabase import Client

logger = logging.getLogger(__name__)

# ── Taux de commission par niveau ─────────────────────────────────────────────
COMMISSION_RATES = {
    1: 0.30,   # 30% sur les filleuls directs (niveau 1)
    2: 0.15,   # 15% sur les filleuls de mes filleuls (niveau 2)
    3: 0.05,   # 5%  niveau 3
}

ACTIVATION_AMOUNT_FCFA = 2500   # Prix d'activation en FCFA


async def get_dashboard_stats(db: Client, user_id: str) -> dict:
    """
    Retourne toutes les statistiques pour le dashboard d'un utilisateur.
    Structure retournée :
      - user            : données profil
      - stats           : chiffres clés (solde, filleuls, gains)
      - referrals       : liste des filleuls directs
      - transactions    : historique des paiements
    """

    # ── 1. Données utilisateur ────────────────────────────────────────────────
    try:
        user_res = db.table("users").select("*").eq("id", user_id).execute()
        if not user_res.data:
            raise ValueError("Utilisateur introuvable.")
        user = user_res.data[0]
    except ValueError:
        raise
    except Exception as e:
        logger.error("[DASHBOARD] Erreur récupération user %s : %s", user_id, e)
        raise RuntimeError("Impossible de charger le profil.") from e

    # ── 2. Filleuls directs (niveau 1) ────────────────────────────────────────
    try:
        ref_res = (
            db.table("users")
            .select("id, full_name, email, is_active, created_at, referral_count")
            .eq("sponsor_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        referrals = ref_res.data or []
    except Exception as e:
        logger.error("[DASHBOARD] Erreur récupération filleuls : %s", e)
        referrals = []

    # ── 3. Calcul des gains ────────────────────────────────────────────────────
    active_referrals   = [r for r in referrals if r.get("is_active")]
    inactive_referrals = [r for r in referrals if not r.get("is_active")]

    # Gain niveau 1 : 30% × 2500 FCFA × nombre de filleuls actifs
    gain_n1 = len(active_referrals) * ACTIVATION_AMOUNT_FCFA * COMMISSION_RATES[1]

    # ── 4. Transactions de paiement (historique) ───────────────────────────────
    try:
        pay_res = (
            db.table("payments")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        transactions = pay_res.data or []
    except Exception as e:
        logger.error("[DASHBOARD] Erreur récupération paiements : %s", e)
        transactions = []

    # ── 5. Solde total (somme des commissions) ────────────────────────────────
    # En production, ce champ viendrait d'une table "wallets" dédiée.
    # Pour la Phase 3, on le calcule dynamiquement depuis les filleuls actifs.
    total_balance_fcfa = int(gain_n1)

    # ── 6. Construction du lien de parrainage ─────────────────────────────────
    referral_link = f"https://winaffinity.com/auth/register?ref={user['referral_code']}"

    # ── 7. Assemblage final ────────────────────────────────────────────────────
    stats = {
        "total_balance_fcfa"  : total_balance_fcfa,
        "total_referrals"     : len(referrals),
        "active_referrals"    : len(active_referrals),
        "inactive_referrals"  : len(inactive_referrals),
        "gain_n1_fcfa"        : int(gain_n1),
        "referral_link"       : referral_link,
        "commission_rate_n1"  : int(COMMISSION_RATES[1] * 100),
    }

    return {
        "user"        : user,
        "stats"       : stats,
        "referrals"   : referrals,
        "transactions": transactions,
    }


async def get_user_referral_tree(db: Client, user_id: str, depth: int = 2) -> list:
    """
    Construit l'arbre de parrainage jusqu'à `depth` niveaux.
    Utilisé pour l'affichage du réseau dans le dashboard.
    """
    tree = []
    try:
        # Niveau 1
        lvl1_res = (
            db.table("users")
            .select("id, full_name, is_active, referral_count, created_at")
            .eq("sponsor_id", user_id)
            .execute()
        )
        lvl1 = lvl1_res.data or []

        for member in lvl1:
            node = {**member, "level": 1, "children": []}

            if depth >= 2:
                # Niveau 2
                lvl2_res = (
                    db.table("users")
                    .select("id, full_name, is_active, created_at")
                    .eq("sponsor_id", member["id"])
                    .execute()
                )
                lvl2 = lvl2_res.data or []
                node["children"] = [{**m, "level": 2} for m in lvl2]

            tree.append(node)
    except Exception as e:
        logger.error("[DASHBOARD] Erreur arbre parrainage : %s", e)

    return tree
