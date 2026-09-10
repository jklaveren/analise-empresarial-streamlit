"""WhoDados API Endpoints - CRM (notas, status e kanban por CNPJ)."""
from fastapi import APIRouter, Depends
from typing import Dict
from .auth import get_current_user
from .db import (
    create_or_update_crm, get_crm_by_cnpj, get_crm_all,
    create_notificacao,
)

router = APIRouter(prefix="/api/v1")


@router.put("/crm/{cnpj}")
async def atualizar_crm(cnpj: str, data: Dict, current_user: Dict = Depends(get_current_user)):
    crm = create_or_update_crm(cnpj, status=data.get("status"), notas=data.get("notas"), criado_por=current_user.get("sub"))
    if data.get("status"):
        create_notificacao("status_mudou", f"CRM {data.get('status')}", f"CNPJ {cnpj}", user_id=current_user.get("sub"), cnpj=cnpj)
    return crm


@router.get("/crm/{cnpj}")
async def get_crm(cnpj: str, current_user: Dict = Depends(get_current_user)):
    return get_crm_by_cnpj(cnpj)


@router.get("/crm")
async def listar_crm(current_user: Dict = Depends(get_current_user)):
    registros = get_crm_all()
    kanban = {"novo": [], "em_contato": [], "negociando": [], "convertido": [], "descartado": []}
    for r in registros:
        s = r.get("status") or "novo"
        if s in kanban:
            kanban[s].append(r)
    return kanban
