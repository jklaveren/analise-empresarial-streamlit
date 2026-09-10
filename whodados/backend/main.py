"""WhoDados Backend 2.0 - FastAPI Entry Point."""
from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .logger import logger
from .db.config import ensure_tables_exist, check_database_health
from .db import seed_default_templates
from .endpoints import router as api_router


_SECRET_KEY_PADRAO = "change-me-in-production-use-strong-secret"


def secret_key_ok() -> bool:
    """A SECRET_KEY assina os tokens de login. Se ficar na padrao (ou curta),
    os tokens sao forjaveis. Consideramos OK quando foi trocada e tem tamanho
    razoavel."""
    sk = settings.SECRET_KEY or ""
    return sk != _SECRET_KEY_PADRAO and len(sk) >= 32


def _verificar_seguranca() -> None:
    """Alerta (bem visivel) sobre configuracoes de seguranca frageis. NAO derruba
    o app -- so grita no log -- pra nao trancar o acesso caso a env nao esteja
    setada; a Jessica confere no Render pelo /health (secret_key_ok / producao)."""
    if not secret_key_ok():
        logger.error(
            "!!! SEGURANCA: SECRET_KEY esta na padrao ou muito curta -- os tokens de "
            "login sao FORJAVEIS. Defina uma SECRET_KEY forte (>=32 chars) no Render."
        )
    if not settings.is_production:
        logger.warning(
            f"APP_ENV={settings.APP_ENV} (nao-producao). Em producao, defina "
            "APP_ENV=production no Render."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"WhoDados API iniciando v{settings.APP_VERSION}")
    _verificar_seguranca()
    if settings.DATABASE_URL:
        try:
            ensure_tables_exist()
            logger.info("Tabelas verificadas")
            try:
                criados = seed_default_templates()
                if criados:
                    logger.info(f"{criados} templates padrao inseridos")
            except Exception as e:
                logger.error(f"Falha ao popular templates padrao: {e}")
        except Exception as e:
            logger.error(f"Falha ao inicializar banco: {e}")
    yield
    logger.info("WhoDados API encerrando")


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# CORS (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middlewares (innermost)
try:
    from .security import SecurityHeadersMiddleware, RateLimiterMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimiterMiddleware)
    logger.info("Security middlewares loaded")
except ImportError as e:
    logger.warning(f"Security middlewares not available: {e}")

app.include_router(api_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "versao": settings.APP_VERSION,
        "ambiente": settings.APP_ENV,
        "producao": settings.is_production,
        "secret_key_ok": secret_key_ok(),
        "banco_ok": check_database_health(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
async def root():
    return {"msg": f"WhoDados API v{settings.APP_VERSION}", "docs": "/docs"}
