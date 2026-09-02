# =================================================================
# PIPELINE DE EXTRACAO RS MASTER 2026
# Versao para ambientes nao-Colab (GitHub Actions / local)
# LOCAL: whodados/pipeline/pipeline.py
# Roda com: python whodados/pipeline/pipeline.py
# =================================================================
import os
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import zipfile
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------------------------------------------
# CONFIGURACAO
# ----------------------------------------------------------------
if "WHO_PROJECT_DIR" in os.environ:
    BASE_DIR = Path(os.environ["WHO_PROJECT_DIR"])
else:
    _candidato = Path(__file__).resolve().parent.parent
    while _candidato.parent != _candidato:
        if (_candidato / "setup.py").exists():
            BASE_DIR = _candidato
            break
        _candidato = _candidato.parent
    else:
        print("ERROR: Nao foi possivel localizar o diretorio raiz do projeto.")
        print("Defina a variavel de ambiente WHO_PROJECT_DIR apontando para a pasta whodados/.")
        sys.exit(1)

RAW  = BASE_DIR / "pipeline" / "raw"
OUT  = BASE_DIR / "pipeline" / "out"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

TOKEN_COMPARTILHAMENTO = os.environ.get("RF_SHARE_TOKEN", "gn672Ad4CF8N6TK")
BASE_URL_RF = (
    f"https://arquivos.receitafederal.gov.br/public.php/webdav/"
    f"Dados/Cadastros/CNPJ/2026-05/"
)

URL_BASE_PGFN_INDEX = "https://dadosabertos.pgfn.gov.br/"

CHUNK_SIZE = 500_000

EMPRESAS = [f"Empresas{i}.zip" for i in range(10)]
ESTABS   = [f"Estabelecimentos{i}.zip" for i in range(10)]
SOCIOS   = [f"Socios{i}.zip" for i in range(10)]
AUX      = ["Cnaes.zip", "Municipios.zip"]
PGFN     = [
    "Dados_abertos_FGTS.zip",
    "Dados_abertos_Nao_Previdenciario.zip",
    "Dados_abertos_Previdenciario.zip",
]

ultimo_trimestre = detectar_trimestre_pgfn()


def baixar_rf(arquivo: str) -> Path:
    destino = RAW / arquivo
    if destino.exists():
        print(f"  [PULSO] {arquivo} ja existe — pulando.")
        return destino
    url = BASE_URL_RF + arquivo
    cmd = [
        "curl", "-u", f"{TOKEN_COMPARTILHAMENTO}:", "-L", "-C", "-",
        url, "-o", str(destino), "--progress-bar", "--fail",
    ]
    print(f"  Baixando RF: {arquivo}")
    resultado = subprocess.run(cmd)
    if resultado.returncode != 0:
        print(f"  [WARN] Falha ao baixar {arquivo} (exit {resultado.returncode}).")
    return destino


def baixar_pgfn(arquivo: str) -> Path:
    destino = RAW / arquivo
    if destino.exists():
        print(f"  [PULSO] {arquivo} ja existe — pulando.")
        return destino
    url = BASE_URL_PGFN_INDEX + ultimo_trimestre + "/" + arquivo
    cmd = [
        "wget", "--no-check-certificate", "-c", url,
        "-P", str(RAW), "-q", "--show-progress",
    ]
    print(f"  Baixando PGFN: {arquivo}")
    resultado = subprocess.run(cmd)
    if resultado.returncode != 0:
        print(f"  [WARN] Falha ao baixar {arquivo} (exit {resultado.returncode}).")
    return destino


