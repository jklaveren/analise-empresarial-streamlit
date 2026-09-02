"""
Endpoint de lead scoring — plugar em backend/main.py junto dos outros
routers (o mesmo lugar onde endpoints_part1.py e endpoints_part2.py
já são incluídos com app.include_router(...)).

    from backend.app.api.scoring import router as scoring_router
    app.include_router(scoring_router, prefix="/api/v1")
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.dependencies import get_current_user  # já existe no projeto
from backend.app.data.loader import carregar_empresa_detalhe  # já existe no projeto
from backend.app.ml.lead_scoring_service import ModeloIndisponivel, calcular_score

router = APIRouter(tags=["scoring"])


@router.get("/empresas/{cnpj}/score")
def obter_score(cnpj: str, usuario=Depends(get_current_user)):
    empresa = carregar_empresa_detalhe(cnpj)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    try:
        resultado = calcular_score(empresa)
    except ModeloIndisponivel as exc:
        # Cold start: devolve 200 com score nulo em vez de quebrar o
        # frontend — a badge de score simplesmente não aparece ainda.
        return {"cnpj": cnpj, "score": None, "faixa": None, "motivo": str(exc)}

    return {
        "cnpj": resultado.cnpj,
        "score": resultado.score,
        "faixa": resultado.faixa,
        "modelo_versao": resultado.modelo_versao,
    }
