"""Admin Endpoints - WhoDados."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from .auth import get_current_user
from .mailer import (
    get_smtp_config, test_smtp_connection, test_email_send,
    get_smtp_presets
)
from .logger import get_logger
logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/admin")


def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


@router.get("/smtp/config")
async def get_smtp_status(current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Retorna configuracao atual de SMTP (sem a senha)."""
    return get_smtp_config()


@router.get("/smtp/presets")
async def list_presets(current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Lista provedores SMTP pre-configurados."""
    return {"presets": get_smtp_presets()}


@router.post("/smtp/test-connection")
async def test_connection(data: Dict, current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Testa conexao SMTP com os parametros fornecidos."""
    host = data.get("host", "").strip()
    port = data.get("port", 587)
    username = data.get("username", "").strip()
    password = data.get("password", "")
    use_tls = data.get("use_tls", True)

    if not host or not username or not password:
        raise HTTPException(status_code=400, detail="Host, username e password sao obrigatorios")

    logger.info(f"Testando conexao SMTP para {username}@{host}:{port}")
    return test_smtp_connection(host, port, username, password, use_tls)


@router.post("/smtp/test-send")
async def send_test_email(data: Dict, current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Envia e-mail de teste usando a configuracao atual."""
    para = data.get("para", "").strip()
    if not para or "@" not in para:
        raise HTTPException(status_code=400, detail="Email invalido")

    logger.info(f"Enviando e-mail de teste para {para}")
    return test_email_send(para)
