"""
database_config.py -- Configuracao e schema para sincronizar os dados
extraidos da Receita Federal / PGFN (whodados/pipeline/pipeline.py) com o
Postgres (Supabase).

Usado por whodados/scripts/sync_data_to_db.py, executado automaticamente
pelo GitHub Action em .github/workflows/whodados-etl.yml (ou manualmente
via "workflow_dispatch" na aba Actions do GitHub).

As tabelas de DADOS criadas aqui (dados_empresas, dados_socios, municipios)
sao distintas das tabelas da APLICACAO (crm, campanhas, notificacoes, etc.),
que sao criadas pelo backend FastAPI na inicializacao
(whodados/backend/db/config.py::ensure_tables_exist).
"""
from __future__ import annotations
import os

TABELA_EMPRESAS = "dados_empresas"
TABELA_SOCIOS = "dados_socios"
TABELA_MUNICIPIOS = "municipios"


def get_data_table_names() -> dict:
    """Nomes das tabelas de dados no Postgres."""
    return {"empresas": TABELA_EMPRESAS, "socios": TABELA_SOCIOS}


# Colunas produzidas por whodados/pipeline/pipeline.py::gerar_master()
# (arquivo out/subset_rs_final_completo.csv)
EXPECTED_EMPRESA_COLUMNS = [
    "CNPJ_BASICO", "CNPJ_COMPLETO", "RAZAO_SOCIAL", "NOME_FANTASIA",
    "DATA_FUNDACAO", "CNAE_PRINCIPAL", "LOGRADOURO", "NUMERO", "BAIRRO",
    "CEP", "COD_MUNICIPIO", "DDD", "TELEFONE", "EMAIL", "CONTATO_FONE",
    "CAPITAL_SOCIAL", "PORTE_EMPRESA", "PORTE_NOME", "DIVIDA_TOTAL",
]

# Colunas produzidas por whodados/pipeline/pipeline.py::filtrar_socios()
# (arquivo out/socios_rs.csv)
EXPECTED_SOCIO_COLUMNS = [
    "CNPJ_BASICO", "IDENTIFICADOR_SOCIO", "NOME_SOCIO",
    "CPF_CNPJ_SOCIO", "QUALIF_SOCIO",
]


def garantir_colunas_obrigatorias(df, colunas_esperadas):
    """Garante que o DataFrame tenha exatamente as colunas esperadas: cria
    como vazias (None) as que faltarem e mantem apenas as que estao na lista,
    na ordem esperada. Protege a sincronizacao contra mudancas de schema no
    CSV gerado pelo pipeline."""
    for col in colunas_esperadas:
        if col not in df.columns:
            df[col] = None
    return df[colunas_esperadas]


def create_db_engine():
    """Engine SQLAlchemy usado pelo pandas.DataFrame.to_sql() no script de
    sincronizacao. Requer a variavel de ambiente DATABASE_URL."""
    from sqlalchemy import create_engine

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL nao configurada. Defina a variavel de ambiente "
            "(no GitHub: Settings > Secrets and variables > Actions > "
            "Variables > SUPABASE_CONNECTION_STRING) antes de rodar a "
            "sincronizacao."
        )
    return create_engine(database_url, pool_pre_ping=True)


def ensure_app_tables() -> None:
    """Garante que a tabela de lookup de municipios exista antes da
    sincronizacao. Nao falha se DATABASE_URL nao estiver configurada --
    quem chama (sync_data_to_db.py) ja trata essa ausencia."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABELA_MUNICIPIOS} (
                    cod_municipio VARCHAR(10) PRIMARY KEY,
                    nome_municipio VARCHAR(200) NOT NULL
                )
                """
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def criar_indices_dados() -> None:
    """Cria indices nas tabelas de dados depois de recarregadas (to_sql com
    if_exists="replace" recria a tabela do zero a cada sincronizacao, entao
    os indices precisam ser recriados depois, nao antes)."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return
    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f'''CREATE INDEX IF NOT EXISTS idx_dados_empresas_cnpj_completo '''
                f'''ON {TABELA_EMPRESAS} ("CNPJ_COMPLETO")'''
            )
            cur.execute(
                f'''CREATE INDEX IF NOT EXISTS idx_dados_empresas_cnpj_basico '''
                f'''ON {TABELA_EMPRESAS} ("CNPJ_BASICO")'''
            )
            cur.execute(
                f'''CREATE INDEX IF NOT EXISTS idx_dados_socios_cnpj_basico '''
                f'''ON {TABELA_SOCIOS} ("CNPJ_BASICO")'''
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
