"""
win_affinity/app/config.py
──────────────────────────
Configuration centralisée chargée depuis .env via pydantic-settings.
Toute valeur manquante lève une erreur claire au démarrage (fail-fast).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Paramètres de l'application.
    Les champs sans valeur par défaut sont OBLIGATOIRES dans .env.
    """

    # ── Application ──────────────────────────────────────────────────
    app_name: str = "WIN AFFINITY"
    app_env: str = "development"
    secret_key: str                      # OBLIGATOIRE – utilisé pour les cookies signés
    debug: bool = False

    # ── Supabase ─────────────────────────────────────────────────────
    supabase_url: str                    # OBLIGATOIRE
    supabase_anon_key: str               # OBLIGATOIRE

    # ── JWT ──────────────────────────────────────────────────────────
    jwt_secret_key: str                  # OBLIGATOIRE – différent de secret_key
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # ── LeekPay ──────────────────────────────────────────────────────
    leekpay_public_key: str              # OBLIGATOIRE
    leekpay_secret_key: str = ""         # Optionnel en dev, obligatoire en prod
    leekpay_api_url: str = "https://leekpay.fr/api/v1"
    activation_amount: int = 2500        # en XOF
    activation_currency: str = "XOF"

    # ── URLs ─────────────────────────────────────────────────────────
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8000"

    # ── Rate Limiting ─────────────────────────────────────────────────
    rate_limit_login: str = "5/minute"   # 5 tentatives / minute max
    rate_limit_register: str = "3/minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cookie_secure(self) -> bool:
        """Cookies HTTPS-only uniquement en production."""
        return self.is_production


@lru_cache()
def get_settings() -> Settings:
    """
    Singleton mis en cache – instancié une seule fois.
    Lève ValidationError si des variables obligatoires sont absentes.
    """
    return Settings()
