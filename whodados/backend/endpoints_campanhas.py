"""WhoDados API Endpoints - Campanhas de e-mail (criacao e execucao)."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
from .auth import get_current_user, get_active_org
from .db import (
    create_campanha, get_campanha, get_all_campanhas,
    get_template, create_notificacao, listar_empresas_db,
)
from .mailer import enviar_campanha

router = APIRouter(prefix="/api/v1")


@router.get("/campanhas")
async def listar_campanhas(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    return get_all_campanhas(organizacao_id=org_id)


@router.post("/campanhas")
async def criar_campanha(data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    t = get_template(data.get("template_id"), organizacao_id=org_id)
    if not t:
        raise HTTPException(status_code=400, detail="Template nao encontrado")
    return create_campanha(data.get("nome"), data.get("template_id"), data.get("filtros", {}), created_by=current_user.get("sub"), eh_sequencia=data.get("eh_sequencia", False), agendada_para=data.get("agendada_para"), organizacao_id=org_id)


@router.get("/campanhas/{campanha_id}")
async def get_campanha_by_id(campanha_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    c = get_campanha(campanha_id, organizacao_id=org_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    return c


@router.post("/campanhas/{campanha_id}/executar")
async def executar_campanha(campanha_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    campanha = get_campanha(campanha_id, organizacao_id=org_id)
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    if campanha.get("status") not in ["rascunho", "agendada"]:
        raise HTTPException(status_code=400, detail="Campanha ja executada")
    template = get_template(campanha["template_id"], organizacao_id=org_id)
    filtros = campanha.get("filtros") or {}
    empresas = listar_empresas_db(
        cidade=filtros.get("cidade"), cnae=filtros.get("cnae"), busca=filtros.get("busca"),
        limit=100000, offset=0,
    )
    # Classifica em 3 grupos: (1) tem e-mail real -> envia; (2) sem e-mail mas
    # com telefone -> vira notificacao "Ligar" (follow-up por telefone); (3) sem
    # nada -> pula. Antes usava um e-mail falso (contato@<cnpj>.com) e nada chegava.
    emails_por_cnpj = {}
    sem_email_com_fone = []
    for e in empresas:
        cnpj = e.get("cnpj_completo")
        if not cnpj:
            continue
        email = (e.get("email") or "").strip()
        if email and "@" in email:
            emails_por_cnpj[cnpj] = email
        elif (e.get("contato_fone") or "").strip(" ()-"):
            sem_email_com_fone.append(e)
    cnpjs = list(emails_por_cnpj.keys())
    if not cnpjs and not sem_email_com_fone:
        raise HTTPException(status_code=400, detail="Nenhuma empresa deste filtro tem e-mail nem telefone cadastrado.")

    # Notificacoes de "Ligar" para os sem e-mail com telefone (limitado para nao
    # inundar a aba Notificacoes numa campanha grande).
    _LIMITE_LIGAR = 100
    for e in sem_email_com_fone[:_LIMITE_LIGAR]:
        create_notificacao(
            "ligar", f"Ligar: {e.get('razao_social') or e['cnpj_completo']}",
            f"Sem e-mail. Telefone: {(e.get('contato_fone') or '').strip()} | {e.get('municipio', '')}",
            cnpj=e["cnpj_completo"], user_id=current_user.get("sub"), organizacao_id=org_id,
        )
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
    resultado = enviar_campanha(campanha_id, template, cnpjs, emails_por_cnpj, dados_empresas, organizacao_id=org_id)
    create_notificacao(
        "campanha_concluida", f"Campanha {campanha['nome']} concluida",
        f"Enviados: {resultado.get('sucessos', 0)} | Erros: {resultado.get('erros', 0)}",
        user_id=current_user.get("sub"), organizacao_id=org_id,
    )
    return resultado
