"""WhoDados API Endpoints - Empresas (dados da Receita Federal) e metricas do dashboard.

A base de leads e' COMPARTILHADA entre as empresas (nao e' escopada por org) -- o
funil de filtros roda no servidor (server-side), entao o app trabalha a base
inteira sem baixar tudo para o navegador."""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Any, Dict, List, Optional
from .auth import get_current_user, get_active_org, get_papel_ativo
try:
    from .security import log_access, AuditAction
    HAS_AUDIT = True
except ImportError:
    HAS_AUDIT = False
from .db import (
    org_escopo_base, contar_carteira_db,
    get_crm_by_cnpj,
    listar_empresas_db, contar_empresas_db, get_empresa_by_cnpj_db, get_metricas_db,
)

router = APIRouter(prefix="/api/v1")


def _faixa_valor(v: Any) -> float:
    """Bucket determinístico pra visitante -- nunca o valor exato, mas
    ainda um numero (o frontend formata como moeda direto, sem saber que
    e' visitante)."""
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        v = 0.0
    if v <= 0:
        return 0.0
    if v < 100_000:
        return 50_000.0
    if v < 500_000:
        return 300_000.0
    if v < 1_000_000:
        return 750_000.0
    return 1_500_000.0


def _mascarar_empresa(e: Dict) -> Dict:
    """Visitante ve a empresa (razao social, municipio, CNAE, potencial),
    mas nao o dado de contato nem os valores financeiros exatos -- pensado
    pra dar acesso a alguem de fora (ex.: recrutador) sem expor cliente
    real."""
    e = dict(e)
    cnpj = e.get("cnpj_completo") or ""
    if len(cnpj) > 8:
        e["cnpj_completo"] = cnpj[:8] + "*" * (len(cnpj) - 8)
    if "email" in e:
        e["email"] = None
    if "contato_fone" in e:
        e["contato_fone"] = None
    if "capital_social" in e:
        e["capital_social"] = _faixa_valor(e.get("capital_social"))
    if "divida_total" in e:
        e["divida_total"] = _faixa_valor(e.get("divida_total"))
    e["_visitante"] = True
    return e


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
    potencial: Optional[List[str]] = Query(None),
    ordenar_por: str = "razao_social",
    limit: int = 100,
    offset: int = 0,
    current_user: Dict = Depends(get_current_user),
    papel: str = Depends(get_papel_ativo),
    org_id: int = Depends(get_active_org),
):
    """Uma pagina de empresas para o filtro atual (funil server-side).

    organizacao_id NAO e' opcional aqui: e' o que decide se a listagem sai da
    base da Receita ou da carteira propria da empresa. Sem ele, toda empresa
    cairia na base publica."""
    empresas = listar_empresas_db(
        cidade=cidade, cnae=cnae, porte=porte, busca=busca,
        divida_min=divida_min, divida_max=divida_max,
        capital_min=capital_min, capital_max=capital_max,
        fundacao_de=fundacao_de, fundacao_ate=fundacao_ate,
        incluir_inativas=incluir_inativas, potencial=potencial,
        ordenar_por=ordenar_por, limit=limit, offset=offset,
        organizacao_id=org_id,
    )
    if papel == "visitante":
        empresas = [_mascarar_empresa(e) for e in empresas]
    return empresas


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
    potencial: Optional[List[str]] = Query(None),
    current_user: Dict = Depends(get_current_user),
    org_id: int = Depends(get_active_org),
):
    """Quantas empresas batem no filtro atual (para o contador do funil)."""
    total = contar_empresas_db(
        organizacao_id=org_id,
        cidade=cidade, cnae=cnae, porte=porte, busca=busca,
        divida_min=divida_min, divida_max=divida_max,
        capital_min=capital_min, capital_max=capital_max,
        fundacao_de=fundacao_de, fundacao_ate=fundacao_ate,
        incluir_inativas=incluir_inativas, potencial=potencial,
    )
    return {"total": total}


@router.get("/empresas/{cnpj}")
async def get_empresa(
    request: Request, cnpj: str, current_user: Dict = Depends(get_current_user),
    org_id: int = Depends(get_active_org), papel: str = Depends(get_papel_ativo),
):
    empresa = get_empresa_by_cnpj_db(cnpj, organizacao_id=org_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa nao encontrada")
    if papel == "visitante":
        # Sem CRM: notas/motivo de descarte sao informacao interna de
        # negocio, nao dado publico da empresa -- visitante nao ve.
        empresa = _mascarar_empresa(empresa)
        empresa["crm"] = None
        return empresa
    crm = get_crm_by_cnpj(cnpj, org_id)
    empresa["crm"] = crm
    if HAS_AUDIT:
        log_access(request, AuditAction.EMPRESA_VIEW, user=current_user.get("sub"), resource_type="empresa", resource_id=cnpj)
    return empresa


@router.get("/dashboard/metricas")
async def metricas(
    current_user: Dict = Depends(get_current_user),
    org_id: int = Depends(get_active_org),
):
    # Empresa que prospecta sobre carteira propria nao tem numero da Receita
    # pra mostrar -- o painel dela se apoia na carteira, nao na base publica.
    if org_escopo_base(org_id) == "carteira":
        return {"escopo_base": "carteira", "total_empresas": contar_carteira_db(org_id)}
    return get_metricas_db()
