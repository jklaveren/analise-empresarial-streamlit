"""WhoDados API Endpoints - Lotes de Leads (Criação de lotes com filtros de potencial, etc.)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Optional
from .auth import get_current_user, get_active_org
from .db import (
    create_lote_db, get_lote_db, listar_lotes_db, delete_lote_db,
    contar_empresas_db, listar_empresas_db, create_campanha
)

router = APIRouter(prefix="/api/v1")


@router.get("/lotes")
async def listar_lotes(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    return listar_lotes_db(organizacao_id=org_id)


@router.post("/lotes")
async def criar_lote(data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    nome = (data.get("nome") or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Nome do lote é obrigatório")
    filtros = data.get("filtros") or {}

    # Calcular total de empresas que atendem aos filtros
    total = contar_empresas_db(
        organizacao_id=org_id,
        cidade=filtros.get("cidade"),
        cnae=filtros.get("cnae"),
        porte=filtros.get("porte"),
        busca=filtros.get("busca"),
        divida_min=filtros.get("divida_min"),
        divida_max=filtros.get("divida_max"),
        capital_min=filtros.get("capital_min"),
        capital_max=filtros.get("capital_max"),
        fundacao_de=filtros.get("fundacao_de"),
        fundacao_ate=filtros.get("fundacao_ate"),
        incluir_inativas=filtros.get("incluir_inativas", True),
        potencial=filtros.get("potencial"),
    )

    lote = create_lote_db(
        organizacao_id=org_id,
        nome=nome,
        filtros=filtros,
        total_encontrado=total,
        criado_por=current_user.get("sub")
    )
    return lote


@router.get("/lotes/{lote_id}")
async def get_lote(lote_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    lote = get_lote_db(lote_id, organizacao_id=org_id)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote não encontrado")

    filtros = lote.get("filtros") or {}
    empresas = listar_empresas_db(
        cidade=filtros.get("cidade"),
        cnae=filtros.get("cnae"),
        porte=filtros.get("porte"),
        busca=filtros.get("busca"),
        divida_min=filtros.get("divida_min"),
        divida_max=filtros.get("divida_max"),
        capital_min=filtros.get("capital_min"),
        capital_max=filtros.get("capital_max"),
        fundacao_de=filtros.get("fundacao_de"),
        fundacao_ate=filtros.get("fundacao_ate"),
        incluir_inativas=filtros.get("incluir_inativas", True),
        potencial=filtros.get("potencial"),
        limit=50,
        offset=0,
        organizacao_id=org_id,
    )
    lote["amostra_empresas"] = empresas
    return lote


@router.delete("/lotes/{lote_id}")
async def excluir_lote(lote_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    sucesso = delete_lote_db(lote_id, organizacao_id=org_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Lote não encontrado ou sem permissão")
    return {"ok": True}


@router.post("/lotes/{lote_id}/criar-campanha")
async def criar_campanha_do_lote(lote_id: int, data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    lote = get_lote_db(lote_id, organizacao_id=org_id)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote não encontrado")

    nome_campanha = data.get("nome_campanha") or f"Campanha - Lote: {lote['nome']}"
    template_id = data.get("template_id")
    canal = data.get("canal", "email")
    mensagem = data.get("mensagem")
    tamanho_lote = data.get("tamanho_lote", 100)

    campanha = create_campanha(
        nome=nome_campanha,
        template_id=template_id,
        filtros=lote.get("filtros") or {},
        created_by=current_user.get("sub"),
        organizacao_id=org_id,
        canal=canal,
        mensagem=mensagem,
        tamanho_lote=tamanho_lote
    )
    return campanha
