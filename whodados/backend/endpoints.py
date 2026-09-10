"""Agrega todos os routers da API WhoDados num unico router.

Cada dominio vive em seu proprio arquivo endpoints_<dominio>.py; aqui eles
sao apenas montados na ordem. Todos usam o mesmo prefixo /api/v1 (exceto os
que definem o proprio prefixo, como admin e analytics)."""
from fastapi import APIRouter
from .endpoints_auth import router as auth_router
from .endpoints_organizacoes import router as organizacoes_router
from .endpoints_empresas import router as empresas_router
from .endpoints_crm import router as crm_router
from .endpoints_templates import router as templates_router
from .endpoints_campanhas import router as campanhas_router
from .endpoints_notificacoes import router as notificacoes_router
from .endpoints_monitor import router as monitor_router
from .endpoints_admin import router as admin_router
from .endpoints_nlp import router as nlp_router
from .endpoints_enriquecimento import router as enriquecimento_router
from .endpoints_analytics import router as analytics_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(organizacoes_router)
router.include_router(empresas_router)
router.include_router(crm_router)
router.include_router(templates_router)
router.include_router(campanhas_router)
router.include_router(notificacoes_router)
router.include_router(monitor_router)
router.include_router(admin_router)
router.include_router(nlp_router)
router.include_router(enriquecimento_router)
router.include_router(analytics_router)
