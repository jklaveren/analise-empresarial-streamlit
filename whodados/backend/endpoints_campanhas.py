"""WhoDados API Endpoints - Campanhas (e-mail e WhatsApp, em lote ou de uma vez)."""
import re
import time
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Any, Dict, Optional
from .auth import get_current_user, get_active_org
from .config import settings
from .db import (
    create_campanha, get_campanha, get_all_campanhas, update_campanha_status,
    get_template, create_notificacao, listar_empresas_db,
    cnpjs_ja_contatados_campanha, registrar_envio_campanha, contar_envios_campanha,
    listar_campanhas_pendentes, buscar_socios_principais, contar_emails_enviados_hoje,
    cnpjs_contatados_org,
    org_escopo_base, email_esta_descadastrado,
)
from .mailer import enviar_campanha, montar_email_para_cnpj, validar_lote
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


def _selecionar_lote(campanha: Dict, org_id: int) -> Dict:
    """Quem entra no proximo lote, e de onde essa lista saiu.

    E' a MESMA selecao usada no disparo -- a previa chama esta funcao pra
    mostrar exatamente o que vai sair, nao uma estimativa parecida.
    """
    filtros = campanha.get("filtros") or {}
    ja_contatados = cnpjs_ja_contatados_campanha(campanha["id"])

    # Supressao global. filtros.recontato_dias libera recontato apos N dias.
    recontato_dias = filtros.get("recontato_dias")
    ja_contatados |= cnpjs_contatados_org(
        org_id, desde_dias=None if recontato_dias in (None, "") else int(recontato_dias)
    )

    # Passa o filtro INTEIRO. Antes so ia cidade/cnae/porte/busca/divida_min:
    # uma campanha feita a partir de um lote com capital minimo ou data de
    # fundacao disparava pra um conjunto maior do que o lote mostrava.
    empresas = listar_empresas_db(
        cidade=filtros.get("cidade"), cnae=filtros.get("cnae"), porte=filtros.get("porte"),
        busca=filtros.get("busca"),
        divida_min=filtros.get("divida_min"), divida_max=filtros.get("divida_max"),
        capital_min=filtros.get("capital_min"), capital_max=filtros.get("capital_max"),
        fundacao_de=filtros.get("fundacao_de"), fundacao_ate=filtros.get("fundacao_ate"),
        incluir_inativas=filtros.get("incluir_inativas", False),
        contato=filtros.get("contato"),
        potencial=filtros.get("potencial"), categoria=filtros.get("categoria"),
        limit=100000, offset=0, organizacao_id=org_id,
    )
    pendentes = [e for e in empresas if e.get("cnpj_completo") and e["cnpj_completo"] not in ja_contatados]
    tamanho_lote = campanha.get("tamanho_lote")
    lote = pendentes[:tamanho_lote] if tamanho_lote else pendentes
    return {
        "fonte": "carteira" if org_escopo_base(org_id) == "carteira" else "Receita Federal",
        "no_filtro": len(empresas),
        "ja_contatados": len(empresas) - len(pendentes),
        "pendentes": len(pendentes),
        "lote": lote,
        "restantes_depois": max(len(pendentes) - len(lote), 0),
    }


@router.get("/campanhas/{campanha_id}/previa")
async def previa_do_lote(campanha_id: int, current_user: Dict = Depends(get_current_user),
                         org_id: int = Depends(get_active_org)):
    """De onde vem a carga e o que realmente vai sair no proximo disparo.

    Existe porque "mandar a campanha" escondia decisoes que mudam muito o
    resultado: quanta gente do filtro nem tem e-mail, quantos ja' foram
    contatados, quantos pediram descadastro, e quantos endereços sao
    repetidos (o mesmo e-mail de contabilidade responde por dezenas de
    empresas na base da Receita -- disparar pros dois e' o mesmo destinatario
    recebendo duas vezes).
    """
    campanha = get_campanha(campanha_id, organizacao_id=org_id)
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")

    sel = _selecionar_lote(campanha, org_id)
    lote = sel.pop("lote")

    com_email, sem_email_com_fone, sem_contato, descadastrados = [], 0, 0, 0
    vistos: Dict[str, int] = {}
    for e in lote:
        email = (e.get("email") or "").strip().lower()
        if email and "@" in email:
            if email_esta_descadastrado(email):
                descadastrados += 1
                continue
            vistos[email] = vistos.get(email, 0) + 1
            com_email.append({
                "cnpj": e.get("cnpj_completo"), "razao_social": e.get("razao_social"),
                "municipio": e.get("municipio"), "email": email,
            })
        elif (e.get("contato_fone") or "").strip(" ()-"):
            sem_email_com_fone += 1
        else:
            sem_contato += 1

    repetidos = sum(n - 1 for n in vistos.values() if n > 1)
    return {
        **sel,
        "no_lote": len(lote),
        "vao_receber": len(com_email),
        "enderecos_distintos": len(vistos),
        "repetidos_no_lote": repetidos,
        "sem_email_viram_ligacao": sem_email_com_fone,
        "sem_nenhum_contato": sem_contato,
        "descadastrados_lgpd": descadastrados,
        "amostra": com_email[:10],
    }


