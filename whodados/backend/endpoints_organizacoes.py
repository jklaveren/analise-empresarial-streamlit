"""WhoDados API Endpoints - Organizacoes (empresas do usuario).

Multi-tenant: cada usuario opera uma ou mais empresas (NRA / SYVP). Este
endpoint alimenta o seletor de empresa ativa no frontend. O isolamento em si
(qual empresa cada request opera) e' feito pela dependencia get_active_org via
header X-Org-Id."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from typing import Dict, List, Any
from .auth import get_current_user
from .db import listar_organizacoes_do_usuario, get_org_logo

router = APIRouter(prefix="/api/v1")


@router.get("/organizacoes")
async def minhas_organizacoes(current_user: Dict = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Lista as empresas que o usuario logado pode operar."""
    return listar_organizacoes_do_usuario(current_user["sub"])


@router.get("/organizacoes/{organizacao_id}/logo")
async def logo_organizacao(organizacao_id: int):
    """Endpoint publico (sem login) -- serve o logo da empresa para ser embutido
    na assinatura do e-mail, carregado pelo cliente de e-mail do destinatario."""
    row = get_org_logo(organizacao_id)
    if not row or not row.get("logo_data"):
        raise HTTPException(status_code=404, detail="Empresa sem logo")
    return Response(content=bytes(row["logo_data"]), media_type=row.get("logo_mime") or "image/png", headers={"Cache-Control": "public, max-age=300"})
