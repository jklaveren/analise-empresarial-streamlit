"""WhoDados API Endpoints - CRM (notas, status, kanban e classificacao por CNPJ).

Isolado por empresa (multi-tenant): todo acesso passa pela empresa ativa
(get_active_org, header X-Org-Id). NRA e SYVP tem CRMs separados."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from typing import Dict
from .auth import get_current_user, get_active_org
from .db import (
    create_or_update_crm, get_crm_by_cnpj, get_crm_all,
    create_notificacao, classificar_base, estatisticas_classificacao,
    listar_crm_classificados,
)

router = APIRouter(prefix="/api/v1")


@router.put("/crm/{cnpj}")
async def atualizar_crm(cnpj: str, data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    crm = create_or_update_crm(
        cnpj, org_id,
        status=data.get("status"), notas=data.get("notas"),
        criado_por=current_user.get("sub"),
        classificacao=data.get("classificacao"),
        motivo=data.get("motivo"),
        parceiro=data.get("parceiro"),
    )
    if data.get("status"):
        create_notificacao("status_mudou", f"CRM {data.get('status')}", f"CNPJ {cnpj}", user_id=current_user.get("sub"), cnpj=cnpj, organizacao_id=org_id)
    return crm


@router.get("/crm/{cnpj}")
async def get_crm(cnpj: str, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    return get_crm_by_cnpj(cnpj, org_id)


@router.get("/crm")
async def listar_crm(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    registros = get_crm_all(org_id)
    kanban = {"novo": [], "em_contato": [], "negociando": [], "convertido": [], "descartado": []}
    for r in registros:
        s = r.get("status") or "novo"
        if s in kanban:
            kanban[s].append(r)
    return kanban


@router.get("/crm/classificacao/estatisticas")
async def crm_classificacao_estatisticas(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    """Contadores por classificacao (ideal/possivel/fora/parceiro) da carteira."""
    return estatisticas_classificacao(org_id)


@router.get("/crm/classificacao")
async def crm_classificacao_listar(
    filtro: Optional[str] = Query(default=None, description="perfil_ideal|perfil_possivel|fora_perfil|parceiro|sem_classificacao"),
    current_user: Dict = Depends(get_current_user),
    org_id: int = Depends(get_active_org),
):
    """Lista os registros do CRM com classificacao (resolvendo dados da base)."""
    return listar_crm_classificados(org_id, filtro)


@router.post("/crm/classificar")
async def crm_classificar_base(
    limite: Optional[int] = Query(default=None, description="Limite de empresas a classificar (opcional)"),
    current_user: Dict = Depends(get_current_user),
    org_id: int = Depends(get_active_org),
):
    """Roda a regra de perfil na base inteira (lote) e grava ideal/possivel/fora."""
    return classificar_base(org_id, limite) if limite and limite > 0 else classificar_base(org_id)
