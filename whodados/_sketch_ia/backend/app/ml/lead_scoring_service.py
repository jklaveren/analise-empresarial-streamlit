"""
Serviço de inferência do modelo de lead scoring.

Carrega o artefato treinado por train_lead_score.py uma única vez (padrão
lru_cache, igual ao backend/config.py já faz com Settings) e expõe uma
função simples de scoring para o endpoint FastAPI usar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

ARTIFACT_DIR = Path(__file__).parent / "artifacts" / "lead_score_v1"


@dataclass
class ScoreResult:
    cnpj: str
    score: float
    faixa: str
    modelo_versao: str
    features_usadas: dict


class ModeloIndisponivel(RuntimeError):
    """Levantado quando ainda não existe modelo treinado (cold start)."""


@lru_cache
def _carregar_modelo():
    model_path = ARTIFACT_DIR / "model.joblib"
    meta_path = ARTIFACT_DIR / "metadata.json"
    if not model_path.exists():
        raise ModeloIndisponivel(
            "Nenhum modelo treinado ainda. Rode train_lead_score.py depois "
            "de ter desfechos suficientes no CRM (status convertido/perdido)."
        )
    modelo = joblib.load(model_path)
    metadata = json.loads(meta_path.read_text())
    return modelo, metadata


def _faixa(score: float) -> str:
    if score >= 0.7:
        return "quente"
    if score >= 0.35:
        return "morno"
    return "frio"


def calcular_score(empresa_row: pd.Series) -> ScoreResult:
    """empresa_row vem do mesmo DataFrame que carregar_empresa_detalhe()
    já retorna em backend/app/data/loader.py — reaproveita as colunas que
    o endpoint /empresas/{cnpj} já monta, sem precisar de uma query nova.
    """
    modelo, metadata = _carregar_modelo()

    features = {
        "CAPITAL_SOCIAL": empresa_row.get("CAPITAL_SOCIAL", 0.0),
        "DIVIDA_TOTAL": empresa_row.get("DIVIDA_TOTAL", 0.0),
        "IDADE_EMPRESA_ANOS": empresa_row.get("IDADE_EMPRESA_ANOS", 0.0),
        "CNAE_PRINCIPAL": empresa_row.get("CNAE_PRINCIPAL", "desconhecido"),
        "PORTE": empresa_row.get("PORTE", "desconhecido"),
        "COD_MUNICIPIO": empresa_row.get("COD_MUNICIPIO", "desconhecido"),
    }
    X = pd.DataFrame([features])
    proba = float(modelo.predict_proba(X)[0, 1])

    return ScoreResult(
        cnpj=str(empresa_row.get("CNPJ_COMPLETO")),
        score=round(proba, 4),
        faixa=_faixa(proba),
        modelo_versao=metadata.get("trained_at", "desconhecida"),
        features_usadas=features,
    )
