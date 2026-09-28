"""Rastreamento proprio de abertura e clique.

Existe para nao depender do provedor: entrega e bounce so' o provedor sabe,
mas abertura e clique acontecem no NOSSO HTML -- um pixel e um link que
passa por nos antes do destino. Com isto, sair do Brevo (que tem webhook)
para SMTP do Gmail (que nao tem) custa so' entrega/bounce, nao a medicao
toda.

Assinatura: o id sozinho na URL seria falsificavel (ids sao sequenciais).
Cada link leva um HMAC curto derivado do SECRET_KEY. No clique, a URL de
destino entra no HMAC -- sem isso o redirecionador viraria open redirect,
util para phishing em cima do nosso dominio.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from typing import Optional
from urllib.parse import quote, urlencode

try:
    from ..config import settings
except ImportError:
    from backend.config import settings

_TAM_ASSINATURA = 16
# href="..." e href='...' apenas em http(s). Ancora, mailto: e tel: ficam
# de fora -- reescrever mailto quebraria o link de resposta.
_HREF = re.compile(r'href=(["\'])(https?://[^"\']+)\1', re.I)


def _segredo() -> bytes:
    return (getattr(settings, "SECRET_KEY", "") or "").encode()


def _assinar(mensagem: str) -> str:
    return hmac.new(_segredo(), mensagem.encode(), hashlib.sha256).hexdigest()[:_TAM_ASSINATURA]


def assinatura_abertura(email_id: int) -> str:
    return _assinar(f"abertura:{email_id}")


def assinatura_clique(email_id: int, url: str) -> str:
    return _assinar(f"clique:{email_id}:{url}")


def confere(assinatura: str, esperada: str) -> bool:
    """Comparacao em tempo constante."""
    return hmac.compare_digest(assinatura or "", esperada)


def _base() -> str:
    return (getattr(settings, "API_PUBLIC_URL", "") or "").rstrip("/")


def url_pixel(email_id: int) -> str:
    return f"{_base()}/api/v1/t/a/{email_id}/{assinatura_abertura(email_id)}.png"


def url_clique(email_id: int, destino: str) -> str:
    sig = assinatura_clique(email_id, destino)
    return f"{_base()}/api/v1/t/c/{email_id}/{sig}?{urlencode({'u': destino})}"


def injetar(corpo_html: str, email_id: Optional[int]) -> str:
    """Reescreve os links e acrescenta o pixel.

    Chamado depois de create_email_enviado (precisa do id) e antes do envio.
    Sem id ou sem API_PUBLIC_URL, devolve o HTML intacto -- rastreamento e'
    extra, nunca pode impedir o e-mail de sair.
    """
    if not email_id or not _base():
        return corpo_html

    def troca(m: re.Match) -> str:
        aspas, destino = m.group(1), m.group(2)
        # Nao reescreve o proprio descadastro: o link precisa funcionar
        # mesmo se o rastreamento estiver fora do ar.
        if "/descadastro" in destino:
            return m.group(0)
        return f'href={aspas}{url_clique(email_id, destino)}{aspas}'

    html = _HREF.sub(troca, corpo_html or "")
    pixel = (f'<img src="{url_pixel(email_id)}" width="1" height="1" '
             f'alt="" style="display:block;border:0;outline:none" />')
    return html + pixel
