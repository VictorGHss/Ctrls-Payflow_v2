"""
FastAPI main application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.database import init_db
from app.logging import setup_logging
from app.routes_health import router as health_router
from app.routes_oauth_new import router as oauth_router

# Setup logging
logger = setup_logging(__name__, level="INFO")

# Inicializar aplicação
app = FastAPI(
    title="PayFlow Automation API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware de segurança
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.contaazul.com"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://accounts.contaazul.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Setup banco de dados na inicialização
settings = get_settings()
engine, SessionLocal = init_db(settings.DATABASE_URL)

logger.info(f"PayFlow API iniciada - {settings.PROJECT_VERSION}")


# Dependency para obter sessão do banco
def get_db():
    """Dependency para obter sessão do banco."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Registrar routers
app.include_router(health_router)
app.include_router(oauth_router)


@app.on_event("startup")
async def startup_event():
    """Event disparado na inicialização."""
    logger.info("Aplicação iniciada com sucesso")


@app.on_event("shutdown")
async def shutdown_event():
    """Event disparado no encerramento."""
    logger.info("Aplicação encerrada")
