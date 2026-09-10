"""WhoDados API Endpoints - Campanhas de e-mail (criacao e execucao)."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
from .auth import get_current_user
from .db import (
    create_campanha, get_campanha, get_all_campanhas,
    get_template, create_notificacao, listar_empresas_db,
)
from .mailer import enviar_campanha

router = APIRouter(prefix="/api/v1")


@router.get("/campanhas")
async def listar_campanhas(current_user: Dict = Depends(get_current_user)):
    return get_all_campanhas()


@router.post("/campanhas")
async def criar_campanha(data: Dict, current_user: Dict = Depends(get_current_user)):
    t = get_template(data.get("template_id"))
    if not t:
        raise HTTPException(status_code=400, detail="Template nao encontrado")
    return create_campanha(data.get("nome"), data.get("template_id"), data.get("filtros", {}), created_by=current_user.get("sub"), eh_sequencia=data.get("eh_sequencia", False), agendada_para=data.get("agendada_para"))


@router.get("/campanhas/{campanha_id}")
async def get_campanha_by_id(campanha_id: int, current_user: Dict = Depends(get_current_user)):
    c = get_campanha(campanha_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    return c


@router.post("/campanhas/{campanha_id}/executar")
async def executar_campanha(campanha_id: int, current_user: Dict = Depends(get_current_user)):
    campanha = get_campanha(campanha_id)
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    if campanha.get("status") not in ["rascunho", "agendada"]:
        raise HTTPException(status_code=400, detail="Campanha ja executada")
    template = get_template(campanha["template_id"])
    filtros = campanha.get("filtros") or {}
    empresas = listar_empresas_db(
        cidade=filtros.get("cidade"), cnae=filtros.get("cnae"), busca=filtros.get("busca"),
        limit=100000, offset=0,
    )
    cnpjs = [e["cnpj_completo"] for e in empresas if e.get("cnpj_completo")]
    emails_por_cnpj = {cnpj: f"contato@{cnpj[:8]}.com" for cnpj in cnpjs}
    # Monta mapa CNPJ -> dados da empresa (para o template por CNAE)
    dados_empresas = {
        e["cnpj_completo"]: {
            "razao_social": e.get("razao_social", ""),
            "nome_fantasia": e.get("nome_fantasia", ""),
            "municipio": e.get("municipio", ""),
            "cnae_principal": e.get("cnae_principal", ""),
            "porte_nome": e.get("porte_nome", ""),
        }
        for e in empresas if e.get("cnpj_completo")
    }
    resultado = enviar_campanha(campanha_id, template, cnpjs, emails_por_cnpj, dados_empresas)
    create_notificacao(
        "campanha_concluida", f"Campanha {campanha['nome']} concluida",
        f"Enviados: {resultado.get('sucessos', 0)} | Erros: {resultado.get('erros', 0)}",
        user_id=current_user.get("sub"),
    )
    return resultado
