"""Consultas de analytics -- agregacoes sobre dados_empresas / dados_socios.

Tudo agregado no Postgres (GROUP BY / JOIN), nao no cliente: os numeros
refletem a base inteira, nao so as primeiras N linhas carregadas na tela.

Reconstroi o que o app legado (LegadoStream) fazia em pandas:
Home (KPIs), Foco por Cidade, Radar de Setores, Mapa de Passivos e
Analise de Socios.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

try:
    from .config import get_db_cursor
except ImportError:  # execucao fora do pacote
    from backend.db.config import get_db_cursor
try:
    from ..logger import get_logger
except ImportError:  # pragma: no cover
    import logging
    get_logger = lambda x: logging.getLogger(x)  # noqa: E731

log = get_logger(__name__)

# Empresas cuja razao social indica falencia / recuperacao judicial / baixa.
# Mesma lista do legado (app_main.py::BLACK_LIST). Excluidas por padrao.
_REGEX_INATIVAS = r"RECUPERACAO|FALIDA|JUDICIAL|MASSA FALIDA|EM LIQUIDACAO|BAIXADA|INAPTA"

# FROM comum a todas as consultas: empresa + nome do municipio + descricao do CNAE.
_BASE_FROM = """
    FROM dados_empresas e
    LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
    LEFT JOIN cnaes c ON c.codigo_cnae = e."CNAE_PRINCIPAL"
"""

# ::text antes de NULLIF cobre os dois casos: coluna de texto (o normal, o
# pandas.to_sql grava tudo como texto) e coluna ja numerica.
_CAPITAL = 'COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, \'\')::numeric, 0)'
_DIVIDA = 'COALESCE(NULLIF(e."DIVIDA_TOTAL"::text, \'\')::numeric, 0)'

# PORTE_NOME nao existe mais na tabela -- e derivado do PORTE_EMPRESA (codigo).
# Espelha o mapeamento antigo do pipeline pra manter a API igual pro frontend.
# (Mesma expressao vive em service.py; duplicada aqui pra manter cada modulo
# self-contained -- se um dia forem consolidar, mover pra config.py.)
_PORTE_NOME_SQL = (
    "CASE e.\"PORTE_EMPRESA\" "
    "WHEN '01' THEN 'NAO INFORMADO' "
    "WHEN '02' THEN 'ME' "
    "WHEN '03' THEN 'EPP' "
    "WHEN '05' THEN 'MEDIO E GRANDE' "
    "ELSE 'DEMAIS' END"
)
_PORTE_NOME_TO_CODE = {
    "NAO INFORMADO": "01",
    "ME": "02",
    "EPP": "03",
    "MEDIO E GRANDE": "05",
}


def _tabela_existe(cur, nome: str) -> bool:
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_name = %s) AS existe",
        (nome,),
    )
    row = cur.fetchone()
    return bool(row and row["existe"])


def _filtros_sql(
    cidades: Optional[List[str]] = None,
    cnaes: Optional[List[str]] = None,
    portes: Optional[List[str]] = None,
    divida_min: Optional[float] = None,
    divida_max: Optional[float] = None,
    capital_min: Optional[float] = None,
    capital_max: Optional[float] = None,
    incluir_inativas: bool = False,
) -> tuple[str, list]:
    """Monta o trecho ' AND ...' compartilhado por todas as agregacoes.

    Espelha os filtros da sidebar do legado: cidade, CNAE, porte, faixa de
    passivo, faixa de capital social e o toggle de falencia/recuperacao."""
    cond: List[str] = []
    params: list = []

    if cidades:
        cond.append("m.nome_municipio = ANY(%s)")
        params.append(list(cidades))
    if cnaes:
        cond.append('e."CNAE_PRINCIPAL" = ANY(%s)')
        params.append(list(cnaes))
    if portes:
        # Frontend manda nomes ('ME', 'EPP', ...); a tabela guarda so o
        # codigo. Traduz de volta.
        codigos = [_PORTE_NOME_TO_CODE[p] for p in portes if p in _PORTE_NOME_TO_CODE]
        if codigos:
            cond.append('e."PORTE_EMPRESA" = ANY(%s)')
            params.append(codigos)
    if divida_min is not None:
        cond.append(f"{_DIVIDA} >= %s")
        params.append(divida_min)
    if divida_max is not None:
        cond.append(f"{_DIVIDA} <= %s")
        params.append(divida_max)
    if capital_min is not None:
        cond.append(f"{_CAPITAL} >= %s")
        params.append(capital_min)
    if capital_max is not None:
        cond.append(f"{_CAPITAL} <= %s")
        params.append(capital_max)
    if not incluir_inativas:
        cond.append('COALESCE(e."RAZAO_SOCIAL", \'\') !~* %s')
        params.append(_REGEX_INATIVAS)

    return ((" AND " + " AND ".join(cond)) if cond else ""), params


def _vazio(cur) -> bool:
    return not _tabela_existe(cur, "dados_empresas")


# ==================== KPIs (Home) ====================

def analytics_resumo(**filtros) -> Dict[str, Any]:
    """Indicadores-chave da base filtrada (equivale aos 8 KPIs da Home)."""
    zero = {
        "total_empresas": 0, "divida_total": 0.0, "capital_total": 0.0,
        "divida_media": 0.0, "capital_medio": 0.0, "qtd_cidades": 0,
        "qtd_setores": 0, "qtd_com_divida": 0, "qtd_inativas": 0,
    }
    try:
        with get_db_cursor() as cur:
            if _vazio(cur):
                return zero
            where, params = _filtros_sql(**filtros)
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_empresas,
                    COALESCE(SUM({_DIVIDA}), 0) AS divida_total,
                    COALESCE(SUM({_CAPITAL}), 0) AS capital_total,
                    COALESCE(AVG({_DIVIDA}), 0) AS divida_media,
                    COALESCE(AVG({_CAPITAL}), 0) AS capital_medio,
                    COUNT(DISTINCT e."COD_MUNICIPIO") AS qtd_cidades,
                    COUNT(DISTINCT e."CNAE_PRINCIPAL") AS qtd_setores,
                    COUNT(*) FILTER (WHERE {_DIVIDA} > 0) AS qtd_com_divida
                {_BASE_FROM}
                WHERE 1=1 {where}
                """,
                params,
            )
            row = cur.fetchone() or {}

            # contagem separada de inativas (ignora o proprio toggle)
            where_i, params_i = _filtros_sql(**{**filtros, "incluir_inativas": True})
            cur.execute(
                f'SELECT COUNT(*) AS n {_BASE_FROM} '
                f'WHERE COALESCE(e."RAZAO_SOCIAL", \'\') ~* %s {where_i}',
                [_REGEX_INATIVAS, *params_i],
            )
            inativas = (cur.fetchone() or {}).get("n", 0)

            return {
                "total_empresas": int(row.get("total_empresas") or 0),
                "divida_total": float(row.get("divida_total") or 0),
                "capital_total": float(row.get("capital_total") or 0),
                "divida_media": float(row.get("divida_media") or 0),
                "capital_medio": float(row.get("capital_medio") or 0),
                "qtd_cidades": int(row.get("qtd_cidades") or 0),
                "qtd_setores": int(row.get("qtd_setores") or 0),
                "qtd_com_divida": int(row.get("qtd_com_divida") or 0),
                "qtd_inativas": int(inativas or 0),
            }
    except Exception as e:
        log.warning(f"analytics_resumo falhou: {e}")
        return zero


