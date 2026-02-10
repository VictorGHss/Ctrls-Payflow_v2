"""
Rotas básicas (healthz, status, etc).
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/ready")
def ready():
    """Readiness check (verifica banco de dados e dependências)."""
    try:
        # Aqui você pode adicionar verificações mais profundas
        # Ex: tentar conectar ao banco, verificar variáveis de ambiente, etc
        return {"status": "ready", "message": "Serviço pronto"}
    except Exception as e:
        return {"status": "not ready", "error": str(e)}, 503


@router.get("/")
def root():
    """Rota raiz com informações do serviço."""
    return {
        "service": "PayFlow Automation API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/healthz",
            "ready": "/ready",
            "oauth": "/oauth/authorize",
            "callback": "/oauth/callback",
        },
    }