def detectar_trimestre_pgfn() -> str:
    print("🔍 Buscando o trimestre mais recente da PGFN...")
    try:
        response = requests.get(URL_BASE_PGFN_INDEX, verify=False, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        padrao = re.compile(r"^\d{4}_trimestre_\d{2}/$")
        trimestres = [
            a["href"]
            for a in soup.find_all("a", href=True)
            if padrao.match(a["href"].strip("/"))
        ]
        if trimestres:
            ultimo = sorted(trimestres)[-1].strip("/") + "/"
            print(f"✅ Versao mais recente encontrada: {ultimo}")
            return ultimo
        raise ValueError("Nenhum trimestre encontrado no padrao esperado.")
    except Exception as e:
        print(f"⚠️ Falha na deteccao automatica ({e}). Usando fallback 2026_trimestre_01/")
        return "2026_trimestre_01/"


def filtrar_estabelecimentos() -> set:
    """Filtra matrizes ativas no RS e grava aux_estab_rs.csv."""
    print("\n🏭 Etapa: Filtrando Matrizes Ativas no RS...")
    destino = OUT / "aux_estab_rs.csv"
    if destino.exists():
        os.remove(destino)

    primeira_gravacao = True
    total_capturado = 0

    for i, arq_zip in enumerate(sorted(RAW.glob("Estabelecimentos*.zip"))):
        print(f"📦 Lendo Estabelecimentos {i+1}/10: {arq_zip.name}")
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
                            cabecalho = primeira_gravacao
                            selecao.to_csv(destino, sep=";", index=False, encoding="latin1", mode=modo, header=cabecalho)
                            primeira_gravacao = False
                            total_capturado += len(res)
                            print(f"   + {len(res)} matrizes (Total: {total_capturado})", end="\r")
    df_estab = pd.read_csv(destino, sep=";", encoding="latin1", dtype=str)
    cnpjs_rs = set(df_estab["CNPJ_BASICO"].unique())
    print(f"\n✅ Total de matrizes RS capturadas: {len(cnpjs_rs)}")
    return cnpjs_rs


def filtrar_empresas(cnpjs_rs: set) -> pd.DataFrame:
    """Extrai nomes e capital social das empresas que sao matrizes RS."""
    print("\n🏢 Etapa: Buscando Nomes e Capital Social...")
    destino = OUT / "aux_nomes_empresas.csv"
    if destino.exists():
        os.remove(destino)

    emp_chunks_list = []
    for i, arq_zip in enumerate(sorted(RAW.glob("Empresas*.zip"))):
        print(f"📦 Lendo Empresas {i+1}/10: {arq_zip.name}")
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
        .map({"01": "NÃO INFORMADO", "02": "ME", "03": "EPP", "05": "MÉDIO E GRANDE"})
        .fillna("DEMAIS")
    )
    df_emp.to_csv(destino, sep=";", index=False, encoding="utf-8")
    print(f"✅ Empresas filtradas: {len(df_emp)}")
    return df_emp


def filtrar_socios(cnpjs_rs: set) -> None:
    """Extrai socios das matrizes RS."""
    print("\n👥 Etapa: Extraindo Sócios das Matrizes...")
    destino = OUT / "socios_rs.csv"
    if destino.exists():
        os.remove(destino)

    primeira_gravacao = True
    for i, arq_zip in enumerate(sorted(RAW.glob("Socios*.zip"))):
        print(f"📦 Lendo Sócios {i+1}/10: {arq_zip.name}")
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
                            selecao = res[["0", "1", "2", "3", "4"]]
                            selecao.columns = [
                                "CNPJ_BASICO", "IDENTIFICADOR_SOCIO",
                                "NOME_SOCIO", "CPF_CNPJ_SOCIO", "QUALIF_SOCIO",
                            ]
                            modo = "w" if primeira_gravacao else "a"
                            cabecalho = primeira_gravacao
                            selecao.to_csv(destino, sep=";", index=False, encoding="utf-8", mode=modo, header=cabecalho)
                            primeira_gravacao = False
    print("✅ Sócios extraídos.")


