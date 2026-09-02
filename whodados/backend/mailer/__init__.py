"""Mailer Module."""
from .service import enviar_email, enviar_campanha, enviar_template_para_cnpjs
from .templates import TEMPLATES_PADRAO
from .smtp_config import (
    get_smtp_config, test_smtp_connection, test_email_send,
    get_smtp_presets, SMTP_PRESETS
)
__all__ = [
    "enviar_email", "enviar_campanha", "enviar_template_para_cnpjs",
    "TEMPLATES_PADRAO",
    "get_smtp_config", "test_smtp_connection", "test_email_send",
    "get_smtp_presets", "SMTP_PRESETS",
]