# ==================== Foco por Cidade ====================

def analytics_por_cidade(limite: int = 20, **filtros) -> List[Dict[str, Any]]:
    try:
        with get_db_cursor() as cur:
            if _vazio(cur):
                return []
            where, params = _filtros_sql(**filtros)
            cur.execute(
                f"""
                SELECT
                    COALESCE(m.nome_municipio, 'Nao mapeado') AS cidade,
                    COUNT(*) AS qtd,
                    COALESCE(SUM({_CAPITAL}), 0) AS capital_total,
                    COALESCE(SUM({_DIVIDA}), 0) AS divida_total
                {_BASE_FROM}
                WHERE 1=1 {where}
                GROUP BY cidade
                ORDER BY divida_total DESC
                LIMIT %s
                """,
                [*params, limite],
            )
            return [
                {
                    "cidade": r["cidade"],
                    "qtd": int(r["qtd"]),
                    "capital_total": float(r["capital_total"]),
                    "divida_total": float(r["divida_total"]),
                }
                for r in cur.fetchall()
            ]
    except Exception as e:
        log.warning(f"analytics_por_cidade falhou: {e}")
        return []


# ==================== Radar de Setores ====================

def analytics_por_setor(limite: int = 20, **filtros) -> List[Dict[str, Any]]:
    try:
        with get_db_cursor() as cur:
            if _vazio(cur):
                return []
            where, params = _filtros_sql(**filtros)
            cur.execute(
                f"""
                SELECT
                    e."CNAE_PRINCIPAL" AS cnae,
                    COALESCE(MAX(c.descricao_cnae), 'Outras atividades') AS descricao,
                    COUNT(*) AS qtd,
                    COALESCE(SUM({_CAPITAL}), 0) AS capital_total,
                    COALESCE(SUM({_DIVIDA}), 0) AS divida_total,
                    COALESCE(AVG({_DIVIDA}), 0) AS divida_media
                {_BASE_FROM}
                WHERE 1=1 {where}
                GROUP BY e."CNAE_PRINCIPAL"
                ORDER BY capital_total DESC
                LIMIT %s
                """,
                [*params, limite],
            )
            return [
                {
                    "cnae": r["cnae"],
                    "descricao": r["descricao"],
                    "qtd": int(r["qtd"]),
                    "capital_total": float(r["capital_total"]),
                    "divida_total": float(r["divida_total"]),
                    "divida_media": float(r["divida_media"]),
                }
                for r in cur.fetchall()
            ]
    except Exception as e:
        log.warning(f"analytics_por_setor falhou: {e}")
        return []


