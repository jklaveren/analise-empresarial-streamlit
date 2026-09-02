"""
Schema do filtro estruturado que o LLM deve produzir.

Ponto central da Opção 2: o modelo NUNCA gera SQL. Ele preenche este
schema (via structured output / tool use da API da Anthropic), o backend
valida com Pydantic e só então monta a query — usando a mesma função
filtrar_empresas() que o pipeline já usa internamente. Isso fecha a porta
pra SQL injection via prompt e mantém uma única fonte de verdade para as
regras de filtro (pipeline e chat usam o mesmo filtro).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

PORTES_VALIDOS = {"ME", "EPP", "DEMAIS"}


class FiltroEmpresas(BaseModel):
    uf: Optional[str] = Field(default="RS", description="Sempre RS nesta versão do produto")
    municipio: Optional[str] = Field(default=None, description="Nome do município, ex: Porto Alegre")
    cnae_prefixo: Optional[str] = Field(
        default=None, description="Prefixo do CNAE, ex: '47' para comércio varejista"
    )
    porte: Optional[Literal["ME", "EPP", "DEMAIS"]] = None
    capital_social_min: Optional[float] = None
    capital_social_max: Optional[float] = None
    divida_min: Optional[float] = None
    divida_max: Optional[float] = None
    ordenar_por: Literal["DIVIDA_TOTAL", "CAPITAL_SOCIAL", "DATA_FUNDACAO"] = "DIVIDA_TOTAL"
    ordem: Literal["asc", "desc"] = "desc"
    limite: int = Field(default=50, ge=1, le=200)

    @field_validator("cnae_prefixo")
    @classmethod
    def cnae_so_digitos(cls, v):
        if v is not None and not v.isdigit():
            raise ValueError("cnae_prefixo deve conter apenas dígitos")
        return v


class RespostaConsultaNatural(BaseModel):
    pergunta_original: str
    filtro_interpretado: FiltroEmpresas
    total_encontrado: int
    empresas: list[dict]
    resumo_em_texto: str
