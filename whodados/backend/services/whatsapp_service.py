"""
Service de envio de WhatsApp via Twilio.

As credenciais sao POR EMPRESA (tabela integracao_configs, coluna
organizacao_id): cada empresa tem o proprio numero de WhatsApp. Uma linha
com organizacao_id NULL vale como fallback pra empresa que ainda nao
configurou a dela, e as variaveis de ambiente sao o ultimo recurso.
"""
import os
from typing import Optional

from twilio.rest import Client

_ENV = {
    "twilio_sid": "TWILIO_ACCOUNT_SID",
    "twilio_token": "TWILIO_AUTH_TOKEN",
    "twilio_wa_number": "TWILIO_WHATSAPP_NUMBER",
}


def _get_config(key: str, organizacao_id: Optional[int] = None) -> str:
    """Credencial da empresa; cai pra global (organizacao_id NULL) e depois
    pra env var."""
    try:
        from ..db.config import get_cur
        with get_cur() as cur:
            if organizacao_id is not None:
                cur.execute(
                    "SELECT value FROM integracao_configs WHERE key = %s AND organizacao_id = %s",
                    (key, organizacao_id),
                )
                r = cur.fetchone()
                if r and r["value"]:
                    return r["value"]
            cur.execute(
                "SELECT value FROM integracao_configs WHERE key = %s AND organizacao_id IS NULL",
                (key,),
            )
            r = cur.fetchone()
            if r and r["value"]:
                return r["value"]
    except Exception:
        pass
    return os.getenv(_ENV.get(key, ""), "")


def get_twilio_client(organizacao_id: Optional[int] = None):
    account_sid = _get_config("twilio_sid", organizacao_id)
    auth_token = _get_config("twilio_token", organizacao_id)
    if not all([account_sid, auth_token]):
        raise ValueError(
            "Credenciais do Twilio nao configuradas para esta empresa. "
            "Va em Configuracoes > Integracoes e salve SID e Auth Token."
        )
    return Client(account_sid, auth_token)


def get_twilio_auth_token(organizacao_id: Optional[int] = None) -> str:
    """Auth Token isolado (sem instanciar Client) -- usado so pra validar a
    assinatura das chamadas de webhook que o Twilio faz pra gente."""
    return _get_config("twilio_token", organizacao_id)


def get_numero_whatsapp(organizacao_id: Optional[int] = None) -> str:
    """Numero de WhatsApp desta empresa, so' com digitos."""
    return (_get_config("twilio_wa_number", organizacao_id) or "").lstrip("+")


def org_do_numero(numero: str) -> Optional[int]:
    """Qual empresa e' dona deste numero de WhatsApp.

    E' o que permite endereçar a mensagem RECEBIDA: o Twilio manda o numero
    de destino (o nosso) no campo 'To', e e' esse numero que diz de qual
    empresa e' a conversa. Sem isso toda mensagem recebida ficaria sem dono.
    """
    digitos = "".join(c for c in (numero or "") if c.isdigit())
    if not digitos:
        return None
    try:
        from ..db.config import get_cur
        with get_cur() as cur:
            cur.execute(
                """SELECT organizacao_id FROM integracao_configs
                   WHERE key = 'twilio_wa_number' AND organizacao_id IS NOT NULL
                     AND regexp_replace(value, '\\D', '', 'g') = %s
                   LIMIT 1""",
                (digitos,),
            )
            r = cur.fetchone()
            return r["organizacao_id"] if r else None
    except Exception:
        return None


def enviar_whatsapp(to_number: str, mensagem: str, organizacao_id: Optional[int] = None):
    """Envia WhatsApp pelo Twilio DA EMPRESA informada.

    Args:
        to_number: Numero no formato +55XXXXXXXXXX
        mensagem: Texto da mensagem
        organizacao_id: empresa remetente (decide credencial e numero de origem)

    Returns:
        dict com status e SID da mensagem enviada
    """
    client = get_twilio_client(organizacao_id)

    numero_origem = get_numero_whatsapp(organizacao_id) or "14155238886"
    from_number = f"whatsapp:+{numero_origem}"

    message = client.messages.create(
        body=mensagem,
        from_=from_number,
        to=f"whatsapp:{to_number}",
    )

    return {
        "status": "enviado",
        "sid": message.sid,
        "to": to_number,
        "from": numero_origem,
    }


def validar_whatsapp(to_number: str) -> bool:
    """Valida se o numero esta em formato correto (+55...)."""
    return to_number.startswith("+55") and len(to_number) >= 13
