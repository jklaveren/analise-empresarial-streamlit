"""Auth Dependencies."""
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token nao fornecido", headers={"WWW-Authenticate": "Bearer"})
    from .service import decodificar_access_token
    payload = decodificar_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido ou expirado", headers={"WWW-Authenticate": "Bearer"})
    return payload

def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[Dict]:
    if not token:
        return None
    from .service import decodificar_access_token
    return decodificar_access_token(token)

def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return current_user


def get_active_org(
    current_user: Dict = Depends(get_current_user),
    x_org_id: Optional[int] = Header(None, alias="X-Org-Id"),
) -> int:
    """Empresa (organizacao) ativa da requisicao. O frontend manda o header
    'X-Org-Id'; validamos que o usuario tem acesso a ela. Se o header nao vier,
    cai na primeira empresa do usuario. Levanta 403 se o usuario nao tiver
    acesso aquela empresa (ou nenhuma). Centraliza a checagem de isolamento
    entre empresas -- todo endpoint de controle depende disto."""
    from ..db.service import listar_organizacoes_do_usuario, usuario_tem_acesso_org
    username = current_user["sub"]
    if x_org_id is not None:
        if not usuario_tem_acesso_org(username, x_org_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a esta empresa")
        return x_org_id
    orgs = listar_organizacoes_do_usuario(username)
    if not orgs:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario sem empresa vinculada")
    return orgs[0]["id"]