def analytics_por_porte(**filtros) -> List[Dict[str, Any]]:
    try:
        with get_db_cursor() as cur:
            if _vazio(cur):
                return []
            where, params = _filtros_sql(**filtros)
            cur.execute(
                f"""
                SELECT ({_PORTE_NOME_SQL}) AS porte,
                       COUNT(*) AS qtd
                {_BASE_FROM}
                WHERE 1=1 {where}
                GROUP BY porte
                ORDER BY qtd DESC
                """,
                params,
            )
            return [{"porte": r["porte"], "qtd": int(r["qtd"])} for r in cur.fetchall()]
    except Exception as e:
        log.warning(f"analytics_por_porte falhou: {e}")
        return []


# ==================== Top empresas (rankings) ====================

def analytics_top_empresas(
    ordenar_por: str = "divida", limite: int = 10, **filtros
) -> List[Dict[str, Any]]:
    """Maiores empresas por 'divida' ou 'capital' (rankings da Home / Passivos)."""
    coluna = _CAPITAL if ordenar_por == "capital" else _DIVIDA
    try:
        with get_db_cursor() as cur:
            if _vazio(cur):
                return []
            where, params = _filtros_sql(**filtros)
            cur.execute(
                f"""
                SELECT
                    e."CNPJ_COMPLETO" AS cnpj_completo,
                    e."RAZAO_SOCIAL" AS razao_social,
                    COALESCE(m.nome_municipio, '') AS municipio,
                    e."CNAE_PRINCIPAL" AS cnae_principal,
                    COALESCE(c.descricao_cnae, '') AS cnae_descricao,
                    ({_PORTE_NOME_SQL}) AS porte_nome,
                    {_CAPITAL} AS capital_social,
                    {_DIVIDA} AS divida_total
                {_BASE_FROM}
                WHERE 1=1 {where}
                ORDER BY {coluna} DESC
                LIMIT %s
                """,
                [*params, limite],
            )
            return [
                {
                    "cnpj_completo": r["cnpj_completo"],
                    "razao_social": r["razao_social"],
                    "municipio": r["municipio"],
                    "cnae_principal": r["cnae_principal"],
                    "cnae_descricao": r["cnae_descricao"],
                    "porte_nome": r["porte_nome"],
                    "capital_social": float(r["capital_social"]),
                    "divida_total": float(r["divida_total"]),
                }
                for r in cur.fetchall()
            ]
    except Exception as e:
        log.warning(f"analytics_top_empresas falhou: {e}")
        return []


# ==================== Analise de Socios ====================

def analytics_socios_ranking(limite: int = 50, **filtros) -> List[Dict[str, Any]]:
    """Ranking de socios pelo passivo acumulado das empresas em que constam
    (join dados_socios x dados_empresas por CNPJ_BASICO). Os filtros valem
    para o lado das empresas."""
    try:
        with get_db_cursor() as cur:
            if _vazio(cur) or not _tabela_existe(cur, "dados_socios"):
                return []
            where, params = _filtros_sql(**filtros)
            cur.execute(
                f"""
                SELECT
                    s."NOME_SOCIO" AS nome_socio,
                    COUNT(DISTINCT e."CNPJ_BASICO") AS qtd_empresas,
                    COALESCE(SUM({_DIVIDA}), 0) AS divida_total,
                    COALESCE(SUM({_CAPITAL}), 0) AS capital_total
                FROM dados_socios s
                JOIN dados_empresas e ON e."CNPJ_BASICO" = s."CNPJ_BASICO"
                LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                LEFT JOIN cnaes c ON c.codigo_cnae = e."CNAE_PRINCIPAL"
                WHERE COALESCE(s."NOME_SOCIO", '') <> '' {where}
                GROUP BY s."NOME_SOCIO"
                ORDER BY divida_total DESC
                LIMIT %s
                """,
                [*params, limite],
            )
            return [
                {
                    "nome_socio": r["nome_socio"],
                    "qtd_empresas": int(r["qtd_empresas"]),
                    "divida_total": float(r["divida_total"]),
                    "capital_total": float(r["capital_total"]),
                }
                for r in cur.fetchall()
            ]
    except Exception as e:
        log.warning(f"analytics_socios_ranking falhou: {e}")
        return []


