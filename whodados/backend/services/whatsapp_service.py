"""
Service de envio de WhatsApp via Twilio.
Usa as credenciais armazenadas no banco (tabela integracao_configs).
Falls back para variáveis de ambiente se não tiver no banco.
"""
import os
from twilio.rest import Client


def _get_config(key: str) -> str:
    """Busca uma credencial no banco (integracao_configs) ou nas env vars como fallback."""
    try:
        from ..db.config import get_cur
        with get_cur() as cur:
            cur.execute("SELECT value FROM integracao_configs WHERE key = %s", (key,))
            r = cur.fetchone()
            if r and r["value"]:
                return r["value"]
    except Exception:
        pass
    env_map = {
        "twilio_sid": "TWILIO_ACCOUNT_SID",
        "twilio_token": "TWILIO_AUTH_TOKEN",
        "twilio_wa_number": "TWILIO_WHATSAPP_NUMBER",
    }
    return os.getenv(env_map.get(key, ""), "")


def get_twilio_client():
    account_sid = _get_config("twilio_sid")
    auth_token = _get_config("twilio_token")
    if not all([account_sid, auth_token]):
        raise ValueError(
            "Credenciais do Twilio nao configuradas. "
            "Va em Configuracoes > Integracoes e salve SID e Auth Token."
        )
    return Client(account_sid, auth_token)


def enviar_whatsapp(to_number: str, mensagem: str):
    """
    Envia WhatsApp via Twilio.

    Args:
        to_number: Numero no formato +55XXXXXXXXXX
        mensagem: Texto da mensagem

    Returns:
        dict com status e SID da mensagem enviada
    """
    client = get_twilio_client()

    numero_origem = _get_config("twilio_wa_number") or "14155238886"
    from_number = f"whatsapp:+{numero_origem.lstrip('+')}"

    message = client.messages.create(
        body=mensagem,
        from_=from_number,
        to=f"whatsapp:{to_number}"
    )

    return {
        "status": "enviado",
        "sid": message.sid,
        "to": to_number
    }


def validar_whatsapp(to_number: str) -> bool:
    """Valida se o numero esta em formato correto (+55...)."""
    return to_number.startswith("+55") and len(to_number) >= 13