"""Testes do construtor de filtros do funil de empresas (sem banco)."""
from backend.db.service import _where_empresas, _norm_lista


def test_norm_lista():
    assert _norm_lista(None) == []
    assert _norm_lista("") == []
    assert _norm_lista("PoA") == ["PoA"]
    assert _norm_lista(["A", "B", ""]) == ["A", "B"]


def test_where_vazio():
    where, params = _where_empresas()
    assert where == ""
    assert params == []


def test_where_cidade_e_cnae():
    where, params = _where_empresas(cidade=["Porto Alegre", "Canoas"], cnae=["0111301"])
    assert "m.nome_municipio = ANY(%s)" in where
    assert 'e."CNAE_PRINCIPAL" = ANY(%s)' in where
    assert ["Porto Alegre", "Canoas"] in params
    assert ["0111301"] in params


def test_where_faixas():
    where, params = _where_empresas(divida_min=1000, capital_max=50000)
    assert '"DIVIDA_TOTAL"' in where
    assert '"CAPITAL_SOCIAL"' in where
    assert 1000 in params
    assert 50000 in params


def test_where_blacklist_rj():
    where, params = _where_empresas(incluir_inativas=False)
    assert "!~*" in where  # exclui Falencia/Rec. Judicial
    # incluir_inativas=True (padrao) nao filtra
    where2, _ = _where_empresas(incluir_inativas=True)
    assert "!~*" not in where2


def test_where_fundacao_normaliza_data():
    where, params = _where_empresas(fundacao_de="2020-01-15", fundacao_ate="2023-12-31")
    assert '"DATA_FUNDACAO"' in where
    assert "20200115" in params
    assert "20231231" in params
