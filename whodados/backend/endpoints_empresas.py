"""WhoDados API Endpoints - Empresas (dados da Receita Federal) e metricas do dashboard.

A base de leads e' COMPARTILHADA entre as empresas (nao e' escopada por org) -- o
funil de filtros roda no servidor (server-side), entao o app trabalha a base
inteira sem baixar tudo para o navegador."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from .auth import get_current_user, get_active_org
try:
    from .security import log_access, AuditAction
    HAS_AUDIT = True
except ImportError:
    HAS_AUDIT = False
from .db import (
    get_crm_by_cnpj,
    listar_empresas_db, contar_empresas_db, get_empresa_by_cnpj_db, get_metricas_db,
)

router = APIRouter(prefix="/api/v1")


@router.get("/empresas")
async def listar_empresas(
    cidade: Optional[List[str]] = Query(None),
    cnae: Optional[List[str]] = Query(None),
    porte: Optional[List[str]] = Query(None),
    busca: Optional[str] = None,
    divida_min: Optional[float] = None,
    divida_max: Optional[float] = None,
    capital_min: Optional[float] = None,
    capital_max: Optional[float] = None,
    fundacao_de: Optional[str] = None,
    fundacao_ate: Optional[str] = None,
    incluir_inativas: bool = True,
    limit: int = 100,
    offset: int = 0,
    current_user: Dict = Depends(get_current_user),
):
    """Uma pagina de empresas para o filtro atual (funil server-side)."""
    return listar_empresas_db(
        cidade=cidade, cnae=cnae, porte=porte, busca=busca,
        divida_min=divida_min, divida_max=divida_max,
        capital_min=capital_min, capital_max=capital_max,
        fundacao_de=fundacao_de, fundacao_ate=fundacao_ate,
        incluir_inativas=incluir_inativas, limit=limit, offset=offset,
    )


@router.get("/empresas/count")
async def contar_empresas(
    cidade: Optional[List[str]] = Query(None),
    cnae: Optional[List[str]] = Query(None),
    porte: Optional[List[str]] = Query(None),
    busca: Optional[str] = None,
    divida_min: Optional[float] = None,
    divida_max: Optional[float] = None,
    capital_min: Optional[float] = None,
    capital_max: Optional[float] = None,
    fundacao_de: Optional[str] = None,
    fundacao_ate: Optional[str] = None,
    incluir_inativas: bool = True,
    current_user: Dict = Depends(get_current_user),
):
    """Quantas empresas batem no filtro atual (para o contador do funil)."""
    total = contar_empresas_db(
        cidade=cidade, cnae=cnae, porte=porte, busca=busca,
        divida_min=divida_min, divida_max=divida_max,
        capital_min=capital_min, capital_max=capital_max,
        fundacao_de=fundacao_de, fundacao_ate=fundacao_ate,
        incluir_inativas=incluir_inativas,
    )
    return {"total": total}


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
