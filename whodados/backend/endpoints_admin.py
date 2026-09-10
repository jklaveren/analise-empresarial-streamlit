"""Admin Endpoints - WhoDados."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from .auth import get_current_user
from .mailer import (
    get_smtp_config, test_smtp_connection, test_email_send,
    get_smtp_presets
)
from typing import List, Optional
from .db import (
    get_pipeline_metadata, get_sla_config, set_sla_config,
    list_all_users, update_user_flags,
)
from .auth import criar_usuario, hash_senha
from .db.service import update_user_password
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


@router.get("/sistema/status")
async def get_sistema_status(current_user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Informacoes sobre a ultima atualizacao dos dados (Receita Federal /
    PGFN), pra tela "Sobre" em Configuracoes. Qualquer usuario logado pode
    ver -- nao e informacao sensivel, so status. Retorna tudo vazio/None se
    o pipeline de ETL nunca rodou ainda."""
    meta = get_pipeline_metadata()

    def valor(chave: str):
        item = meta.get(chave)
        return item["valor"] if item else None

    return {
        "mes_referencia_rf": valor("mes_referencia_rf"),
        "trimestre_pgfn": valor("trimestre_pgfn"),
        "gerado_em": valor("gerado_em"),
        "ultima_sincronizacao": valor("ultima_sincronizacao"),
        "total_matrizes": valor("total_matrizes"),
        "total_empresas_sincronizadas": valor("total_empresas_sincronizadas"),
        "total_socios_sincronizados": valor("total_socios_sincronizados"),
        "pipeline_ja_rodou": bool(meta),
    }


@router.get("/sla")
async def get_sla(current_user: Dict = Depends(get_current_user)) -> Dict[str, int]:
    """Prazos (em dias) que definem o semaforo do Monitor de e-mails.
    Qualquer usuario logado pode ver -- e so exibido na tela, nao e sensivel."""
    return get_sla_config()


@router.put("/sla")
async def update_sla(data: Dict, current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Atualiza os prazos do semaforo. So admin pode mudar -- afeta todo mundo."""
    try:
        verde = int(data.get("sla_verde_dias"))
        amarelo = int(data.get("sla_amarelo_dias"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="sla_verde_dias e sla_amarelo_dias precisam ser numeros inteiros")
    try:
        set_sla_config(verde, amarelo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"SLA do monitor atualizado por {current_user.get('sub')}: verde={verde}, amarelo={amarelo}")
    return get_sla_config()


def _serializar_usuario(u: Dict) -> Dict[str, Any]:
    return {
        "id": u["id"],
        "username": u["username"],
        "email": u.get("email"),
        "is_admin": bool(u.get("is_admin")),
        "is_active": bool(u.get("is_active", True)),
        "created_at": u["created_at"].isoformat() if u.get("created_at") else None,
    }


@router.get("/usuarios")
async def listar_usuarios(current_user: Dict = Depends(require_admin)) -> List[Dict[str, Any]]:
    """Lista todos os usuarios do sistema. So admin."""
    return [_serializar_usuario(u) for u in list_all_users()]


@router.post("/usuarios")
async def criar_novo_usuario(data: Dict, current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Cria um novo usuario. So admin."""
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip() or None
    is_admin = bool(data.get("is_admin", False))
    if not username or len(password) < 8:
        raise HTTPException(status_code=400, detail="Usuario obrigatorio e senha precisa ter ao menos 8 caracteres")
    try:
        user = criar_usuario(username, password, email, is_admin)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"Usuario '{username}' criado por {current_user.get('sub')}")
    return user


@router.patch("/usuarios/{user_id}")
async def atualizar_usuario(user_id: int, data: Dict, current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Ativa/desativa ou promove/remove admin de um usuario. So admin.
    Um admin nao pode remover o proprio acesso de admin nem se desativar
    (evita o sistema ficar sem nenhum admin por acidente)."""
    usuarios = list_all_users()
    alvo = next((u for u in usuarios if u["id"] == user_id), None)
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    is_admin = data.get("is_admin")
    is_active = data.get("is_active")

    if alvo["username"] == current_user.get("sub"):
        if is_admin is False:
            raise HTTPException(status_code=400, detail="Voce nao pode remover seu proprio acesso de admin")
        if is_active is False:
            raise HTTPException(status_code=400, detail="Voce nao pode desativar sua propria conta")

    ok = update_user_flags(
        user_id,
        is_admin=bool(is_admin) if is_admin is not None else None,
        is_active=bool(is_active) if is_active is not None else None,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Nada para atualizar")
    logger.info(f"Usuario '{alvo['username']}' atualizado por {current_user.get('sub')}: {data}")
    atualizado = next(u for u in list_all_users() if u["id"] == user_id)
    return _serializar_usuario(atualizado)


@router.post("/usuarios/{user_id}/redefinir-senha")
async def admin_redefinir_senha(user_id: int, data: Dict, current_user: Dict = Depends(require_admin)) -> Dict[str, Any]:
    """Admin redefine a senha de outro usuario direto (sem precisar saber a
    senha antiga) -- util quando alguem da equipe esquece a senha."""
    nova_senha = data.get("nova_senha") or ""
    if len(nova_senha) < 8:
        raise HTTPException(status_code=400, detail="A nova senha precisa ter ao menos 8 caracteres")
    usuarios = list_all_users()
    alvo = next((u for u in usuarios if u["id"] == user_id), None)
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    update_user_password(user_id, hash_senha(nova_senha))
    logger.info(f"Senha do usuario '{alvo['username']}' redefinida por {current_user.get('sub')}")
    return {"sucesso": True, "message": f"Senha de '{alvo['username']}' redefinida."}
