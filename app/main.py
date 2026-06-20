import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from app.config import get_settings
from app.middleware.maintenance import maintenance_middleware
from app.routes import auth, payment, dashboard, withdrawal, gains, pages, admin, notifications, wheel, network, learning, admin_user, contest, support, push, password_reset, wallet

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WIN AFFINITY démarré")
    yield

app = FastAPI(title=settings.app_name, version="1.0.0", docs_url=None, redoc_url=None, lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.middleware("http")(maintenance_middleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.include_router(auth.router)
app.include_router(payment.router)
app.include_router(dashboard.router)
app.include_router(withdrawal.router)
app.include_router(gains.router)
app.include_router(pages.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(wheel.router)
app.include_router(network.router)
app.include_router(learning.router)
app.include_router(admin_user.router)
app.include_router(contest.router)
app.include_router(support.router)
app.include_router(push.router)
app.include_router(password_reset.router)
app.include_router(wallet.router)

@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    from fastapi.responses import FileResponse
    return FileResponse("assets/sw.js", media_type="application/javascript")

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/auth/register")

@app.exception_handler(404)
async def not_found(request: Request, exc):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def error(request: Request, exc):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)
