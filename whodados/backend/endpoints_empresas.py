"""WhoDados API Endpoints - Empresas (dados da Receita Federal) e metricas do dashboard."""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Optional
from .auth import get_current_user, get_active_org
try:
    from .security import log_access, AuditAction
    HAS_AUDIT = True
except ImportError:
    HAS_AUDIT = False
from .db import (
    get_crm_by_cnpj,
    listar_empresas_db, get_empresa_by_cnpj_db, get_metricas_db,
)

router = APIRouter(prefix="/api/v1")


@router.get("/empresas")
async def listar_empresas(cidade: Optional[str] = None, cnae: Optional[str] = None, busca: Optional[str] = None, limit: int = 100, offset: int = 0, current_user: Dict = Depends(get_current_user)):
    return listar_empresas_db(cidade=cidade, cnae=cnae, busca=busca, limit=limit, offset=offset)


@router.get("/empresas/{cnpj}")
async def get_empresa(request: Request, cnpj: str, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    empresa = get_empresa_by_cnpj_db(cnpj)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")
    crm = get_crm_by_cnpj(cnpj, org_id)
    empresa["crm"] = crm
    if HAS_AUDIT:
        log_access(request, AuditAction.EMPRESA_VIEW, user=current_user.get("sub"), resource_type="empresa", resource_id=cnpj)
    return empresa


@router.get("/dashboard/metricas")
async def metricas(current_user: Dict = Depends(get_current_user)):
    return get_metricas_db()
