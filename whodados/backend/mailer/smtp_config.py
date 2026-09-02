"""SMTP Configuration Service - WhoDados."""
from __future__ import annotations
import os
import smtplib
from typing import Dict, Any

try:
    from ..config import settings
except ImportError:
    class _S:
        SMTP_HOST = os.getenv("SMTP_HOST", "")
        SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@whodados.com")
        EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "WhoDados")
        APP_ENV = os.getenv("APP_ENV", "development")
    settings = _S()

try:
    from ..logger import get_logger
except ImportError:
    import logging
    get_logger = lambda x: logging.getLogger(x)

log = get_logger(__name__)


def get_smtp_config() -> Dict[str, Any]:
    return {
        "smtp_host": settings.SMTP_HOST or "",
        "smtp_port": settings.SMTP_PORT,
        "smtp_username": settings.SMTP_USERNAME or "",
        "smtp_use_tls": settings.SMTP_USE_TLS,
        "email_from": settings.EMAIL_FROM or "",
        "email_from_name": settings.EMAIL_FROM_NAME or "",
        "configurado": bool(settings.SMTP_HOST and settings.SMTP_USERNAME),
        "is_production": settings.APP_ENV == "production",
    }


def test_smtp_connection(host: str, port: int, username: str, password: str, use_tls: bool = True) -> Dict[str, Any]:
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
        log.info(f"Teste SMTP bem-sucedido para {username}@{host}:{port}")
        return {"sucesso": True, "message": f"Conexao com {host}:{port} bem-sucedida!"}
    except smtplib.SMTPAuthenticationError:
        return {"sucesso": False, "message": "Falha na autenticacao. Verifique usuario e senha."}
    except smtplib.SMTPConnectError:
        return {"sucesso": False, "message": f"Nao foi possivel conectar a {host}:{port}."}
    except smtplib.SMTPException as e:
        return {"sucesso": False, "message": f"Erro SMTP: {str(e)}"}
    except Exception as e:
        return {"sucesso": False, "message": f"Erro: {str(e)}"}


def test_email_send(para: str) -> Dict[str, Any]:
    if not settings.SMTP_HOST:
        return {
            "sucesso": False,
            "message": "SMTP nao configurado. Defina SMTP_HOST, SMTP_USERNAME e SMTP_PASSWORD no .env"
        }
    from .service import enviar_email
    html_body = f"""
    <html><body style="font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #4f46e5;">Teste de Configuracao - WhoDados</h2>
    <p>Este e-mail de teste foi enviado com sucesso!</p>
    <p><strong>Detalhes da configuracao:</strong></p>
    <ul>
        <li>Servidor: {settings.SMTP_HOST}:{settings.SMTP_PORT}</li>
        <li>Usuario: {settings.SMTP_USERNAME}</li>
        <li>TLS: {'Sim' if settings.SMTP_USE_TLS else 'Nao'}</li>
    </ul>
    </body></html>"""
    result = enviar_email(para=para, assunto="[WhoDados] Teste de Configuracao", corpo_html=html_body, corpo_texto="Teste OK")
    if result.get("sucesso"):
        return {"sucesso": True, "message": f"E-mail de teste enviado para {para}", "detalhe": result}
    return {"sucesso": False, "message": f"Falha: {result.get('erro', 'Erro')}", "detalhe": result}


SMTP_PRESETS = {
    "gmail": {"name": "Gmail / Google Workspace", "host": "smtp.gmail.com", "port": 587, "tls": True, "note": "Requer Senhas de App (nao a senha normal)"},
    "outlook": {"name": "Outlook / Microsoft 365", "host": "smtp-mail.outlook.com", "port": 587, "tls": True, "note": "Use sua senha normal ou Senha de App"},
    "yahoo": {"name": "Yahoo Mail", "host": "smtp.mail.yahoo.com", "port": 587, "tls": True, "note": "Requer Senhas de App"},
    "sendgrid": {"name": "SendGrid", "host": "smtp.sendgrid.net", "port": 587, "tls": True, "note": "Use API Key como senha, username = apikey"},
    "mailgun": {"name": "Mailgun", "host": "smtp.mailgun.org", "port": 587, "tls": True, "note": "Use credenciais SMTP do painel Mailgun"},
    "amazon_ses": {"name": "Amazon SES", "host": "email-smtp.us-east-1.amazonaws.com", "port": 587, "tls": True, "note": "Use SMTP credentials do console AWS"},
    "zoho": {"name": "Zoho Mail", "host": "smtp.zoho.com", "port": 587, "tls": True, "note": "Para contas gratuitas e pagas"},
    "custom": {"name": "Servidor Personalizado", "host": "", "port": 587, "tls": True, "note": "Use qualquer provedor SMTP"},
}


def get_smtp_presets() -> Dict[str, Dict[str, Any]]:
    return SMTP_PRESETS
