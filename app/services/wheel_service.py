"""
Roue de la chance
1 tour gratuit par jour
Probabilités : perdre plus que gagner
"""
import random
import logging
from datetime import datetime, timezone
from supabase import Client

logger = logging.getLogger(__name__)

# Segments : (montant, probabilité, label, couleur)
SEGMENTS = [
    (0,   35, "Perdu",    "#E05A5A"),
    (0,   25, "Perdu",    "#C04040"),
    (50,  15, "+50 FCFA", "#C9A84C"),
    (0,   10, "Perdu",    "#E05A5A"),
    (100,  7, "+100 FCFA","#4CAF7E"),
    (25,   5, "+25 FCFA", "#E09050"),
    (0,    2, "Perdu",    "#C04040"),
    (200,  1, "+200 FCFA","#E8C96A"),
]

def spin_wheel() -> dict:
    """Tire aléatoirement un segment selon les probabilités."""
    total = sum(s[1] for s in SEGMENTS)
    r = random.randint(1, total)
    cumul = 0
    for i, (amount, prob, label, color) in enumerate(SEGMENTS):
        cumul += prob
        if r <= cumul:
            return {"segment": i, "amount": amount, "label": label, "color": color}
    return {"segment": 0, "amount": 0, "label": "Perdu", "color": "#E05A5A"}

async def can_spin(db: Client, user_id: str) -> bool:
    """Vérifie si l'utilisateur peut tourner aujourd'hui."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        res = db.table("wheel_spins").select("id").eq("user_id", user_id).gte("spun_at", today).execute()
        return len(res.data or []) == 0
    except Exception as e:
        logger.error("[WHEEL] Erreur can_spin : %s", e)
        return False

async def do_spin(db: Client, user_id: str) -> dict:
    """Effectue un tour de roue."""
    if not await can_spin(db, user_id):
        raise ValueError("Vous avez déjà tourné la roue aujourd'hui. Revenez demain !")

    result = spin_wheel()

    # Enregistrer le spin
    db.table("wheel_spins").insert({
        "user_id": user_id,
        "reward": result["amount"],
    }).execute()

    # Créditer si gain
    if result["amount"] > 0:
        wallet = db.table("wallets").select("*").eq("user_id", user_id).execute().data
        if wallet:
            w = wallet[0]
            db.table("wallets").update({
                "balance": w["balance"] + result["amount"],
                "total_earned": w["total_earned"] + result["amount"],
            }).eq("user_id", user_id).execute()
        else:
            db.table("wallets").insert({
                "user_id": user_id,
                "balance": result["amount"],
                "total_earned": result["amount"],
            }).execute()

        # Notification
        from app.services.notification_service import send_notification
        await send_notification(
            db, user_id,
            f"🎡 Roue : +{result['amount']} FCFA !",
            f"Vous avez gagné {result['amount']} FCFA à la roue de la chance !",
            "success"
        )

    logger.info("[WHEEL] User %s → %s FCFA", user_id, result["amount"])
    return result

async def get_spin_history(db: Client, user_id: str) -> list:
    try:
        res = db.table("wheel_spins").select("*").eq("user_id", user_id).order("spun_at", desc=True).limit(10).execute()
        return res.data or []
    except:
        return []
