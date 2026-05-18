"""
win_affinity/app/database.py
────────────────────────────
Client Supabase singleton.
Toutes les interactions avec la base de données passent par ce module.
"""

from functools import lru_cache
from supabase import create_client, Client
from app.config import get_settings

settings = get_settings()


@lru_cache()
def get_supabase() -> Client:
    """
    Retourne le client Supabase (singleton mis en cache).
    Lève une erreur si les credentials sont invalides.
    """
    try:
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        return client
    except Exception as e:
        # Erreur critique au démarrage – on la propage clairement
        raise RuntimeError(
            f"[DATABASE] Impossible de se connecter à Supabase : {e}"
        ) from e