def _janela_de_envio() -> Dict[str, Any]:
    """Se agora esta dentro da janela de envio, no fuso do negocio."""
    try:
        from zoneinfo import ZoneInfo
        agora = datetime.now(ZoneInfo(getattr(settings, "ENVIO_TIMEZONE", "America/Sao_Paulo")))
    except Exception:
        agora = datetime.now(timezone.utc)

    dias = {int(d) for d in str(getattr(settings, "ENVIO_DIAS_SEMANA", "1,2,3,4,5")).split(",") if d.strip()}
    if agora.isoweekday() not in dias:
        return {"aberta": False, "motivo": f"fora dos dias de envio ({agora:%A})"}

    def minutos(hhmm: str, padrao: int) -> int:
        try:
            h, m = str(hhmm).split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return padrao

    inicio = minutos(getattr(settings, "ENVIO_JANELA_INICIO", "07:00"), 7 * 60)
    fim = minutos(getattr(settings, "ENVIO_JANELA_FIM", "19:30"), 19 * 60 + 30)
    atual = agora.hour * 60 + agora.minute
    if not (inicio <= atual <= fim):
        return {"aberta": False,
                "motivo": f"fora da janela ({agora:%H:%M} nao esta entre "
                          f"{getattr(settings, 'ENVIO_JANELA_INICIO', '07:00')} e "
                          f"{getattr(settings, 'ENVIO_JANELA_FIM', '19:30')})"}
    return {"aberta": True, "agora": agora.strftime("%Y-%m-%d %H:%M %Z")}


def _orcamento_email_hoje() -> Optional[int]:
    """Quantos e-mails ainda cabem hoje no limite do provedor, ou None se a
    checagem estiver desligada (EMAIL_LIMITE_DIARIO=0)."""
    limite = int(getattr(settings, "EMAIL_LIMITE_DIARIO", 0) or 0)
    if limite <= 0:
        return None
    return max(limite - contar_emails_enviados_hoje(), 0)


def _executar_um_lote(campanha: Dict, current_user: Dict, org_id: int,
                      max_envios: Optional[int] = None) -> Dict:
    """Manda o proximo lote (ou a campanha inteira, se tamanho_lote nao
    estiver definido -- comportamento antigo preservado). Pode ser chamado
    repetidas vezes: cada chamada avanca sobre quem ainda nao foi
    contatado por essa campanha. Marca 'concluida' quando o filtro inteiro
    ja foi coberto, ou 'em_andamento' quando ainda falta gente."""
    campanha_id = campanha["id"]
    canal = campanha.get("canal") or "email"

    sel = _selecionar_lote(campanha, org_id)
    lote = sel["lote"]
    pendentes_total = sel["pendentes"]

    if not lote:
        update_campanha_status(campanha_id, "concluida", concluida_em=datetime.now(timezone.utc))
        return {"sucessos": 0, "erros": 0, "restantes": 0, "status": "concluida"}

    # Teto diario do provedor (so e-mail; WhatsApp tem limite proprio).
    if canal == "email" and max_envios is not None:
        if max_envios <= 0:
            return {"sucessos": 0, "erros": 0, "restantes": pendentes_total,
                    "status": campanha.get("status") or "em_andamento",
                    "adiado_por_limite": True}
        lote = lote[:max_envios]

    if canal == "whatsapp":
        resultado = _enviar_lote_whatsapp(campanha_id, lote, campanha.get("mensagem") or "")
    else:
        resultado = _enviar_lote_email(campanha_id, lote, campanha, org_id,
                                       remetente=current_user.get("sub"))

    restantes = pendentes_total - len(lote)
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


