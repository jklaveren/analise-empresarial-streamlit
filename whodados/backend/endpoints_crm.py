"""WhoDados API Endpoints - CRM (notas, status, kanban, classificacao e
atividades/tarefas por CNPJ).

Isolado por empresa (multi-tenant): todo acesso passa pela empresa ativa
(get_active_org, header X-Org-Id). NRA e SYVP tem CRMs separados.

IMPORTANTE sobre ordem das rotas: rotas literais de um so segmento
("/crm/usuarios", "/crm/classificacao", ...) precisam vir ANTES de
"/crm/{cnpj}" no arquivo -- o FastAPI/Starlette casa por ordem de
registro, entao um "/crm/{cnpj}" cadastrado antes intercepta qualquer
outra rota GET de um segmento so (era exatamente o que travava
"/crm/classificacao" antes desta reorganizacao)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict
from .auth import get_current_user, get_active_org
from .db import (
    create_or_update_crm, get_crm_by_cnpj, get_crm_all,
    create_notificacao, classificar_base, estatisticas_classificacao,
    listar_crm_classificados,
    listar_usuarios_da_org, criar_atividade_crm, listar_atividades_crm,
    contar_atividades_pendentes, concluir_atividade_crm, deletar_atividade_crm,
    listar_todas_atividades, mover_atividade_crm, buscar_empresas_rapido,
    registrar_historico_atividade, listar_historico_atividade,
    atualizar_prazo_atividade, get_status_atividade,
)
from .mailer import notificar_tarefa_por_email

router = APIRouter(prefix="/api/v1")


@router.get("/crm")
async def listar_crm(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    registros = get_crm_all(org_id)
    pendentes_por_cnpj = contar_atividades_pendentes(org_id)
    kanban = {"novo": [], "em_contato": [], "negociando": [], "convertido": [], "descartado": []}
    for r in registros:
        r["atividades_pendentes"] = pendentes_por_cnpj.get(r["cnpj"], 0)
        s = r.get("status") or "novo"
        if s in kanban:
            kanban[s].append(r)
    return kanban


@router.get("/crm/usuarios")
async def crm_listar_usuarios(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    """Usuarios da organizacao ativa, pra popular o seletor de responsavel."""
    return listar_usuarios_da_org(org_id)


@router.get("/crm/buscar-empresa")
async def crm_buscar_empresa(
    q: str = Query(..., min_length=3, description="Parte do nome ou CNPJ"),
    current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org),
):
    """Busca rapida por nome/CNPJ, pra vincular uma atividade a uma empresa
    sem precisar sair da tela de Atividades."""
    return buscar_empresas_rapido(q, limite=10)


@router.get("/crm/atividades")
async def crm_listar_todas_atividades(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    """Todas as atividades da organizacao (board agregado, tipo Trello) --
    nao filtrado por empresa, ao contrario de /crm/{cnpj}/atividades."""
    return listar_todas_atividades(org_id)


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


def _criar_atividade(data: Dict, cnpj: Optional[str], current_user: Dict, org_id: int):
    """Cria a atividade e avisa o responsavel. cnpj opcional -- tarefa entre
    socios ("revisar proposta") nao precisa de empresa vinculada."""
    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="Titulo e' obrigatorio")
    atividade = criar_atividade_crm(
        cnpj, org_id, titulo, criado_por=current_user.get("sub"),
        tipo=data.get("tipo") or "tarefa", descricao=data.get("descricao"),
        responsavel_user_id=data.get("responsavel_user_id"), prazo=data.get("prazo"),
    )
    if data.get("responsavel_user_id"):
        usuarios = {u["id"]: u for u in listar_usuarios_da_org(org_id)}
        responsavel = usuarios.get(data["responsavel_user_id"])
        if responsavel:
            corpo = data.get("descricao") or f"Atribuida por {current_user.get('sub')}"
            create_notificacao(
                "tarefa_atribuida", f"Nova tarefa: {titulo}", corpo,
                cnpj=cnpj, user_id=responsavel["username"], organizacao_id=org_id,
            )
            # Aviso tambem no e-mail cadastrado do usuario -- quem recebe
            # tarefa nem sempre esta' com o app aberto. Falha aqui nao
            # derruba a criacao: a notificacao no app ja' foi gravada.
            notificar_tarefa_por_email(
                responsavel.get("email"), titulo, corpo, organizacao_id=org_id,
                prazo=data.get("prazo"), atribuida_por=current_user.get("sub"),
            )
    return atividade


@router.post("/crm/atividades")
async def crm_criar_atividade_avulsa(data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    """Cria atividade direto do board, sem precisar abrir uma empresa antes.
    Aceita "cnpj" no corpo pra vincular a uma empresa (opcional)."""
    return _criar_atividade(data, (data.get("cnpj") or "").strip() or None, current_user, org_id)


@router.post("/crm/atividades/{atividade_id}/concluir")
async def crm_concluir_atividade(atividade_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    anterior = get_status_atividade(atividade_id, org_id)
    if not concluir_atividade_crm(atividade_id, org_id):
        raise HTTPException(status_code=404, detail="Atividade nao encontrada")
    if anterior != "concluida":
        registrar_historico_atividade(
            atividade_id, "status", current_user.get("sub"), de=anterior, para="concluida"
        )
    return {"ok": True}


@router.post("/crm/atividades/{atividade_id}/mover")
async def crm_mover_atividade(atividade_id: int, data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    """Move a atividade entre colunas do board (pendente / em_andamento / concluida)."""
    status = data.get("status")
    anterior = get_status_atividade(atividade_id, org_id)
    if not mover_atividade_crm(atividade_id, org_id, status):
        raise HTTPException(status_code=400, detail="Atividade nao encontrada ou status invalido")
    if anterior != status:
        registrar_historico_atividade(
            atividade_id, "status", current_user.get("sub"), de=anterior, para=status
        )
    return {"ok": True}


@router.get("/crm/atividades/{atividade_id}/historico")
async def crm_historico_atividade(atividade_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    """Acompanhamento da tarefa: comentarios + mudancas de status/prazo."""
    return listar_historico_atividade(atividade_id, org_id)


@router.post("/crm/atividades/{atividade_id}/comentario")
async def crm_comentar_atividade(atividade_id: int, data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    texto = (data.get("texto") or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Comentario vazio")
    if get_status_atividade(atividade_id, org_id) is None:
        raise HTTPException(status_code=404, detail="Atividade nao encontrada")
    return registrar_historico_atividade(atividade_id, "comentario", current_user.get("sub"), texto=texto)


@router.post("/crm/atividades/{atividade_id}/prazo")
async def crm_alterar_prazo_atividade(atividade_id: int, data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    """Novo prazo (YYYY-MM-DD, ou vazio pra tirar). Fica no historico."""
    novo = (data.get("prazo") or "").strip() or None
    anterior = atualizar_prazo_atividade(atividade_id, org_id, novo)
    if anterior is None:
        raise HTTPException(status_code=404, detail="Atividade nao encontrada")
    if anterior != (novo or ""):
        registrar_historico_atividade(
            atividade_id, "prazo", current_user.get("sub"), de=anterior or None, para=novo
        )
    return {"ok": True}


@router.delete("/crm/atividades/{atividade_id}")
async def crm_deletar_atividade(atividade_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    if not deletar_atividade_crm(atividade_id, org_id):
        raise HTTPException(status_code=404, detail="Atividade nao encontrada")
    return {"ok": True}


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


@router.get("/crm/{cnpj}/atividades")
async def crm_listar_atividades(cnpj: str, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    return listar_atividades_crm(cnpj, org_id)


@router.post("/crm/{cnpj}/atividades")
async def crm_criar_atividade(cnpj: str, data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    return _criar_atividade(data, cnpj, current_user, org_id)
