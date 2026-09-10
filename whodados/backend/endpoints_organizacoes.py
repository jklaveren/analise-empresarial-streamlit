"""WhoDados API Endpoints - Organizacoes (empresas do usuario).

Multi-tenant: cada usuario opera uma ou mais empresas (NRA / SYVP). Este
endpoint alimenta o seletor de empresa ativa no frontend. O isolamento em si
(qual empresa cada request opera) e' feito pela dependencia get_active_org via
header X-Org-Id."""
from fastapi import APIRouter, Depends
from typing import Dict, List, Any
from .auth import get_current_user
from .db import listar_organizacoes_do_usuario

router = APIRouter(prefix="/api/v1")


@router.get("/organizacoes")
async def minhas_organizacoes(current_user: Dict = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Lista as empresas que o usuario logado pode operar."""
    return listar_organizacoes_do_usuario(current_user["sub"])
