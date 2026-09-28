"""Envio pela API do Gmail (HTTPS), alternativa ao SMTP.

O Render bloqueia saida SMTP nas portas 587 e 465; a API do Gmail fala 443.

Dois modos de autenticacao, nesta ordem:
1. OAuth com refresh token (GMAIL_OAUTH_*). Nao exige ser admin do
   Workspace -- a pessoa autoriza a propria conta uma vez.
2. Service account com delegacao no dominio (GMAIL_SERVICE_ACCOUNT_JSON).
   Exige superadmin, mas nao precisa de autorizacao por usuario.
"""
from __future__ import annotations

import base64
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from typing import Any, Dict, Optional

try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials as CredenciaisOAuth
    from google.auth.transport.requests import AuthorizedSession
except ImportError:
    service_account = None
    CredenciaisOAuth = None
    AuthorizedSession = None

try:
    from ..logger import get_logger
except ImportError:
    import logging
    get_logger = lambda x: logging.getLogger(x)

log = get_logger(__name__)

_ESCOPOS = ["https://www.googleapis.com/auth/gmail.send"]
_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_ENV = "GMAIL_SERVICE_ACCOUNT_JSON"
_ENV_OAUTH = ("GMAIL_OAUTH_CLIENT_ID", "GMAIL_OAUTH_CLIENT_SECRET", "GMAIL_OAUTH_REFRESH_TOKEN")


def _tem_oauth() -> bool:
    return all(os.environ.get(k) for k in _ENV_OAUTH) and CredenciaisOAuth is not None


def configurado() -> bool:
    return _tem_oauth() or (bool(os.environ.get(_ENV)) and service_account is not None)


def diagnostico() -> Dict[str, Any]:
    """Por que a API do Gmail esta (ou nao) ativa. Nao expoe valor nenhum."""
    return {
        "ativo": configurado(),
        "modo": "oauth" if _tem_oauth() else ("service_account" if configurado() else None),
        "biblioteca_google_auth": CredenciaisOAuth is not None,
        "envs_oauth_presentes": {k: bool(os.environ.get(k)) for k in _ENV_OAUTH},
        "env_service_account": bool(os.environ.get(_ENV)),
    }


def _credencial(remetente: str):
    """OAuth do usuario quando houver; senao service account delegada."""
    if _tem_oauth():
        cid, secret, refresh = (os.environ[k] for k in _ENV_OAUTH)
        return CredenciaisOAuth(
            token=None, refresh_token=refresh, client_id=cid, client_secret=secret,
            token_uri="https://oauth2.googleapis.com/token", scopes=_ESCOPOS,
        )
    info = json.loads(os.environ.get(_ENV, ""))
    cred = service_account.Credentials.from_service_account_info(info, scopes=_ESCOPOS)
    # subject precisa ser um usuario do dominio autorizado na delegacao.
    return cred.with_subject(remetente)


def enviar(
    para: str, assunto: str, corpo_html: str, corpo_texto: Optional[str],
    remetente: str, remetente_nome: Optional[str] = None,
) -> Dict[str, Any]:
    if not configurado():
        return {"sucesso": False, "erro": f"{_ENV} nao configurada"}
    if not remetente:
        return {"sucesso": False, "erro": "remetente nao definido"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"{remetente_nome} <{remetente}>" if remetente_nome else remetente
    msg["To"] = para
    msg_id = make_msgid(domain=remetente.split("@")[-1] or None)
    msg["Message-ID"] = msg_id
    if corpo_texto:
        msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    try:
        sessao = AuthorizedSession(_credencial(remetente))
        r = sessao.post(
            _ENDPOINT,
            json={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()},
            timeout=30,
        )
        if r.status_code >= 400:
            # O corpo do erro do Google diz o motivo real (delegacao faltando,
            # escopo errado, usuario inexistente).
            detalhe = (r.text or "")[:300]
            log.error(f"Gmail API {r.status_code} para {para}: {detalhe}")
            return {"sucesso": False, "para": para, "erro": f"Gmail API {r.status_code}: {detalhe}"}
        log.info(f"Email enviado via Gmail API para {para}: {assunto}")
        return {"sucesso": True, "para": para, "assunto": assunto, "message_id": msg_id}
    except Exception as e:
        log.error(f"Falha na Gmail API para {para}: {e}")
        return {"sucesso": False, "para": para, "erro": str(e)}
