"""
Treino do modelo de lead scoring do WhoDados.

Ideia central
--------------
O CRM já guarda, para cada CNPJ que algum dia entrou no kanban, um `status`
(ex.: "novo", "em_contato", "convertido", "perdido"). Isso é o rótulo que
falta pra virar um problema de ML supervisionado: dado o perfil da empresa
(dados públicos do pipeline), prever a probabilidade de ela virar cliente.

Isso resolve o problema de "não tenho dataset rotulado" citado no plano de
carreira: o rótulo nasce do seu próprio uso do produto, não precisa vir de
fora. A limitação (documentada abaixo, seção "Vieses") é que só aprendemos
com empresas que alguém já trabalhou no CRM — cold start é esperado nos
primeiros meses de coleta.

Rodar:
    python -m backend.app.ml.train_lead_score \
        --csv whodados/pipeline/out/subset_rs_final_completo.csv \
        --database-url $DATABASE_URL \
        --out backend/app/ml/artifacts/lead_score_v1

Saída:
    lead_score_v1/model.joblib       — pipeline sklearn treinado
    lead_score_v1/metadata.json      — features, métricas, data de treino
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Mesmas colunas que backend/app/data/loader.py já expõe a partir do CSV do
# pipeline — ver whodados/pipeline/pipeline.py::gerar_master().
NUMERIC_FEATURES = [
    "CAPITAL_SOCIAL",
    "DIVIDA_TOTAL",
    "IDADE_EMPRESA_ANOS",  # derivada de DATA_FUNDACAO, calculada abaixo
]
CATEGORICAL_FEATURES = [
    "CNAE_PRINCIPAL",
    "PORTE",
    "COD_MUNICIPIO",
]
TARGET_STATUSES_POSITIVE = {"convertido", "cliente", "ganho"}
TARGET_STATUSES_NEGATIVE = {"perdido", "descartado", "sem_interesse"}
# Registros com status "novo" / "em_contato" / NULL ficam de fora do treino:
# ainda não têm desfecho, não são nem exemplo positivo nem negativo.


@dataclass
class TrainMetrics:
    n_treino: int
    n_teste: int
    n_positivos: int
    n_negativos: int
    roc_auc: float
    average_precision: float
    trained_at: str
    features_numericas: list
    features_categoricas: list


def carregar_dataset(csv_path: str, database_url: str) -> pd.DataFrame:
    """Junta o CSV de empresas (saída do pipeline) com os status do CRM.

    Em produção isso troca para uma query direta no Supabase
    (empresas JOIN crm), mas manter o CSV como fonte permite rodar o
    treino localmente sem depender do banco de produção.
    """
    empresas = pd.read_csv(csv_path, dtype={"CNPJ_COMPLETO": str})

    # backend/app/db/service.py já tem get_audit_logs / CRUDs de crm —
    # aqui reaproveitamos a mesma connection string.
    import psycopg2

    with psycopg2.connect(database_url) as conn:
        crm = pd.read_sql(
            "SELECT cnpj, status FROM crm WHERE status IS NOT NULL", conn
        )

    df = empresas.merge(crm, left_on="CNPJ_COMPLETO", right_on="cnpj", how="inner")

    df["DATA_FUNDACAO"] = pd.to_datetime(df["DATA_FUNDACAO"], errors="coerce")
    hoje = pd.Timestamp.now(tz=None)
    df["IDADE_EMPRESA_ANOS"] = (hoje - df["DATA_FUNDACAO"]).dt.days / 365.25

    status_norm = df["status"].str.lower().str.strip()
    df["label"] = np.select(
        [status_norm.isin(TARGET_STATUSES_POSITIVE), status_norm.isin(TARGET_STATUSES_NEGATIVE)],
        [1, 0],
        default=np.nan,
    )
    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)
    return df


def construir_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", min_frequency=10),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    modelo = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        random_state=42,
    )
    return Pipeline(steps=[("pre", pre), ("modelo", modelo)])


def treinar(df: pd.DataFrame) -> tuple[Pipeline, TrainMetrics]:
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    pipe = construir_pipeline()
    pipe.fit(X_train, y_train)

    proba = pipe.predict_proba(X_test)[:, 1]
    metrics = TrainMetrics(
        n_treino=len(X_train),
        n_teste=len(X_test),
        n_positivos=int(y.sum()),
        n_negativos=int((y == 0).sum()),
        roc_auc=float(roc_auc_score(y_test, proba)),
        average_precision=float(average_precision_score(y_test, proba)),
        trained_at=datetime.now(timezone.utc).isoformat(),
        features_numericas=NUMERIC_FEATURES,
        features_categoricas=CATEGORICAL_FEATURES,
    )
    print(classification_report(y_test, proba > 0.5))
    return pipe, metrics


def salvar(pipe: Pipeline, metrics: TrainMetrics, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out / "model.joblib")
    (out / "metadata.json").write_text(json.dumps(asdict(metrics), indent=2, ensure_ascii=False))
    print(f"Modelo salvo em {out}/model.joblib")
    print(f"ROC-AUC: {metrics.roc_auc:.3f} | AP: {metrics.average_precision:.3f}")
    print(f"Positivos: {metrics.n_positivos} | Negativos: {metrics.n_negativos}")
    if metrics.n_positivos < 30:
        print(
            "\n⚠️  Menos de 30 exemplos positivos. O modelo vai funcionar, mas "
            "trate isso como cold-start: até acumular mais desfechos reais no "
            "CRM, use o score como um sinal a mais, não como verdade absoluta."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--out", default="backend/app/ml/artifacts/lead_score_v1")
    args = parser.parse_args()

    dataset = carregar_dataset(args.csv, args.database_url)
    modelo, metricas = treinar(dataset)
    salvar(modelo, metricas, args.out)
