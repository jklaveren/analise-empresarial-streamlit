"""Auth Dependencies."""
from fastapi import Depends, HTTPException, status
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
