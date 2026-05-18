"""
win_affinity/app/main.py
────────────────────────
Point d'entrée FastAPI.
Configure : middlewares, rate limiting, CORS, routes, gestion d'erreurs.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.routes import auth, payment  # dashboard Phase 3

settings = get_settings()
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 WIN AFFINITY démarré en mode %s", settings.app_env)
    yield
    logger.info("🛑 WIN AFFINITY arrêté.")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── Middlewares ───────────────────────────────────────────────────────────────

# Hôtes de confiance (protection contre les attaques Host header)
if settings.is_production:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["winaffinity.com", "*.winaffinity.com"])

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Rate limiting global
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Fichiers statiques ────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(payment.router)
# app.include_router(payment.router)   # À activer en phase 2
# app.include_router(dashboard.router) # À activer en phase 3


# ── Page d'accueil → redirection vers inscription ─────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/auth/register")


# ── Gestionnaire d'erreurs global ─────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Page introuvable."},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.exception("[GLOBAL] Erreur interne : %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Erreur interne du serveur."},
    )
