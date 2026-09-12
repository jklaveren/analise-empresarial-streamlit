"""
Extracao de dados da Receita Federal (CNPJ).

Baixa e processa os zips publicados em
https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/
(Empresas, Estabelecimentos, Socios, Cnaes, Municipios) e gera os CSVs
intermediarios em pipeline/out/:

  - aux_estab_rs.csv     matrizes ativas do RS
  - aux_nomes_empresas.csv  razao social + capital social + porte
  - socios_rs.csv        socios das matrizes RS
  - municipios.csv       codigo -> nome de municipio (lookup)
  - cnaes.csv            codigo -> descricao de CNAE (lookup)

Este modulo *nao* toca em dados de divida (PGFN) -- isso e responsabilidade
de pipeline_pgfn.py. O merge final que junta empresa+divida vive em
pipeline.py.

LOCAL: whodados/pipeline/pipeline_rf.py
Roda com: python whodados/pipeline/pipeline_rf.py <estagio>
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline_common import (
    RAW, OUT, CHUNK_SIZE, zip_valido, cabecalho,
    diagnosticar_url, imprimir_diagnostico, abortar_com_diagnostico,
)


# ----------------------------------------------------------------
# CONFIGURACAO
# ----------------------------------------------------------------
# .get(..., default) so cai no default se a chave nao existir -- mas o workflow
# SEMPRE define RF_SHARE_TOKEN (mesmo vazio, se o secret nao estiver configurado
# no GitHub), entao um secret vazio silenciosamente vencia o token padrao valido
# e quebrava o download com 401. Usar "or" garante que uma string vazia tambem
# cai no padrao.
TOKEN_COMPARTILHAMENTO = os.environ.get("RF_SHARE_TOKEN", "").strip() or "gn672Ad4CF8N6TK"


def detectar_mes_rf() -> str:
    """Detecta o mes/ano de referencia dos dados da Receita Federal.

    Prioridade:
    1. Variavel de ambiente RF_MES_REFERENCIA, se definida -- permite fixar
       manualmente (ex: pra reprocessar um mes especifico).
    2. Deteccao automatica: testa o mes atual e recua mes a mes (ate 6 meses)
       verificando no servidor da Receita Federal qual pasta existe de fato
       (a Receita costuma publicar com atraso). Loga o HTTP code de cada
       tentativa pra distinguir 401 (token expirado), 404 (mes ainda nao
       publicado) e 000 (timeout/conexao caiu).
    3. Se nada retornar 200, FALHA em vez de cair num fallback fantasma
       (rodar o pipeline inteiro contra um mes que nao existe queima 2h+
       do runner por nada, o que ja aconteceu). Pra debugar sem quebrar,
       defina RF_ALLOW_FALLBACK=1 -- ai usa RF_FALLBACK_MES ou o padrao
       abaixo.
    """
    override = os.environ.get("RF_MES_REFERENCIA", "").strip().strip("/")
    if override:
        print(f"  [INFO] Mes RF fixado manualmente via RF_MES_REFERENCIA: {override}", file=sys.stderr)
        return override

    tentativas: list[tuple[str, str]] = []
    ano, mes = datetime.utcnow().year, datetime.utcnow().month
    for _ in range(6):
        candidato = f"{ano:04d}-{mes:02d}"
        url_teste = (
            f"https://arquivos.receitafederal.gov.br/public.php/webdav/"
            f"Dados/Cadastros/CNPJ/{candidato}/Empresas0.zip"
        )
        try:
            # GET-de-1-byte em vez de HEAD (-I): o servidor da Receita nao
            # responde 200 para HEAD (retorna 405/403), o que fazia toda
            # sondagem falhar no runner do GitHub e caia num fallback fantasma.
            # --range 0-0 pede so o primeiro byte via GET; 200 ou 206 = existe.
            resultado = subprocess.run(
                [
                    "curl", "-u", f"{TOKEN_COMPARTILHAMENTO}:", "-s", "-o", "/dev/null",
                    "-w", "%{http_code}", "-L", "--range", "0-0",
                    "--max-time", "15", url_teste,
                ],
                capture_output=True, text=True,
            )
            codigo = (resultado.stdout or "").strip() or "000"
        except Exception as e:
            print(f"  [WARN] Falha ao verificar disponibilidade de {candidato}: {e}", file=sys.stderr)
            codigo = "erro"

        tentativas.append((candidato, codigo))
        print(f"  [SONDA] {candidato} -> HTTP {codigo}", file=sys.stderr)

        # 206 = Partial Content (servidor honrou o --range).
        # 200 = OK (servidor ignorou o range e mandou tudo -- funciona igual).
        if codigo in ("200", "206"):
            print(f"  [OK] Mes RF detectado automaticamente: {candidato}", file=sys.stderr)
            return candidato

        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1

    resumo = ", ".join(f"{m}={c}" for m, c in tentativas)
    permite_fallback = os.environ.get("RF_ALLOW_FALLBACK", "").strip().lower() in ("1", "true", "yes")
    if permite_fallback:
        fallback = os.environ.get("RF_FALLBACK_MES", "").strip() or "2026-05"
        print(f"  [WARN] Nenhum mes RF respondeu 200 ({resumo}); usando fallback {fallback} (RF_ALLOW_FALLBACK=1).", file=sys.stderr)
        return fallback

    # Cai aqui em token invalido (todos 401), servidor fora (todos 000 ou erro),
    # ou mes ainda nao publicado (todos 404). Loga o resumo antes de morrer
    # pra debugar qual dos tres foi.
    hint = ""
    codigos = {c for _, c in tentativas}
    if codigos == {"401"} or codigos == {"401", "erro"}:
        hint = " (todos 401 -- provavel token RF_SHARE_TOKEN invalido/expirado)"
    elif codigos.issubset({"000", "erro", "28"}):
        hint = " (todos timeout/erro -- servidor da Receita fora ou rede do runner)"
    elif codigos.issubset({"404", "403"}):
        hint = " (todos 404/403 -- URL/schema pode ter mudado no servidor)"

    raise SystemExit(
        f"Nao foi possivel detectar o mes RF automaticamente. Tentativas: {resumo}.{hint} "
        f"Pra rodar mesmo assim, defina RF_ALLOW_FALLBACK=1 (usa RF_FALLBACK_MES ou 2026-05) "
        f"ou passe RF_MES_REFERENCIA=<AAAA-MM> pra fixar um mes especifico."
    )


MES_REFERENCIA_RF = detectar_mes_rf()

BASE_URL_RF = (
    f"https://arquivos.receitafederal.gov.br/public.php/webdav/"
    f"Dados/Cadastros/CNPJ/{MES_REFERENCIA_RF}/"
)

EMPRESAS = [f"Empresas{i}.zip" for i in range(10)]
ESTABS   = [f"Estabelecimentos{i}.zip" for i in range(10)]
SOCIOS   = [f"Socios{i}.zip" for i in range(10)]
AUX      = ["Cnaes.zip", "Municipios.zip"]


# ----------------------------------------------------------------
# DOWNLOAD
# ----------------------------------------------------------------
def baixar_rf(arquivo: str) -> Path:
    """Baixa um arquivo da Receita com retomada e retentativas.

    - curl -C - retoma de onde parou (nao rebaixa o que ja veio).
    - --retry cobre erros transitorios de rede/HTTP do proprio curl.
    - Um laco externo revalida o zip: se o download terminou corrompido,
      apaga e rebaixa; se foi interrompido, mantem o parcial e retoma.
    - --no-progress-meter em vez de --progress-bar: com downloads paralelos
      as barras se misturavam e geravam dezenas de milhares de linhas de log.

    Nao levanta excecao: quem chama (_baixar_lista) faz a checagem final
    de integridade e decide se o estagio falhou."""
    destino = RAW / arquivo
    if zip_valido(destino):
        print(f"  [PULO] {arquivo} ja existe e esta integro.")
        return destino

    url = BASE_URL_RF + arquivo
    tentativas = max(1, int(os.environ.get("RF_DOWNLOAD_RETRIES", "4")))
    for tentativa in range(1, tentativas + 1):
        cmd = [
            "curl", "-u", f"{TOKEN_COMPARTILHAMENTO}:", "-L", "-C", "-",
            "--retry", "3", "--retry-delay", "5", "--retry-all-errors",
            "--no-progress-meter", "--fail", url, "-o", str(destino),
        ]
        inicio = time.time()
        resultado = subprocess.run(cmd)
        if resultado.returncode == 0 and zip_valido(destino):
            tam_mb = destino.stat().st_size / (1024 * 1024)
            print(f"  [OK] {arquivo} — {tam_mb:.0f} MB em {time.time() - inicio:.0f}s "
                  f"(tentativa {tentativa}/{tentativas}).")
            return destino

        if resultado.returncode == 0:
            # Download "completo" mas zip corrompido: recomeca limpo.
            print(f"  [RETRY] {arquivo}: baixou mas o zip esta corrompido "
                  f"(tentativa {tentativa}/{tentativas}); rebaixando do zero.")
            if destino.exists():
                destino.unlink()
        else:
            # Interrompido: mantem o parcial, o -C - retoma na proxima volta.
            print(f"  [RETRY] {arquivo}: interrompido (exit {resultado.returncode}, "
                  f"tentativa {tentativa}/{tentativas}); vai retomar.")
            time.sleep(3)

    print(f"  [ERRO] {arquivo}: falhou apos {tentativas} tentativas.")
    return destino


def _preflight_rf(titulo: str, arquivos: list) -> None:
    """Antes de disparar N workers × M arquivos, testa se o primeiro
    arquivo esta acessivel. Se der 401/403/404/5xx, aborta o estagio ja
    com diagnostico -- em vez de queimar horas em curl retries contra um
    servidor que ja disse 'nao' na primeira conexao."""
    if not arquivos:
        return
    # Filtra os que ja estao integros em cache; testa o primeiro que falta.
    faltando = [a for a in arquivos if not zip_valido(RAW / a)]
    if not faltando:
        print(f"  [PREFLIGHT] Todos os {len(arquivos)} arquivos ja estao em cache. Pulando.")
        return
    alvo = faltando[0]
    url = BASE_URL_RF + alvo
    print(f"  [PREFLIGHT] Testando acesso: {alvo}")
    diag = diagnosticar_url(url, auth=f"{TOKEN_COMPARTILHAMENTO}:")
    imprimir_diagnostico(alvo, url, diag)
    if not diag.ok:
        abortar_com_diagnostico(f"DOWNLOAD {titulo}", url, diag)


def _baixar_lista(titulo: str, arquivos: list) -> None:
    """Baixa uma lista de arquivos RF em paralelo (RF_DOWNLOAD_WORKERS conexoes).

    Roda um preflight antes (falha rapido em token invalido / servidor fora
    / mes fantasma). Depois usa um circuit breaker: se as 3 primeiras
    tentativas falharem seguidas com erro nao-transitorio, aborta o
    estagio inteiro em vez de deixar todos os 10 arquivos girarem retries
    contra o mesmo problema."""
    cabecalho(f"DOWNLOAD {titulo}", {"Mes RF": MES_REFERENCIA_RF})
    _preflight_rf(titulo, arquivos)

    workers = max(1, int(os.environ.get("RF_DOWNLOAD_WORKERS", "5")))
    print(f"Baixando {len(arquivos)} arquivos com ate {workers} conexoes paralelas...")

    falhas: list[str] = []
    sucessos: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {executor.submit(baixar_rf, arq): arq for arq in arquivos}
        for fut in as_completed(futuros):
            arq = futuros[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"  [ERRO] Excecao inesperada ao baixar {arq}: {e}")
            if zip_valido(RAW / arq):
                sucessos.append(arq)
            else:
                falhas.append(arq)

    print(f"\n[RESUMO] {titulo}: {len(sucessos)} ok, {len(falhas)} falhas.")
    if falhas:
        # Diagnostica o primeiro falho pra deixar claro por que caiu.
        alvo = falhas[0]
        url = BASE_URL_RF + alvo
        print(f"[FALHA] Investigando '{alvo}' pra reportar o motivo real:")
        diag = diagnosticar_url(url, auth=f"{TOKEN_COMPARTILHAMENTO}:")
        imprimir_diagnostico(alvo, url, diag)
        raise SystemExit(
            f"Download {titulo} incompleto -- {len(falhas)} zip(s) invalido(s) apos "
            f"retentativas: {falhas}. Motivo mais provavel: {diag.motivo} "
            f"({diag.detalhe})."
        )
    print(f"OK Download {titulo} concluido (todos os {len(sucessos)} zips integros).")


# ----------------------------------------------------------------
# PROCESSAMENTO
# ----------------------------------------------------------------
def filtrar_estabelecimentos() -> set:
    """Filtra matrizes ativas no RS e grava aux_estab_rs.csv."""
    print("\n[Etapa] Filtrando Matrizes Ativas no RS...")
    destino = OUT / "aux_estab_rs.csv"
    if destino.exists():
        os.remove(destino)

    primeira_gravacao = True
    total_capturado = 0

    for i, arq_zip in enumerate(sorted(RAW.glob("Estabelecimentos*.zip"))):
        print(f"  Lendo Estabelecimentos {i+1}/10: {arq_zip.name}")
        with zipfile.ZipFile(arq_zip) as z:
            for f_name in z.namelist():
                with z.open(f_name) as f:
                    chunks = pd.read_csv(
                        f, sep=";", encoding="latin1", header=None,
                        dtype=str, chunksize=CHUNK_SIZE,
                    )
                    for chunk in chunks:
                        res = chunk[
                            (chunk[19] == "RS")
                            & (chunk[5] == "02")
                            & (chunk[3] == "1")
                        ].copy()
                        if not res.empty:
                            res["CNPJ_BASICO"] = res[0].str.zfill(8)
                            res["CNPJ_COMPLETO"] = (
                                res["CNPJ_BASICO"]
                                + res[1].str.zfill(4)
                                + res[2].str.zfill(2)
                            )
                            selecao = res[
                                ["CNPJ_BASICO", "CNPJ_COMPLETO", 4, 10, 11, 13, 14, 16, 18, 20, 21, 22, 27]
                            ]
                            selecao.columns = [
                                "CNPJ_BASICO", "CNPJ_COMPLETO", "NOME_FANTASIA",
                                "DATA_FUNDACAO", "CNAE_PRINCIPAL", "LOGRADOURO",
                                "NUMERO", "BAIRRO", "CEP", "COD_MUNICIPIO",
                                "DDD", "TELEFONE", "EMAIL",
                            ]
                            modo = "w" if primeira_gravacao else "a"
                            cabecalho_csv = primeira_gravacao
                            selecao.to_csv(destino, sep=";", index=False, encoding="latin1", mode=modo, header=cabecalho_csv)
                            primeira_gravacao = False
                            total_capturado += len(res)
                            print(f"   + {len(res)} matrizes (Total: {total_capturado})", end="\r")
    df_estab = pd.read_csv(destino, sep=";", encoding="latin1", dtype=str)
    cnpjs_rs = set(df_estab["CNPJ_BASICO"].unique())
    print(f"\nOK Total de matrizes RS capturadas: {len(cnpjs_rs)}")
    return cnpjs_rs


def filtrar_empresas(cnpjs_rs: set) -> pd.DataFrame:
    """Extrai nomes e capital social das empresas que sao matrizes RS."""
    print("\n[Etapa] Buscando Nomes e Capital Social...")
    destino = OUT / "aux_nomes_empresas.csv"
    if destino.exists():
        os.remove(destino)

    emp_chunks_list = []
    for i, arq_zip in enumerate(sorted(RAW.glob("Empresas*.zip"))):
        print(f"  Lendo Empresas {i+1}/10: {arq_zip.name}")
        with zipfile.ZipFile(arq_zip) as z:
            for f_name in z.namelist():
                with z.open(f_name) as f:
                    chunks = pd.read_csv(
                        f, sep=";", encoding="latin1", header=None,
                        dtype=str, chunksize=CHUNK_SIZE,
                    )
                    for chunk in chunks:
                        chunk[0] = chunk[0].str.zfill(8)
                        res = chunk[chunk[0].isin(cnpjs_rs)].copy()
                        if not res.empty:
                            emp_chunks_list.append(res[[0, 1, 4, 5]])

    df_emp = pd.concat(emp_chunks_list, ignore_index=True)
    df_emp.columns = ["CNPJ_BASICO", "RAZAO_SOCIAL", "CAPITAL_SOCIAL", "PORTE_EMPRESA"]
    df_emp["PORTE_NOME"] = (
        df_emp["PORTE_EMPRESA"]
        .str.strip()
        .map({"01": "NAO INFORMADO", "02": "ME", "03": "EPP", "05": "MEDIO E GRANDE"})
        .fillna("DEMAIS")
    )
    df_emp.to_csv(destino, sep=";", index=False, encoding="utf-8")
    print(f"OK Empresas filtradas: {len(df_emp)}")
    return df_emp


def filtrar_socios(cnpjs_rs: set) -> None:
    """Extrai socios das matrizes RS."""
    print("\n[Etapa] Extraindo Socios das Matrizes...")
    destino = OUT / "socios_rs.csv"
    if destino.exists():
        os.remove(destino)

    primeira_gravacao = True
    for i, arq_zip in enumerate(sorted(RAW.glob("Socios*.zip"))):
        print(f"  Lendo Socios {i+1}/10: {arq_zip.name}")
        with zipfile.ZipFile(arq_zip) as z:
            for f_name in z.namelist():
                with z.open(f_name) as f:
                    chunks = pd.read_csv(
                        f, sep=";", encoding="latin1", header=None,
                        dtype=str, chunksize=CHUNK_SIZE,
                    )
                    for chunk in chunks:
                        chunk[0] = chunk[0].str.zfill(8)
                        res = chunk[chunk[0].isin(cnpjs_rs)].copy()
                        if not res.empty:
                            selecao = res[[0, 1, 2, 3, 4]]
                            selecao.columns = [
                                "CNPJ_BASICO", "IDENTIFICADOR_SOCIO",
                                "NOME_SOCIO", "CPF_CNPJ_SOCIO", "QUALIF_SOCIO",
                            ]
                            modo = "w" if primeira_gravacao else "a"
                            cabecalho_csv = primeira_gravacao
                            selecao.to_csv(destino, sep=";", index=False, encoding="utf-8", mode=modo, header=cabecalho_csv)
                            primeira_gravacao = False
    print("OK Socios extraidos.")


def processar_municipios() -> None:
    """Extrai a tabela de codigo->nome de municipios (baixada em Municipios.zip)
    para out/municipios.csv. Usada para resolver COD_MUNICIPIO em nome da cidade."""
    print("\n[Etapa] Processando tabela de Municipios...")
    destino = OUT / "municipios.csv"
    zip_path = RAW / "Municipios.zip"
    if not zip_path.exists():
        print("  [AVISO] Municipios.zip nao encontrado, pulando esta etapa.")
        return
    with zipfile.ZipFile(zip_path) as z:
        f_name = z.namelist()[0]
        with z.open(f_name) as f:
            df_mun = pd.read_csv(f, sep=";", encoding="latin1", header=None, dtype=str)
    df_mun = df_mun.iloc[:, :2]
    df_mun.columns = ["COD_MUNICIPIO", "NOME_MUNICIPIO"]
    df_mun.to_csv(destino, sep=";", index=False, encoding="utf-8")
    print(f"OK Municipios processados: {len(df_mun)}")


def processar_cnaes() -> None:
    """Extrai a tabela de codigo->descricao de CNAEs (baixada em Cnaes.zip)
    para out/cnaes.csv. Usada para traduzir CNAE_PRINCIPAL (que vem so como
    codigo, ex: '6201100') no nome da atividade economica."""
    print("\n[Etapa] Processando tabela de CNAEs...")
    destino = OUT / "cnaes.csv"
    zip_path = RAW / "Cnaes.zip"
    if not zip_path.exists():
        print("  [AVISO] Cnaes.zip nao encontrado, pulando esta etapa.")
        return
    with zipfile.ZipFile(zip_path) as z:
        f_name = z.namelist()[0]
        with z.open(f_name) as f:
            df_cnae = pd.read_csv(f, sep=";", encoding="latin1", header=None, dtype=str)
    df_cnae = df_cnae.iloc[:, :2]
    df_cnae.columns = ["CODIGO_CNAE", "DESCRICAO_CNAE"]
    df_cnae.to_csv(destino, sep=";", index=False, encoding="utf-8")
    print(f"OK CNAEs processados: {len(df_cnae)}")


# ----------------------------------------------------------------
# HELPERS DE CARREGAMENTO (para estagios re-executados isolados)
# ----------------------------------------------------------------
def carregar_cnpjs_rs() -> set:
    """Le aux_estab_rs.csv (saida de filtrar_estabelecimentos) e devolve o
    conjunto de CNPJ_BASICO. Usado pelos estagios de empresas/socios quando
    rodam isolados, sem receber a lista de CNPJs em memoria."""
    caminho = OUT / "aux_estab_rs.csv"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao encontrado. Rode antes o estagio 'process-estab'."
        )
    df = pd.read_csv(caminho, sep=";", encoding="latin1", dtype=str)
    return set(df["CNPJ_BASICO"].unique())


def carregar_empresas_aux() -> pd.DataFrame:
    """Le aux_nomes_empresas.csv (saida de filtrar_empresas). Usado pelo
    estagio de merge quando rodado isolado."""
    caminho = OUT / "aux_nomes_empresas.csv"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao encontrado. Rode antes o estagio 'process-empresas'."
        )
    return pd.read_csv(caminho, sep=";", encoding="utf-8", dtype=str)


# ----------------------------------------------------------------
# ESTAGIOS
# ----------------------------------------------------------------
def stage_download_rf_empresas() -> None:
    """Empresas0-9 + auxiliares (Cnaes, Municipios)."""
    _baixar_lista("RF EMPRESAS (+ aux)", AUX + EMPRESAS)


def stage_download_rf_estab() -> None:
    """Estabelecimentos0-9 (o mais pesado do download)."""
    _baixar_lista("RF ESTABELECIMENTOS", ESTABS)


def stage_download_rf_socios() -> None:
    """Socios0-9."""
    _baixar_lista("RF SOCIOS", SOCIOS)


def stage_download_rf() -> None:
    """Wrapper local (modo 'all') que roda os 3 sub-estagios em sequencia."""
    stage_download_rf_empresas()
    stage_download_rf_estab()
    stage_download_rf_socios()


def stage_process_aux() -> None:
    """Municipios + CNAEs -- lookups rapidos (extrai um zip pequeno cada)."""
    cabecalho("PROCESS AUX (municipios + cnaes)", {"Mes RF": MES_REFERENCIA_RF})
    processar_municipios()
    processar_cnaes()
    print("\nOK Aux (municipios + cnaes) concluido.")


def stage_process_estab() -> None:
    """Filtra as matrizes ativas do RS (le os 10 zips de Estabelecimentos)."""
    cabecalho("PROCESS ESTABELECIMENTOS", {"Mes RF": MES_REFERENCIA_RF})
    filtrar_estabelecimentos()
    print("\nOK Estabelecimentos concluido.")


def stage_process_empresas() -> None:
    """Nomes / capital social das matrizes RS (le os 10 zips de Empresas)."""
    cabecalho("PROCESS EMPRESAS", {"Mes RF": MES_REFERENCIA_RF})
    filtrar_empresas(carregar_cnpjs_rs())
    print("\nOK Empresas concluido.")


def stage_process_socios() -> None:
    """Socios das matrizes RS (le os 10 zips de Socios)."""
    cabecalho("PROCESS SOCIOS", {"Mes RF": MES_REFERENCIA_RF})
    filtrar_socios(carregar_cnpjs_rs())
    print("\nOK Socios concluido.")


def stage_process_rf() -> None:
    """Roda os 4 sub-estagios de processamento RF em sequencia (modo 'all')."""
    stage_process_aux()
    stage_process_estab()
    stage_process_empresas()
    stage_process_socios()
    print("\nOK Processamento RF concluido.")


_STAGES = {
    "download-rf": stage_download_rf,
    "download-rf-empresas": stage_download_rf_empresas,
    "download-rf-estab": stage_download_rf_estab,
    "download-rf-socios": stage_download_rf_socios,
    "process-rf": stage_process_rf,
    "process-aux": stage_process_aux,
    "process-estab": stage_process_estab,
    "process-empresas": stage_process_empresas,
    "process-socios": stage_process_socios,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline ETL WhoDados -- Receita Federal (CNPJ)."
    )
    parser.add_argument(
        "stage", choices=list(_STAGES),
        help="Estagio a executar.",
    )
    _STAGES[parser.parse_args().stage]()
