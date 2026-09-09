"""
Sincroniza os CSVs gerados pelo pipeline para o banco Postgres (Supabase).
LOCAL: whodados/scripts/sync_data_to_db.py

Uso:
    DATABASE_URL="<connection-string>" python whodados/scripts/sync_data_to_db.py
"""
import sys
from pathlib import Path

# Adiciona a raiz do repo ao sys.path para encontrar database_config.py.
# parents[2] = raiz do repo (que contem whodados/).
_RAIZ = Path(__file__).resolve().parents[2]
for _caminho in (_RAIZ, _RAIZ / "analise-empresarial-streamlit"):
    if _caminho.exists() and str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import pandas as pd

from database_config import (
    EXPECTED_EMPRESA_COLUMNS,
    EXPECTED_SOCIO_COLUMNS,
    create_db_engine,
    criar_indices_dados,
    ensure_app_tables,
    garantir_colunas_obrigatorias,
    get_data_table_names,
    TABELA_MUNICIPIOS,
)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "pipeline" / "out"

ARQ_EMPRESAS = DATA_DIR / "subset_rs_final_completo.csv"
ARQ_SOCIOS = DATA_DIR / "socios_rs.csv"
ARQ_MUNICIPIOS = DATA_DIR / "municipios.csv"


def carregar_csvs():
    if not ARQ_EMPRESAS.exists() or not ARQ_SOCIOS.exists():
        faltantes = [str(p) for p in (ARQ_EMPRESAS, ARQ_SOCIOS) if not p.exists()]
        raise FileNotFoundError(
            "Arquivos de origem nao encontrados: "
            + ", ".join(faltantes)
            + ". Rode antes o pipeline (whodados/pipeline/pipeline.py)."
        )

    empresas = pd.read_csv(ARQ_EMPRESAS, sep=";", encoding="latin-1", dtype=str)
    socios = pd.read_csv(ARQ_SOCIOS, sep=";", encoding="utf-8", dtype=str)

    if empresas.empty:
        raise ValueError(f"'{ARQ_EMPRESAS.name}' esta vazio. Abortando.")
    if socios.empty:
        raise ValueError(f"'{ARQ_SOCIOS.name}' esta vazio. Abortando.")

    empresas = garantir_colunas_obrigatorias(empresas, EXPECTED_EMPRESA_COLUMNS)
    socios = garantir_colunas_obrigatorias(socios, EXPECTED_SOCIO_COLUMNS)

    return empresas, socios


def carregar_municipios():
    """Carrega o CSV de municipios, se existir. Nao e obrigatorio -- se
    faltar, a sincronizacao das empresas continua normalmente, so a coluna
    de cidade fica sem nome resolvido (o backend ja trata isso sem quebrar)."""
    if not ARQ_MUNICIPIOS.exists():
        print(f"[AVISO] '{ARQ_MUNICIPIOS.name}' nao encontrado, pulando tabela de municipios.")
        return None
    df = pd.read_csv(ARQ_MUNICIPIOS, sep=";", encoding="utf-8", dtype=str)
    if df.empty:
        print(f"[AVISO] '{ARQ_MUNICIPIOS.name}' esta vazio, pulando tabela de municipios.")
        return None
    df = df.rename(columns={"COD_MUNICIPIO": "cod_municipio", "NOME_MUNICIPIO": "nome_municipio"})
    return df[["cod_municipio", "nome_municipio"]]


def main():
    ensure_app_tables()
    engine = create_db_engine()
    tabelas = get_data_table_names()

    try:
        empresas, socios = carregar_csvs()
    except (FileNotFoundError, ValueError) as erro:
        print(f"Sincronizacao abortada: {erro}", file=sys.stderr)
        sys.exit(1)

    empresas.to_sql(tabelas["empresas"], engine, if_exists="replace", index=False, chunksize=5000)
    socios.to_sql(tabelas["socios"], engine, if_exists="replace", index=False, chunksize=5000)
    print(f"OK Tabela de empresas atualizada: {tabelas['empresas']} ({len(empresas)} linhas)")
    print(f"OK Tabela de socios atualizada: {tabelas['socios']} ({len(socios)} linhas)")

    municipios = carregar_municipios()
    if municipios is not None:
        municipios.to_sql(TABELA_MUNICIPIOS, engine, if_exists="replace", index=False, chunksize=5000)
        print(f"OK Tabela de municipios atualizada: {TABELA_MUNICIPIOS} ({len(municipios)} linhas)")

    criar_indices_dados()
    print("OK Indices recriados.")


if __name__ == "__main__":
    main()
