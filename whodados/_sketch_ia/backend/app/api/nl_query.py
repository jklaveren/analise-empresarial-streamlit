"""
Endpoint de consulta em linguagem natural — mesmo padrão de inclusão do
scoring.py:

    from backend.app.api.nl_query import router as nl_query_router
    app.include_router(nl_query_router, prefix="/api/v1")
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.auth.dependencies import get_current_user
from backend.app.data.loader import filtrar_empresas  # já existe no projeto
from backend.app.nlp.nl_query_service import interpretar_pergunta, resumir_resultado
from backend.app.nlp.schemas import RespostaConsultaNatural
from backend.app.security.rate_limiter import limitar  # reaproveita o rate limiter existente

router = APIRouter(tags=["nl_query"])


class PerguntaRequest(BaseModel):
    pergunta: str


@router.post("/empresas/consulta-natural", response_model=RespostaConsultaNatural)
@limitar(por_minuto=10)  # chamadas de LLM custam dinheiro — limite mais baixo que os 60/min padrão
def consulta_natural(payload: PerguntaRequest, usuario=Depends(get_current_user)):
    if not payload.pergunta.strip():
        raise HTTPException(status_code=400, detail="Pergunta vazia")

    try:
        filtro = interpretar_pergunta(payload.pergunta)
    except Exception as exc:  # noqa: BLE001 — qualquer falha do LLM vira 502, não 500
        raise HTTPException(
            status_code=502, detail=f"Não consegui interpretar a pergunta: {exc}"
        )

    empresas = filtrar_empresas(
        uf=filtro.uf,
        municipio=filtro.municipio,
        cnae_prefixo=filtro.cnae_prefixo,
        porte=filtro.porte,
        capital_social_min=filtro.capital_social_min,
        capital_social_max=filtro.capital_social_max,
        divida_min=filtro.divida_min,
        divida_max=filtro.divida_max,
        ordenar_por=filtro.ordenar_por,
        ordem=filtro.ordem,
        limite=filtro.limite,
    )

    return RespostaConsultaNatural(
        pergunta_original=payload.pergunta,
        filtro_interpretado=filtro,
        total_encontrado=len(empresas),
        empresas=empresas,
        resumo_em_texto=resumir_resultado(payload.pergunta, filtro, len(empresas)),
    )