def analytics_socio_detalhe(nome_socio: str) -> List[Dict[str, Any]]:
    """Empresas vinculadas a um socio (drill-down da Analise de Socios)."""
    if not nome_socio:
        return []
    try:
        with get_db_cursor() as cur:
            if _vazio(cur) or not _tabela_existe(cur, "dados_socios"):
                return []
            cur.execute(
                f"""
                SELECT DISTINCT
                    e."CNPJ_COMPLETO" AS cnpj_completo,
                    e."RAZAO_SOCIAL" AS razao_social,
                    COALESCE(m.nome_municipio, '') AS municipio,
                    e."CNAE_PRINCIPAL" AS cnae_principal,
                    COALESCE(c.descricao_cnae, '') AS cnae_descricao,
                    {_CAPITAL} AS capital_social,
                    {_DIVIDA} AS divida_total
                FROM dados_socios s
                JOIN dados_empresas e ON e."CNPJ_BASICO" = s."CNPJ_BASICO"
                LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                LEFT JOIN cnaes c ON c.codigo_cnae = e."CNAE_PRINCIPAL"
                WHERE s."NOME_SOCIO" = %s
                ORDER BY divida_total DESC
                """,
                (nome_socio,),
            )
            return [
                {
                    "cnpj_completo": r["cnpj_completo"],
                    "razao_social": r["razao_social"],
                    "municipio": r["municipio"],
                    "cnae_principal": r["cnae_principal"],
                    "cnae_descricao": r["cnae_descricao"],
                    "capital_social": float(r["capital_social"]),
                    "divida_total": float(r["divida_total"]),
                }
                for r in cur.fetchall()
            ]
    except Exception as e:
        log.warning(f"analytics_socio_detalhe falhou: {e}")
        return []


# ==================== Opcoes de filtro ====================

def analytics_opcoes_filtro() -> Dict[str, Any]:
    """Valores distintos para popular os multiselects da tela (cidades,
    portes) e a lista de CNAEs com descricao."""
    vazio = {"cidades": [], "portes": [], "cnaes": []}
    try:
        with get_db_cursor() as cur:
            if _vazio(cur):
                return vazio

            cidades: List[str] = []
            if _tabela_existe(cur, "municipios"):
                cur.execute(
                    "SELECT DISTINCT nome_municipio FROM municipios "
                    "WHERE nome_municipio <> '' ORDER BY nome_municipio"
                )
                cidades = [r["nome_municipio"] for r in cur.fetchall()]

            # Porte agora e derivado do codigo PORTE_EMPRESA -- so 5 nomes
            # possiveis, e a ordem visual eh melhor fixa (ME, EPP, MEDIO E
            # GRANDE, ...) do que ordem alfabetica.
            cur.execute(
                f'SELECT DISTINCT ({_PORTE_NOME_SQL}) AS p FROM dados_empresas e '
                f'WHERE e."PORTE_EMPRESA" IS NOT NULL'
            )
            portes = sorted({r["p"] for r in cur.fetchall() if r["p"]})

            cnaes: List[str] = []
            if _tabela_existe(cur, "cnaes"):
                cur.execute(
                    """
                    SELECT e."CNAE_PRINCIPAL" AS cnae,
                           COALESCE(MAX(c.descricao_cnae), '') AS descricao,
                           COUNT(*) AS qtd
                    FROM dados_empresas e
                    LEFT JOIN cnaes c ON c.codigo_cnae = e."CNAE_PRINCIPAL"
                    GROUP BY e."CNAE_PRINCIPAL"
                    ORDER BY qtd DESC
                    """
                )
                cnaes = [
                    {"codigo": r["cnae"], "descricao": r["descricao"], "qtd": int(r["qtd"])}
                    for r in cur.fetchall()
                ]

            return {"cidades": cidades, "portes": portes, "cnaes": cnaes}
    except Exception as e:
        log.warning(f"analytics_opcoes_filtro falhou: {e}")
        return vazio
