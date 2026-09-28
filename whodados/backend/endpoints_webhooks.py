"""Webhook de eventos do Brevo: entrega, abertura, clique e bounce.

Desligado (403) sem BREVO_WEBHOOK_SECRET.
"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Any, Dict, List

from .config import settings
from .db import registrar_evento_email
from .logger import get_logger

router = APIRouter(prefix="/api/v1")
log = get_logger(__name__)

# Eventos que nos interessam. Os demais (request, unsubscribed, ...) sao
# aceitos com 200 e ignorados -- devolver erro faria o Brevo reenviar em loop.
_EVENTOS_TRATADOS = {
    "delivered", "opened", "unique_opened", "click",
    "hard_bounce", "soft_bounce", "blocked", "spam", "invalid_email", "deferred",
}


def _normalizar(evento_bruto: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai os campos do payload do Brevo (que usa 'message-id' com hifen)."""
    return {
        "evento": str(evento_bruto.get("event") or "").lower().strip(),
        "email": evento_bruto.get("email") or "",
        "message_id": evento_bruto.get("message-id") or evento_bruto.get("message_id"),
        "link": evento_bruto.get("link"),
        "motivo": evento_bruto.get("reason") or evento_bruto.get("error"),
    }


@router.post("/webhooks/brevo")
async def webhook_brevo(request: Request, token: str = Query("")):
    """Recebe eventos de e-mail do Brevo.

    O Brevo nao assina o corpo, entao a autenticacao e' um token no
    querystring -- a URL cadastrada la' ja' vai com ele.

    Sempre responde 200 quando o token confere, mesmo para evento
    desconhecido ou sem correspondencia no banco: qualquer outro codigo faz
    o Brevo reenviar o mesmo evento indefinidamente.
    """
    # Mensagens distintas de proposito: sem isso nao da' pra saber, de fora,
    # se o Render pegou a variavel ou se o token e' que esta errado. Nao
    # vaza o segredo -- so' diz se existe um configurado.
    esperado = getattr(settings, "BREVO_WEBHOOK_SECRET", "") or ""
    if not esperado:
        raise HTTPException(status_code=403,
                            detail="BREVO_WEBHOOK_SECRET nao configurado no servidor")
    if token != esperado:
        raise HTTPException(status_code=403, detail="Token de webhook invalido")

    try:
        corpo = await request.json()
    except Exception:
        return {"ok": True, "ignorados": 0, "motivo": "corpo nao e' JSON"}

    # O Brevo manda um objeto por evento, mas pode agrupar em lista.
    eventos: List[Dict[str, Any]] = corpo if isinstance(corpo, list) else [corpo]

    aplicados, ignorados = 0, 0
    for bruto in eventos:
        if not isinstance(bruto, dict):
            ignorados += 1
            continue
        dados = _normalizar(bruto)
        if dados["evento"] not in _EVENTOS_TRATADOS or not dados["email"]:
            ignorados += 1
            continue
        if registrar_evento_email(**dados):
            aplicados += 1
        else:
            ignorados += 1

    if ignorados:
        log.info(f"webhook brevo: {aplicados} aplicados, {ignorados} ignorados")
    return {"ok": True, "aplicados": aplicados, "ignorados": ignorados}
