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

def _smtp_da_org(organizacao_id: Optional[int]) -> Dict[str, Any]:
    """Config SMTP efetiva: a da empresa (se configurada) ou a global (.env)."""
    if organizacao_id is not None:
        try:
            from ..db.service import get_org_smtp_config
            cfg = get_org_smtp_config(organizacao_id, incluir_password=True)
        except Exception as e:
            log.warning(f"Falha lendo SMTP da empresa {organizacao_id}, usando global: {e}")
            cfg = None
        if cfg and cfg.get("configurado"):
            return {
                "host": cfg.get("smtp_host"),
                "port": cfg.get("smtp_port") or 587,
                "username": cfg.get("smtp_username"),
                "password": cfg.get("smtp_password"),
                "use_tls": cfg.get("smtp_use_tls", True),
                "email_from": cfg.get("email_from") or settings.EMAIL_FROM,
                "email_from_name": cfg.get("email_from_name") or settings.EMAIL_FROM_NAME,
            }
    return {
        "host": settings.SMTP_HOST, "port": settings.SMTP_PORT,
        "username": settings.SMTP_USERNAME, "password": settings.SMTP_PASSWORD,
        "use_tls": settings.SMTP_USE_TLS,
        "email_from": settings.EMAIL_FROM, "email_from_name": settings.EMAIL_FROM_NAME,
    }


def enviar_email(para: str, assunto: str, corpo_html: str, corpo_texto: Optional[str] = None, smtp: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = smtp or _smtp_da_org(None)
    if not cfg.get("host"):
        log.warning(f"SMTP nao configurado. Email simulado para {para}")
        return {"sucesso": True, "simulado": True, "para": para, "assunto": assunto}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = f"{cfg.get('email_from_name')} <{cfg.get('email_from')}>"
        msg["To"] = para
        if corpo_texto:
            msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP(cfg.get("host"), cfg.get("port") or 587) as server:
            if cfg.get("use_tls"):
                server.starttls()
            if cfg.get("username") and cfg.get("password"):
                server.login(cfg.get("username"), cfg.get("password"))
            server.sendmail(cfg.get("email_from"), [para], msg.as_string())
        log.info(f"Email enviado para {para}: {assunto}")
        return {"sucesso": True, "para": para, "assunto": assunto}
    except Exception as e:
        log.error(f"Erro ao enviar email para {para}: {e}")
        return {"sucesso": False, "para": para, "erro": str(e)}

def _assinatura_da_org(organizacao_id: Optional[int]) -> str:
    """HTML da assinatura da empresa, com {{logo}} resolvido para a URL publica
    do logo. Vazio se a empresa nao tiver assinatura."""
    if organizacao_id is None:
        return ""
    try:
        from ..db.service import get_org_smtp_config
        cfg = get_org_smtp_config(organizacao_id)
        assinatura = (cfg or {}).get("assinatura_html") or ""
    except Exception:
        return ""
    if not assinatura:
        return ""
    try:
        base = getattr(settings, "API_PUBLIC_URL", "") or ""
    except Exception:
        base = ""
    return assinatura.replace("{{logo}}", f"{base}/api/v1/organizacoes/{organizacao_id}/logo")


def enviar_template_para_cnpjs(
    campanha_id: Optional[int],
    template: Dict,
    cnpjs: List[str],
    emails_por_cnpj: Dict[str, str],
    dados_empresas: Optional[Dict[str, Dict[str, str]]] = None,
    organizacao_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Envia template para CNPJs, escolhendo o template correto por CNAE.
    Usa o SMTP e a assinatura da empresa (organizacao_id)."""
    resultados = {"sucessos": 0, "erros": 0, "enviados": [], "erros_list": []}
    smtp_cfg = _smtp_da_org(organizacao_id)
    assinatura = _assinatura_da_org(organizacao_id)
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
            rendered.get("corpo_html", "") + assinatura, rendered.get("corpo_texto"),
            smtp=smtp_cfg,
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
    organizacao_id: Optional[int] = None,
) -> Dict[str, Any]:
    return enviar_template_para_cnpjs(campanha_id, template, cnpjs, emails_por_cnpj, dados_empresas, organizacao_id=organizacao_id)


def enviar_email_teste(para: str, template: Dict, organizacao_id: Optional[int] = None) -> Dict[str, Any]:
    """Envia UM e-mail de teste com o template renderizado (valores de exemplo),
    usando o SMTP e a assinatura da empresa -- para a pessoa conferir como o
    e-mail vai chegar antes de disparar a campanha."""
    smtp_cfg = _smtp_da_org(organizacao_id)
    assinatura = _assinatura_da_org(organizacao_id)
    vars_amostra = {
        "empresa": "Empresa Exemplo LTDA", "cnpj": "00000000000000",
        "cidade": "Porto Alegre", "cnae": "", "cnae_descricao": "",
        "tema": CATEGORIA_TEMAS["todos"], "categoria": CATEGORIA_DESCRICOES["todos"],
        "nome_fantasia": "Exemplo", "porte": "", "imagem": template.get("imagem_url") or "",
    }
    rendered = _render_template(template, vars_amostra)
    assunto = "[TESTE] " + (rendered.get("assunto", "") or "Sem assunto")
    return enviar_email(
        para, assunto,
        rendered.get("corpo_html", "") + assinatura, rendered.get("corpo_texto"),
        smtp=smtp_cfg,
    )
