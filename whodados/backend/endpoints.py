"""WhoDados API Endpoints v2.0 - Unificado."""
from fastapi import APIRouter
from .endpoints_part1 import router as part1
from .endpoints_part2 import router as part2
from .endpoints_admin import router as admin_router
from .endpoints_nlp import router as nlp_router
from .endpoints_enriquecimento import router as enriquecimento_router
from .endpoints_analytics import router as analytics_router
router = APIRouter()
router.include_router(part1)
router.include_router(part2)
router.include_router(admin_router)
router.include_router(nlp_router)
router.include_router(enriquecimento_router)
router.include_router(analytics_router)