def consolidar_dividas_pgfn() -> pd.DataFrame:
    """Consolida dividas ativas da PGFN."""
    print("\n💰 Etapa: Consolidando Dívida Ativa (PGFN)...")
    pgfn_chunks = []

    for arq_pgfn in ["Dados_abertos_Nao_Previdenciario.zip", "Dados_abertos_Previdenciario.zip", "Dados_abertos_FGTS.zip"]:
        arq_zip_path = RAW / arq_pgfn
        if not arq_zip_path.exists():
            print(f"  [PULSO] {arq_pgfn} nao encontrado.")
            continue
        print(f"📦 Lendo PGFN: {arq_pgfn}")
        with zipfile.ZipFile(arq_zip_path) as z:
            for f_name in z.namelist():
                with z.open(f_name) as f:
                    chunks = pd.read_csv(
                        f, sep=";", encoding="latin1", header=None,
                        dtype=str, chunksize=CHUNK_SIZE, low_memory=False,
                    )
                    for chunk in chunks:
                        if 0 in chunk.columns and 4 in chunk.columns:
                            chunk["CNPJ_BASICO"] = (
                                chunk[0]
                                .astype(str)
                                .str.replace(r"\D", "", regex=True)
                                .str.zfill(14)
                                .str[:8]
                            )
                            chunk["VALOR"] = pd.to_numeric(
                                chunk[4].astype(str).str.replace(",", ".", regex=False),
                                errors="coerce",
                            ).fillna(0.0)
                            pgfn_chunks.append(chunk[["CNPJ_BASICO", "VALOR"]])

    if pgfn_chunks:
        df_pgfn_total = pd.concat(pgfn_chunks, ignore_index=True)
        df_dividas = df_pgfn_total.groupby("CNPJ_BASICO")["VALOR"].sum().reset_index()
        df_dividas.rename(columns={"VALOR": "DIVIDA_TOTAL"}, inplace=True)
    else:
        df_dividas = pd.DataFrame(columns=["CNPJ_BASICO", "DIVIDA_TOTAL"])
    print(f"✅ Dívidas consolidadas: {len(df_dividas)} empresas.")
    return df_dividas


def gerar_master(df_emp: pd.DataFrame, df_dividas: pd.DataFrame) -> pd.DataFrame:
    """Gera o arquivo final subset_rs_final_completo.csv."""
    print("\n🚀 Etapa Final: Gerando Master...")
    df_estab = pd.read_csv(OUT / "aux_estab_rs.csv", sep=";", encoding="latin1", dtype=str)

    master = df_estab.merge(df_emp, on="CNPJ_BASICO", how="left")
    master = master.merge(df_dividas, on="CNPJ_BASICO", how="left")

    master["CONTATO_FONE"] = "(" + master["DDD"].fillna("") + ") " + master["TELEFONE"].fillna("")
    master["CAPITAL_SOCIAL"] = pd.to_numeric(master["CAPITAL_SOCIAL"].str.replace(",", "."), errors="coerce").fillna(0.0)
    master["DIVIDA_TOTAL"] = master["DIVIDA_TOTAL"].fillna(0.0)

    ARQUIVO_FINAL = OUT / "subset_rs_final_completo.csv"
    master.to_csv(ARQUIVO_FINAL, sep=";", index=False, encoding="latin1")
    print(f"\n✅ PROCESSO FINALIZADO! Total de Matrizes Ativas no RS: {len(master)}")
    print(f"📂 Local: {ARQUIVO_FINAL}")
    return master


def rodar_pipeline() -> None:
    """Executa o pipeline completo de extração."""
    print("=" * 60)
    print("PIPELINE RS MASTER 2026 — INICIANDO")
    print(f"Diretorio raiz: {BASE_DIR}")
    print(f"Raw: {RAW}")
    print(f"Out: {OUT}")
    print(f"Trimestre PGFN: {ultimo_trimestre}")
    print("=" * 60)

    print("\n📥 Baixando arquivos...")
    for arq in AUX + EMPRESAS + ESTABS + SOCIOS:
        baixar_rf(arq)
    for arq in PGFN:
        baixar_pgfn(arq)

    cnpjs_rs = filtrar_estabelecimentos()
    df_emp = filtrar_empresas(cnpjs_rs)
    filtrar_socios(cnpjs_rs)
    df_dividas = consolidar_dividas_pgfn()
    gerar_master(df_emp, df_dividas)

    print("\n🏁 Pipeline concluído com sucesso!")


if __name__ == "__main__":
    rodar_pipeline()