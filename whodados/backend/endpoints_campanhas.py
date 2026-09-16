"""WhoDados API Endpoints - Campanhas (e-mail e WhatsApp, em lote ou de uma vez)."""
import re
import time
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Optional
from .auth import get_current_user, get_active_org
from .config import settings
from .db import (
    create_campanha, get_campanha, get_all_campanhas, update_campanha_status,
    get_template, create_notificacao, listar_empresas_db,
    cnpjs_ja_contatados_campanha, registrar_envio_campanha, contar_envios_campanha,
    listar_campanhas_pendentes, buscar_socios_principais,
)
from .mailer import enviar_campanha
from .services.whatsapp_service import enviar_whatsapp

router = APIRouter(prefix="/api/v1")

_STATUS_EXECUTAVEIS = ("rascunho", "agendada", "em_andamento")


def _telefone_e164(contato_fone: Optional[str]) -> Optional[str]:
    """Converte o 'contato_fone' formatado ((DDD) NUMERO) pro formato E.164
    que o Twilio exige (+55DDDNUMERO). None se nao tiver digitos suficientes
    pra ser um numero de verdade."""
    digitos = re.sub(r"\D", "", contato_fone or "")
    if len(digitos) < 10:
        return None
    return "+55" + digitos


@router.get("/campanhas")
async def listar_campanhas(current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    campanhas = get_all_campanhas(organizacao_id=org_id)
    for c in campanhas:
        if c.get("tamanho_lote"):
            c["ja_contatados"] = contar_envios_campanha(c["id"])
    return campanhas


@router.post("/campanhas")
async def criar_campanha(data: Dict, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    canal = (data.get("canal") or "email").strip()
    if canal not in ("email", "whatsapp"):
        raise HTTPException(status_code=400, detail="Canal invalido (use 'email' ou 'whatsapp')")

    if canal == "email":
        t = get_template(data.get("template_id"), organizacao_id=org_id)
        if not t:
            raise HTTPException(status_code=400, detail="Template nao encontrado")
    else:
        if not (data.get("mensagem") or "").strip():
            raise HTTPException(status_code=400, detail="Mensagem e' obrigatoria para campanhas de WhatsApp")

    tamanho_lote = data.get("tamanho_lote")
    if tamanho_lote is not None:
        tamanho_lote = int(tamanho_lote)
        if tamanho_lote <= 0:
            raise HTTPException(status_code=400, detail="tamanho_lote deve ser maior que zero")

    return create_campanha(
        data.get("nome"), data.get("template_id"), data.get("filtros", {}),
        created_by=current_user.get("sub"), eh_sequencia=data.get("eh_sequencia", False),
        agendada_para=data.get("agendada_para"), organizacao_id=org_id,
        canal=canal, mensagem=data.get("mensagem"), tamanho_lote=tamanho_lote,
        repetir_ate=data.get("repetir_ate"),
    )


@router.get("/campanhas/{campanha_id}")
async def get_campanha_by_id(campanha_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    c = get_campanha(campanha_id, organizacao_id=org_id)
    if not c:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    c["ja_contatados"] = contar_envios_campanha(campanha_id)
    return c


def _executar_um_lote(campanha: Dict, current_user: Dict, org_id: int) -> Dict:
    """Manda o proximo lote (ou a campanha inteira, se tamanho_lote nao
    estiver definido -- comportamento antigo preservado). Pode ser chamado
    repetidas vezes: cada chamada avanca sobre quem ainda nao foi
    contatado por essa campanha. Marca 'concluida' quando o filtro inteiro
    ja foi coberto, ou 'em_andamento' quando ainda falta gente."""
    campanha_id = campanha["id"]
    canal = campanha.get("canal") or "email"
    filtros = campanha.get("filtros") or {}
    ja_contatados = cnpjs_ja_contatados_campanha(campanha_id)

    empresas = listar_empresas_db(
        cidade=filtros.get("cidade"), cnae=filtros.get("cnae"), porte=filtros.get("porte"),
        busca=filtros.get("busca"), divida_min=filtros.get("divida_min"),
        potencial=filtros.get("potencial"),
        limit=100000, offset=0,
    )
    pendentes = [e for e in empresas if e.get("cnpj_completo") and e["cnpj_completo"] not in ja_contatados]

    tamanho_lote = campanha.get("tamanho_lote")
    lote = pendentes[:tamanho_lote] if tamanho_lote else pendentes

    if not lote:
        update_campanha_status(campanha_id, "concluida", concluida_em=datetime.now(timezone.utc))
        return {"sucessos": 0, "erros": 0, "restantes": 0, "status": "concluida"}

    if canal == "whatsapp":
        resultado = _enviar_lote_whatsapp(campanha_id, lote, campanha.get("mensagem") or "")
    else:
        resultado = _enviar_lote_email(campanha_id, lote, campanha, org_id)

    restantes = len(pendentes) - len(lote)
    novo_status = "em_andamento" if restantes > 0 else "concluida"
    update_campanha_status(
        campanha_id, novo_status,
        ultimo_lote_em=datetime.now(timezone.utc),
        **({"concluida_em": datetime.now(timezone.utc)} if novo_status == "concluida" else {}),
    )
    create_notificacao(
        "campanha_lote_concluido" if novo_status == "em_andamento" else "campanha_concluida",
        f"Campanha {campanha['nome']}: lote enviado",
        f"Enviados: {resultado.get('sucessos', 0)} | Erros: {resultado.get('erros', 0)} | Restam: {restantes}",
        # user_id=None (em vez do usuario que clicou) -- assim a notificacao
        # aparece pra todo mundo da organizacao, nao so pra quem executou.
        # Necessario tambem pro lote automatico via cron, que nao tem um
        # usuario de verdade por tras do clique.
        organizacao_id=org_id,
    )
    resultado["restantes"] = restantes
    resultado["status"] = novo_status
    return resultado


def _enviar_lote_whatsapp(campanha_id: int, empresas: list, mensagem: str) -> Dict:
    sucessos, erros, erros_list = 0, 0, []
    for i, e in enumerate(empresas):
        cnpj = e["cnpj_completo"]
        telefone = _telefone_e164(e.get("contato_fone"))
        if not telefone:
            registrar_envio_campanha(campanha_id, cnpj, "whatsapp", status="sem_telefone")
            erros += 1
            erros_list.append({"cnpj": cnpj, "erro": "sem telefone cadastrado"})
            continue
        texto = (
            mensagem
            .replace("{{empresa}}", e.get("razao_social") or e.get("nome_fantasia") or "")
            .replace("{{cidade}}", e.get("municipio") or "")
        )
        try:
            r = enviar_whatsapp(telefone, texto)
            from .db import registrar_mensagem_whatsapp
            registrar_mensagem_whatsapp(telefone=telefone, direcao="saida", corpo=texto, cnpj=cnpj, status="enviada", twilio_sid=r.get("sid"))
            registrar_envio_campanha(campanha_id, cnpj, "whatsapp", status="enviado")
            sucessos += 1
        except Exception as e2:
            erros += 1
            erros_list.append({"cnpj": cnpj, "erro": str(e2)})
            registrar_envio_campanha(campanha_id, cnpj, "whatsapp", status="erro")
        # Twilio (contas de teste/baixo volume) rate-limita por segundo -- 1
        # msg/s e' conservador o bastante pra nao levar 429.
        if i < len(empresas) - 1:
            time.sleep(1.0)
    return {"sucessos": sucessos, "erros": erros, "erros_list": erros_list}


def _enviar_lote_email(campanha_id: int, empresas: list, campanha: Dict, org_id: int) -> Dict:
    template = get_template(campanha["template_id"], organizacao_id=org_id)
    emails_por_cnpj, sem_email_com_fone = {}, []
    for e in empresas:
        cnpj = e["cnpj_completo"]
        email = (e.get("email") or "").strip()
        if email and "@" in email:
            emails_por_cnpj[cnpj] = email
        elif (e.get("contato_fone") or "").strip(" ()-"):
            sem_email_com_fone.append(e)

    _LIMITE_LIGAR = 100
    for e in sem_email_com_fone[:_LIMITE_LIGAR]:
        create_notificacao(
            "ligar", f"Ligar: {e.get('razao_social') or e['cnpj_completo']}",
            f"Sem e-mail. Telefone: {(e.get('contato_fone') or '').strip()} | {e.get('municipio', '')}",
            cnpj=e["cnpj_completo"], organizacao_id=org_id,
        )
        registrar_envio_campanha(campanha_id, e["cnpj_completo"], "email", status="sem_email_ligar")

    # Nome do socio responsavel de cada empresa -- permite personalizar a
    # saudacao com o nome de uma pessoa em vez de so' a razao social.
    basicos_por_cnpj = {e["cnpj_completo"]: e["cnpj_completo"][:8] for e in empresas if e.get("cnpj_completo")}
    socios_por_basico = buscar_socios_principais(list(set(basicos_por_cnpj.values())))

    dados_empresas = {
        e["cnpj_completo"]: {
            "razao_social": e.get("razao_social", ""), "nome_fantasia": e.get("nome_fantasia", ""),
            "municipio": e.get("municipio", ""), "cnae_principal": e.get("cnae_principal", ""),
            "porte_nome": e.get("porte_nome", ""),
            "nome_socio": socios_por_basico.get(basicos_por_cnpj.get(e["cnpj_completo"]), ""),
        }
        for e in empresas if e.get("cnpj_completo")
    }
    cnpjs = list(emails_por_cnpj.keys())
    resultado = enviar_campanha(campanha_id, template, cnpjs, emails_por_cnpj, dados_empresas, organizacao_id=org_id) \
        if cnpjs else {"sucessos": 0, "erros": 0}
    for cnpj in cnpjs:
        registrar_envio_campanha(campanha_id, cnpj, "email", status="enviado")
    return resultado


@router.post("/campanhas/{campanha_id}/executar")
async def executar_campanha(campanha_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    campanha = get_campanha(campanha_id, organizacao_id=org_id)
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    if campanha.get("status") not in _STATUS_EXECUTAVEIS:
        raise HTTPException(status_code=400, detail="Campanha ja concluida")
    return _executar_um_lote(campanha, current_user, org_id)


@router.post("/campanhas/executar-pendentes")
async def executar_campanhas_pendentes(x_cron_secret: Optional[str] = Header(None)):
    """Avanca um lote de cada campanha agendada/em andamento que ainda nao
    rodou hoje. Feito pra ser chamado 1x/dia por um cron externo (GitHub
    Actions) -- o Render free hiberna quando ocioso, entao um scheduler
    dentro do proprio processo nao e' confiavel; um cron batendo aqui de
    fora e' o mesmo padrao ja usado pelo ETL neste repo.

    Protegido por CRON_SECRET (nao pelo login normal, o cron nao tem
    usuario) -- sem o secret configurado, o endpoint fica desligado."""
    secret_esperado = getattr(settings, "CRON_SECRET", "") or ""
    if not secret_esperado or x_cron_secret != secret_esperado:
        raise HTTPException(status_code=403, detail="CRON_SECRET invalido ou nao configurado")

    resultados = []
    for campanha in listar_campanhas_pendentes():
        try:
            r = _executar_um_lote(campanha, {"sub": "cron"}, campanha.get("organizacao_id"))
            resultados.append({"campanha_id": campanha["id"], "nome": campanha["nome"], **r})
        except Exception as e:
            resultados.append({"campanha_id": campanha["id"], "nome": campanha["nome"], "erro": str(e)})
    return {"processadas": len(resultados), "resultados": resultados}
