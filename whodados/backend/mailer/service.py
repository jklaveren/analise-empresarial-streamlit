"""Mailer Service - WhoDados."""
from __future__ import annotations
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, List, Any

try:
    from ..config import settings
except ImportError:
    import os
    class _S:
        SMTP_HOST = os.getenv("SMTP_HOST", "")
        SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@whodados.com")
        EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "WhoDados")
    settings = _S()

try:
    from ..logger import get_logger
    from ..db.service import create_email_enviado, update_email_enviado, update_campanha_status, get_template, get_templates_by_categoria
    from ..classifier import classificar_cnae
except ImportError:
    import logging
    get_logger = lambda x: logging.getLogger(x)
    def noop(*a, **k): pass
    update_campanha_status = noop
    create_email_enviado = noop
    update_email_enviado = noop
    get_template = noop
    get_templates_by_categoria = noop
    def classificar_cnae(x): return "servicos"

log = get_logger(__name__)

# Temas por categoria CNAE (usados como variavel {{tema}})
CATEGORIA_TEMAS = {
    "tecnologia": "transformacao digital e inovacao tecnologica",
    "comercio": "otimizacao de vendas e gestao comercial",
    "industria": "gestao industrial e eficiencia operacional",
    "servicos": "gestao de servicos e crescimento de mercado",
    "todos": "inteligencia comercial e oportunidades de negocio",
}
CATEGORIA_DESCRICOES = {
    "tecnologia": "solucoes em tecnologia e inovacao",
    "comercio": "otimizacao para comercio e varejo",
    "industria": "solucoes para industria e construcao",
    "servicos": "gestao de servicos e mercado",
    "todos": "solucoes de negocio",
}


def _render_template(template: Dict, vars_dict: Dict[str, str]) -> Dict[str, str]:
    """Substitui {{variavel}} no assunto, corpo_html e corpo_texto."""
    resultado = {}
    for campo in ("assunto", "corpo_html", "corpo_texto"):
        texto = template.get(campo, "")
        if not texto:
            resultado[campo] = ""
            continue
        for key, val in vars_dict.items():
            texto = texto.replace("{{" + key + "}}", str(val))
        resultado[campo] = texto
    return resultado


def _obter_template_para_cnpj(template_base_id: int, cnae: Optional[str]) -> Dict[str, str]:
    """Escolhe o template correto para um CNPJ baseado no CNAE."""
    categoria = classificar_cnae(cnae) if cnae else "servicos"
    templates_categoria = get_templates_by_categoria(categoria)
    for t in templates_categoria:
        if t.get("categoria_cnae") == categoria and t.get("id") != template_base_id:
            return dict(t)
    base = get_template(template_base_id)
    if base:
        return dict(base)
    return templates_categoria[0] if templates_categoria else {}

def enviar_email(para: str, assunto: str, corpo_html: str, corpo_texto: Optional[str] = None) -> Dict[str, Any]:
    if not settings.SMTP_HOST:
        log.warning(f"SMTP nao configurado. Email simulado para {para}")
        return {"sucesso": True, "simulado": True, "para": para, "assunto": assunto}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        msg["To"] = para
        if corpo_texto:
            msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, [para], msg.as_string())
        log.info(f"Email enviado para {para}: {assunto}")
        return {"sucesso": True, "para": para, "assunto": assunto}
    except Exception as e:
        log.error(f"Erro ao enviar email para {para}: {e}")
        return {"sucesso": False, "para": para, "erro": str(e)}

def enviar_template_para_cnpjs(
    campanha_id: Optional[int],
    template: Dict,
    cnpjs: List[str],
    emails_por_cnpj: Dict[str, str],
    dados_empresas: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Envia template para CNPJs, escolhendo o template correto por CNAE."""
    resultados = {"sucessos": 0, "erros": 0, "enviados": [], "erros_list": []}
    if campanha_id:
        try:
            update_campanha_status(campanha_id, "em_andamento", total_destinatarios=len(cnpjs))
        except Exception:
            pass

    template_id_base = template.get("id") or template.get("template_id")
    dados_map = dados_empresas or {}

    for i, cnpj in enumerate(cnpjs):
        email_dest = emails_por_cnpj.get(cnpj, f"contato@{cnpj[:8]}.com")
        dados = dados_map.get(cnpj, {})
        cnae = dados.get("cnae_principal") or dados.get("cnae")
        categoria = classificar_cnae(cnae) if cnae else "servicos"

        tpl = _obter_template_para_cnpj(template_id_base, cnae) if template_id_base else template
        if not tpl:
            tpl = template

        empresa = dados.get("razao_social") or dados.get("nome_fantasia") or cnpj
        cidade = dados.get("municipio") or ""
        vars_dict = {
            "empresa": empresa,
            "cnpj": cnpj,
            "cidade": cidade,
            "cnae": cnae or "",
            "cnae_descricao": dados.get("cnae_descricao") or cnae or "",
            "tema": CATEGORIA_TEMAS.get(categoria, CATEGORIA_TEMAS["todos"]),
            "categoria": CATEGORIA_DESCRICOES.get(categoria, CATEGORIA_DESCRICOES["todos"]),
            "nome_fantasia": dados.get("nome_fantasia") or "",
            "porte": dados.get("porte_nome") or "",
            "imagem": tpl.get("imagem_url") or "",
        }
        rendered = _render_template(tpl, vars_dict)

        email_rec = None
        if campanha_id:
            try:
                email_rec = create_email_enviado(campanha_id, cnpj, email_dest, rendered.get("assunto", ""))
            except Exception:
                pass

        result = enviar_email(
            email_dest, rendered.get("assunto", ""),
            rendered.get("corpo_html", ""), rendered.get("corpo_texto"),
        )
        if result.get("sucesso"):
            resultados["sucessos"] += 1
            resultados["enviados"].append({
                "cnpj": cnpj, "email": email_dest,
                "template_usado": tpl.get("nome", ""),
                "categoria_cnae": categoria,
            })
            if email_rec and "id" in email_rec:
                try:
                    update_email_enviado(email_rec["id"], "enviado")
                except Exception:
                    pass
        else:
            resultados["erros"] += 1
            resultados["erros_list"].append({"cnpj": cnpj, "erro": result.get("erro", "desconhecido")})
            if email_rec and "id" in email_rec:
                try:
                    update_email_enviado(email_rec["id"], "erro", result.get("erro"))
                except Exception:
                    pass
        if i < len(cnpjs) - 1:
            time.sleep(0.05)

    if campanha_id:
        try:
            update_campanha_status(
                campanha_id, "concluida",
                enviados=resultados["sucessos"], erros=resultados["erros"],
            )
        except Exception:
            pass
    return resultados


def enviar_campanha(
    campanha_id: int,
    template: Dict,
    cnpjs: List[str],
    emails_por_cnpj: Dict[str, str],
    dados_empresas: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    return enviar_template_para_cnpjs(campanha_id, template, cnpjs, emails_por_cnpj, dados_empresas)