def _enviar_lote_email(campanha_id: int, empresas: list, campanha: Dict, org_id: int,
                       remetente: Optional[str] = None) -> Dict:
    """remetente: quem disparou. O e-mail e' individual -- sai do endereco
    e com a assinatura da pessoa, pelo servidor da empresa."""
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
            "cnae_descricao": e.get("cnae_descricao", ""),
            "porte_nome": e.get("porte_nome", ""),
            "nome_socio": socios_por_basico.get(basicos_por_cnpj.get(e["cnpj_completo"]), ""),
        }
        for e in empresas if e.get("cnpj_completo")
    }
    # Confere o texto ja montado; reprovado fica registrado e nao e enviado.
    montados = []
    for cnpj, email in emails_por_cnpj.items():
        m = montar_email_para_cnpj(template, cnpj, email,
                                   dados_empresas.get(cnpj, {}), org_id, remetente)
        montados.append({
            "cnpj": cnpj,
            "email": email,
            "saudacao": m["variaveis"].get("saudacao", ""),
            "assunto": m["assunto"],
            "corpo_texto": m["corpo_texto"],
            "corpo_html": m["corpo_html"],
        })
    conferencia = validar_lote(montados)
    for cnpj in conferencia["cnpjs_bloqueados"]:
        registrar_envio_campanha(campanha_id, cnpj, "email", status="bloqueado_conferencia")
        emails_por_cnpj.pop(cnpj, None)

    cnpjs = list(emails_por_cnpj.keys())
    resultado = enviar_campanha(campanha_id, template, cnpjs, emails_por_cnpj, dados_empresas, organizacao_id=org_id, remetente=remetente) \
        if cnpjs else {"sucessos": 0, "erros": 0}
    for cnpj in cnpjs:
        registrar_envio_campanha(campanha_id, cnpj, "email", status="enviado")
    resultado["conferencia"] = conferencia
    return resultado


@router.post("/campanhas/{campanha_id}/executar")
async def executar_campanha(campanha_id: int, current_user: Dict = Depends(get_current_user), org_id: int = Depends(get_active_org)):
    campanha = get_campanha(campanha_id, organizacao_id=org_id)
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    if campanha.get("status") not in _STATUS_EXECUTAVEIS:
        raise HTTPException(status_code=400, detail="Campanha ja concluida")
    # Disparo manual entra no mesmo teto diario do cron.
    return _executar_um_lote(campanha, current_user, org_id,
                             max_envios=_orcamento_email_hoje())


@router.post("/campanhas/{campanha_id}/pausar")
async def pausar_campanha(campanha_id: int, current_user: Dict = Depends(get_current_user),
                          org_id: int = Depends(get_active_org)):
    """Tira a campanha da fila sem apagar o historico de contatados."""
    campanha = get_campanha(campanha_id, organizacao_id=org_id)
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    if campanha.get("status") == "concluida":
        raise HTTPException(status_code=400, detail="Campanha ja concluida")
    update_campanha_status(campanha_id, "pausada")
    return {"ok": True, "status": "pausada"}


@router.post("/campanhas/{campanha_id}/retomar")
async def retomar_campanha(campanha_id: int, current_user: Dict = Depends(get_current_user),
                           org_id: int = Depends(get_active_org)):
    """Devolve a campanha para a fila."""
    campanha = get_campanha(campanha_id, organizacao_id=org_id)
    if not campanha:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    if campanha.get("status") != "pausada":
        raise HTTPException(status_code=400, detail="Campanha nao esta pausada")
    novo = "em_andamento" if campanha.get("ultimo_lote_em") else "agendada"
    update_campanha_status(campanha_id, novo)
    return {"ok": True, "status": novo}


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

    janela = _janela_de_envio()
    if not janela["aberta"]:
        return {"processadas": 0, "janela": janela, "resultados": []}

    # Fila: o orcamento do dia e' da CONTA inteira, nao por campanha. As
    # campanhas consomem em ordem ate acabar; as que nao couberem hoje ficam
    # 'em_andamento' e entram na proxima execucao do cron.
    orcamento = _orcamento_email_hoje()
    orcamento_inicial = orcamento

    # Teto da rodada, para nao gastar o orcamento do dia de uma vez.
    por_rodada = int(getattr(settings, "ENVIO_POR_RODADA", 10) or 0)
    if por_rodada > 0:
        orcamento = por_rodada if orcamento is None else min(orcamento, por_rodada)

    resultados = []
    for campanha in listar_campanhas_pendentes():
        try:
            r = _executar_um_lote(campanha, {"sub": "cron"}, campanha.get("organizacao_id"),
                                  max_envios=orcamento)
            if orcamento is not None and (campanha.get("canal") or "email") == "email":
                orcamento = max(orcamento - int(r.get("sucessos", 0) or 0), 0)
            resultados.append({"campanha_id": campanha["id"], "nome": campanha["nome"], **r})
        except Exception as e:
            resultados.append({"campanha_id": campanha["id"], "nome": campanha["nome"], "erro": str(e)})
    return {
        "processadas": len(resultados),
        "janela": janela,
        "limite_diario": int(getattr(settings, "EMAIL_LIMITE_DIARIO", 0) or 0),
        "por_rodada": por_rodada,
        "orcamento_dia_inicial": orcamento_inicial,
        "orcamento_rodada_restante": orcamento,
        "resultados": resultados,
    }
