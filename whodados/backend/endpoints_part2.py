"""WhoDados API Endpoints v2.0 - Part 2: Templates, Campanhas, Notificacoes."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from typing import Dict, Optional
from .auth import get_current_user
from .db import (
    create_template, get_template, get_all_templates,
    create_campanha, get_campanha, get_all_campanhas,
    create_notificacao, get_notificacoes, mark_notificacao_lida,
    # Monitor de emails (follow-up com semaforo)
    get_emails_for_monitor, get_monitor_stats, get_emails_vermelhos_para_followup,
    # Templates por CNAE
    update_template, delete_template, get_templates_by_categoria,
    # Card/imagem do template
    set_template_imagem, get_template_imagem, clear_template_imagem,
)
from .data import carregar_empresas, filtrar_empresas
from .mailer import enviar_campanha
from .logger import get_logger
logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1")

@router.get("/templates")
async def listar_templates(categoria: Optional[str] = None, current_user: Dict = Depends(get_current_user)):
    if categoria and categoria != "todos":
        return get_templates_by_categoria(categoria)
    return get_all_templates()

@router.post("/templates")
async def criar_template(data: Dict, current_user: Dict = Depends(get_current_user)):
    return create_template(
        data.get("nome"), data.get("assunto"), data.get("corpo_html"),
        data.get("corpo_texto"),
        criado_por=current_user.get("sub"),
        categoria_cnae=data.get("categoria_cnae", "todos"),
    )

@router.get("/templates/{template_id}")
async def get_template_by_id(template_id: int, current_user: Dict = Depends(get_current_user)):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template nao encontrado")
    return t

@router.put("/templates/{template_id}")
async def atualizar_template(template_id: int, data: Dict, current_user: Dict = Depends(get_current_user)):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template nao encontrado")
    return update_template(
        template_id,
        nome=data.get("nome"),
        assunto=data.get("assunto"),
        corpo_html=data.get("corpo_html"),
        corpo_texto=data.get("corpo_texto"),
        categoria_cnae=data.get("categoria_cnae"),
    )

@router.delete("/templates/{template_id}")
async def deletar_template(template_id: int, current_user: Dict = Depends(get_current_user)):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template nao encontrado")
    if not delete_template(template_id):
        raise HTTPException(status_code=400, detail="Erro ao deletar template")
    return {"ok": True}

# ---- Card/imagem do template (usada no corpo do email via {{imagem}}) ----

_IMAGEM_MAX_BYTES = 3 * 1024 * 1024  # 3 MB
_IMAGEM_TIPOS_OK = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}

@router.post("/templates/{template_id}/imagem")
async def enviar_imagem_template(template_id: int, arquivo: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template nao encontrado")
    if arquivo.content_type not in _IMAGEM_TIPOS_OK:
        raise HTTPException(status_code=400, detail="Formato de imagem nao suportado (use PNG, JPG, WEBP ou GIF)")
    conteudo = await arquivo.read()
    if len(conteudo) > _IMAGEM_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Imagem muito grande (limite de 3 MB)")
    return set_template_imagem(template_id, conteudo, arquivo.content_type)

@router.get("/templates/{template_id}/imagem")
async def obter_imagem_template(template_id: int):
    """Endpoint publico (sem autenticacao) -- e' o que carrega a imagem quando o email e' aberto
    no cliente de email do destinatario, ou na pre-visualizacao do template no dashboard."""
    row = get_template_imagem(template_id)
    if not row or not row.get("imagem_data"):
        raise HTTPException(status_code=404, detail="Este template nao tem imagem")
    return Response(content=bytes(row["imagem_data"]), media_type=row.get("imagem_mime") or "image/png", headers={"Cache-Control": "public, max-age=300"})

@router.delete("/templates/{template_id}/imagem")
async def remover_imagem_template(template_id: int, current_user: Dict = Depends(get_current_user)):
    t = get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template nao encontrado")
    return clear_template_imagem(template_id)

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
    df = carregar_empresas()
    empresas = filtrar_empresas(df, filtros.get("cidade"), filtros.get("cnae"), filtros.get("busca"))
    cnpjs = empresas["CNPJ_COMPLETO"].dropna().unique().tolist() if not empresas.empty else []
    emails_por_cnpj = {cnpj: f"contato@{cnpj[:8]}.com" for cnpj in cnpjs}
    # Monta mapa CNPJ -> dados da empresa (para o template por CNAE)
    dados_empresas = {}
    if not empresas.empty:
        for _, row in empresas.iterrows():
            cnpj = row.get("CNPJ_COMPLETO")
            if cnpj and cnpj in cnpjs:
                dados_empresas[cnpj] = {
                    "razao_social": row.get("RAZAO_SOCIAL", ""),
                    "nome_fantasia": row.get("NOME_FANTASIA", ""),
                    "municipio": row.get("MUNIC_NOME") or row.get("MUNICIPIO", ""),
                    "cnae_principal": row.get("CNAE_PRINCIPAL", ""),
                    "porte_nome": row.get("PORTE_NOME", ""),
                }
    resultado = enviar_campanha(campanha_id, template, cnpjs, emails_por_cnpj, dados_empresas)
    create_notificacao(
        "campanha_concluida", f"Campanha {campanha['nome']} concluida",
        f"Enviados: {resultado.get('sucessos', 0)} | Erros: {resultado.get('erros', 0)}",
        user_id=current_user.get("sub"),
    )
    return resultado

@router.get("/notificacoes")
async def listar_notificacoes(lidas: Optional[bool] = None, current_user: Dict = Depends(get_current_user)):
    return get_notificacoes(user_id=current_user.get("sub"), lidas=lidas)

@router.post("/notificacoes/{notificacao_id}/ler")
async def marcar_lida(notificacao_id: int, current_user: Dict = Depends(get_current_user)):
    success = mark_notificacao_lida(notificacao_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notificacao nao encontrada")
    return {"ok": True}


# ==================== MONITOR DE EMAILS (FOLLOW-UP 7 DIAS) ====================

@router.get("/emails-enviados/monitor")
async def monitor_emails(
    campaign_id: Optional[int] = None,
    semaforo: Optional[str] = None,
    dias_sla: int = 7,
    limit: int = 200,
    offset: int = 0,
    current_user: Dict = Depends(get_current_user),
):
    """
    Lista e-mails enviados para acompanhamento de follow-up com semaforo.

    - campaign_id: filtra por campanha (opcional)
    - semaforo: 'verde' | 'amarelo' | 'vermelho' | 'cinza' (opcional)
    - dias_sla: dias do SLA (padrao 7)
    """
    items = get_emails_for_monitor(
        campaign_id=campaign_id,
        dias_sla=dias_sla,
        limit=limit,
        offset=offset,
    )
    if semaforo:
        items = [i for i in items if i.get("semaforo_status") == semaforo]
    # Serializa campos de data para ISO
    out = []
    for item in items:
        row = dict(item)
        for k in ("enviado_em", "aberto_em", "criado_em"):
            v = row.get(k)
            if v is not None and hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        # garante tipos primitivos
        for k in ("id", "campaign_id", "sequencia_passo"):
            if k in row and row[k] is not None:
                row[k] = int(row[k])
        if "dias_desde_envio" in row and row["dias_desde_envio"] is not None:
            row["dias_desde_envio"] = float(row["dias_desde_envio"])
        out.append(row)
    return out


@router.get("/emails-enviados/monitor/stats")
async def monitor_stats(
    dias_sla: int = 7,
    current_user: Dict = Depends(get_current_user),
):
    """Resumo agregado (verde/amarelo/vermelho/cinza) para o dashboard."""
    stats = get_monitor_stats(dias_sla=dias_sla)
    # normaliza tipos para JSON
    for k in ("total_enviados", "verde", "amarelo", "vermelho", "cinza"):
        if k in stats and stats[k] is not None:
            stats[k] = int(stats[k])
        else:
            stats[k] = 0
    total = stats["verde"] + stats["amarelo"] + stats["vermelho"] + stats["cinza"]
    stats["total"] = total
    return stats


@router.get("/emails-enviados/monitor/vermelhos")
async def monitor_vermelhos(
    limite: int = 50,
    current_user: Dict = Depends(get_current_user),
):
    """Lista e-mails no estado vermelho (>5 dias sem abertura) para disparo de follow-up."""
    rows = get_emails_vermelhos_para_followup(limite=limite)
    out = []
    for item in rows:
        row = dict(item)
        for k in ("enviado_em", "aberto_em", "criado_em"):
            v = row.get(k)
            if v is not None and hasattr(v, "isoformat"):
                row[k] = v.isoformat()
        out.append(row)
    return out