"""Envio pela API do Gmail (HTTPS), alternativa ao SMTP.

O Render bloqueia saida SMTP nas portas 587 e 465, entao SMTP so' funciona
com provedor que ofereca porta alternativa. A API do Gmail fala 443.

Autentica por service account com delegacao em todo o dominio: a conta
assume (impersonate) o endereco remetente, sem OAuth interativo.
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
    from google.auth.transport.requests import AuthorizedSession
except ImportError:
    service_account = None
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


def configurado() -> bool:
    return bool(os.environ.get(_ENV)) and service_account is not None


def _credencial(remetente: str):
    """Credencial da service account assumindo o endereco remetente."""
    bruto = os.environ.get(_ENV, "")
    info = json.loads(bruto)
    cred = service_account.Credentials.from_service_account_info(info, scopes=_ESCOPOS)
    # subject = quem a conta de servico representa. Precisa ser um usuario do
    # dominio autorizado na delegacao, senao a API devolve 403.
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
