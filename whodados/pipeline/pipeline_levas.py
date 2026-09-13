# =================================================================
# PIPELINE RS MASTER — PROCESSAMENTO EM LEVAS
# =================================================================
# Baixa -> filtra -> apaga, um arquivo por vez.
# Pico de disco ~2GB em vez de 27GB, entao roda no Colab sem encher o
# Drive e cabe nos 14GB do runner do GitHub Actions.
#
# Retomavel: guarda o progresso em _progresso.json. Se a sessao cair,
# rodar de novo continua de onde parou em vez de recomecar.
# =================================================================

import json
import os
import re
import zipfile
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------------------------------------------
# CONFIGURACAO
# ----------------------------------------------------------------
TOKEN_RF = os.environ.get("RF_SHARE_TOKEN", "").strip() or "gn672Ad4CF8N6TK"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# True mantem os zips (cache entre execucoes, precisa dos 27GB).
# False apaga cada zip apos processar -- este e o modo "em levas".
MANTER_ZIPS = os.environ.get("MANTER_ZIPS", "").lower() in ("1", "true", "sim")

NO_COLAB = Path("/content").exists()
if NO_COLAB:
    from google.colab import drive
    drive.mount("/content/drive")
    BASE_DIR = Path("/content/drive/MyDrive/NRA_PROJETO")
else:
    BASE_DIR = Path(os.environ.get("BASE_DIR", "./NRA_PROJETO"))

RAW = BASE_DIR / "raw"
OUT = BASE_DIR / "out"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

AUX_ESTAB = OUT / "aux_estab_rs.csv"
AUX_SOCIOS = OUT / "socios_rs.csv"
AUX_EMPRESAS = OUT / "empresas_rs.csv"
AUX_DIVIDAS = OUT / "dividas.csv"
ARQUIVO_FINAL = OUT / "subset_rs_final_completo.csv"
ESTADO = OUT / "_progresso.json"

CHUNK_SIZE = 500_000
MB = 1024 * 1024

DAV_RF = f"https://arquivos.receitafederal.gov.br/public.php/dav/files/{TOKEN_RF}"
PASTA_CNPJ = "Dados/Cadastros/CNPJ"
PGFN_INDEX = "https://dadosabertos.pgfn.gov.br/"

PGFN_ARQUIVOS = {
    "Dados_abertos_Nao_Previdenciario.zip": "DIVIDA_FEDERAL",
    "Dados_abertos_Previdenciario.zip": "DIVIDA_PREVIDENCIARIA",
    "Dados_abertos_FGTS.zip": "DIVIDA_FGTS",
}
COLS_DIVIDA = ["DIVIDA_FEDERAL", "DIVIDA_PREVIDENCIARIA", "DIVIDA_FGTS"]

print("=" * 70)
print("PIPELINE RS — PROCESSAMENTO EM LEVAS")
print(f"Modo: {'mantendo zips' if MANTER_ZIPS else 'apagando zip apos processar'}")
print("=" * 70)


# ----------------------------------------------------------------
# CHECKPOINT
# ----------------------------------------------------------------
def ler_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"feitos": []}


def marcar_feito(estado, chave):
    estado["feitos"].append(chave)
    ESTADO.write_text(json.dumps(estado, indent=2), encoding="utf-8")


# ----------------------------------------------------------------
# DOWNLOAD
# ----------------------------------------------------------------
def listar_dav(caminho):
    r = requests.request("PROPFIND", f"{DAV_RF}/{caminho}/",
                         headers={"Depth": "1"}, timeout=60, verify=False)
    r.raise_for_status()
    hrefs = re.findall(r"<d:href>([^<]*)</d:href>", r.text, re.IGNORECASE)
    return [h.rstrip("/").split("/")[-1] for h in hrefs if h.rstrip("/").split("/")[-1]]


def baixar(url, destino, rotulo):
    """Baixa com stream e retomada. Levanta SystemExit com o motivo se falhar."""
    if destino.exists() and zipfile.is_zipfile(destino):
        print(f"   ⏭️  {rotulo} (já baixado)")
        return

    parcial = destino.stat().st_size if destino.exists() else 0
    headers = {"Range": f"bytes={parcial}-"} if parcial else {}

    try:
        # stream=True e obrigatorio: Estabelecimentos0.zip tem 2GB e sem isso
        # o requests carrega tudo na RAM antes de gravar.
        with requests.get(url, headers=headers, stream=True,
                          timeout=(30, 300), verify=False) as r:
            if r.status_code not in (200, 206):
                raise SystemExit(f"❌ {rotulo}: HTTP {r.status_code}\n   URL: {url}")

            total = int(r.headers.get("Content-Length", 0))
            modo = "ab" if (r.status_code == 206 and parcial) else "wb"
            if modo == "ab":
                total += parcial
            feito = parcial if modo == "ab" else 0

            with open(destino, modo) as f:
                for bloco in r.iter_content(chunk_size=8 * MB):
                    f.write(bloco)
                    feito += len(bloco)
                    if total:
                        print(f"\r   ⬇️  {rotulo}: {feito/MB:,.0f}/{total/MB:,.0f} MB "
                              f"({feito*100//total}%)", end="", flush=True)
            print()
    except requests.RequestException as e:
        raise SystemExit(f"❌ {rotulo}: {type(e).__name__}: {e}\n   URL: {url}")

    # Uma pagina de erro tambem chega com status 200; o teste de zip pega isso.
    if not zipfile.is_zipfile(destino):
        tamanho = destino.stat().st_size
        destino.unlink(missing_ok=True)
        raise SystemExit(f"❌ {rotulo}: resposta não é um ZIP ({tamanho/MB:,.1f} MB)\n"
                         f"   URL: {url}")


def ler_zip_em_chunks(caminho):
    """Itera os chunks de todos os CSVs dentro do zip."""
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            with z.open(nome) as f:
                yield from pd.read_csv(f, sep=";", encoding="latin1", header=None,
                                       dtype=str, chunksize=CHUNK_SIZE,
                                       low_memory=False)


def em_levas(arquivos, url_base, rotulo, processar):
    """Baixa -> processa -> apaga, um por vez. Retoma pelo checkpoint."""
    estado = ler_estado()
    print(f"\n{'='*70}\n{rotulo}\n{'='*70}")

    for i, arquivo in enumerate(arquivos, 1):
        chave = f"{rotulo}:{arquivo}"
        if chave in estado["feitos"]:
            print(f"   ✔️  [{i}/{len(arquivos)}] {arquivo} (já processado)")
            continue

        caminho = RAW / arquivo
        baixar(f"{url_base}/{arquivo}", caminho, f"[{i}/{len(arquivos)}] {arquivo}")

        linhas = processar(caminho)
        print(f"   ✅ {arquivo}: {linhas:,} linhas aproveitadas")

        if not MANTER_ZIPS:
            caminho.unlink(missing_ok=True)

        marcar_feito(estado, chave)


def anexar_csv(df, destino, encoding="utf-8"):
    """Grava com header na primeira vez, depois so anexa."""
    novo = not destino.exists()
    df.to_csv(destino, sep=";", index=False, encoding=encoding,
              mode="w" if novo else "a", header=novo)


# ----------------------------------------------------------------
# DETECCAO DE FONTES
# ----------------------------------------------------------------
print("\n🔍 Detectando versões disponíveis...")

meses = sorted(m for m in listar_dav(PASTA_CNPJ) if re.fullmatch(r"\d{4}-\d{2}", m))
if not meses:
    raise SystemExit("❌ Nenhuma pasta AAAA-MM no compartilhamento da RF.")
MES_RF = meses[-1]
URL_RF = f"{DAV_RF}/{PASTA_CNPJ}/{MES_RF}"
print(f"✅ Receita Federal: {MES_RF}")

try:
    html = requests.get(PGFN_INDEX, verify=False, timeout=30).text
    trimestres = sorted(set(re.findall(r"(\d{4}_trimestre_\d{2})/", html)))
    if not trimestres:
        raise ValueError("nenhum trimestre listado")
    TRIMESTRE = trimestres[-1]
except Exception as e:
    raise SystemExit(f"❌ Não consegui detectar o trimestre da PGFN: {e}")
URL_PGFN = f"{PGFN_INDEX}{TRIMESTRE}"
print(f"✅ PGFN: {TRIMESTRE}")


# ----------------------------------------------------------------
# ETAPA 1 — ESTABELECIMENTOS (define quais CNPJs sao do RS)
# ----------------------------------------------------------------
COLS_ESTAB = ["CNPJ_BASICO", "CNPJ_COMPLETO", "NOME_FANTASIA", "DATA_FUNDACAO",
              "CNAE_PRINCIPAL", "LOGRADOURO", "NUMERO", "BAIRRO", "CEP",
              "COD_MUNICIPIO", "DDD", "TELEFONE", "EMAIL"]


def processar_estabelecimentos(caminho):
    total = 0
    for chunk in ler_zip_em_chunks(caminho):
        # col 19 = UF, col 5 = situacao cadastral (02 = ativa), col 3 = matriz/filial (1 = matriz)
        res = chunk[(chunk[19] == "RS") & (chunk[5] == "02") & (chunk[3] == "1")].copy()
        if res.empty:
            continue
        res["CNPJ_BASICO"] = res[0].str.zfill(8)
        res["CNPJ_COMPLETO"] = res["CNPJ_BASICO"] + res[1].str.zfill(4) + res[2].str.zfill(2)
        sel = res[["CNPJ_BASICO", "CNPJ_COMPLETO", 4, 10, 11, 13, 14, 16, 18, 20, 21, 22, 27]]
        sel.columns = COLS_ESTAB
        anexar_csv(sel, AUX_ESTAB, encoding="latin1")
        total += len(sel)
    return total


em_levas([f"Estabelecimentos{i}.zip" for i in range(10)], URL_RF,
         "ETAPA 1 — Estabelecimentos (matrizes ativas no RS)",
         processar_estabelecimentos)

if not AUX_ESTAB.exists():
    raise SystemExit("❌ Nenhuma matriz do RS encontrada — o layout da RF pode ter mudado.")

df_estab = pd.read_csv(AUX_ESTAB, sep=";", encoding="latin1", dtype=str)
cnpjs_rs = set(df_estab["CNPJ_BASICO"].unique())
print(f"\n📍 {len(df_estab):,} matrizes ativas no RS | {len(cnpjs_rs):,} CNPJs únicos")


# ----------------------------------------------------------------
# ETAPA 2 — EMPRESAS
# ----------------------------------------------------------------
def processar_empresas(caminho):
    total = 0
    for chunk in ler_zip_em_chunks(caminho):
        chunk[0] = chunk[0].str.zfill(8)
        res = chunk[chunk[0].isin(cnpjs_rs)]
        if res.empty:
            continue
        sel = res[[0, 1, 4, 5]].copy()
        sel.columns = ["CNPJ_BASICO", "RAZAO_SOCIAL", "CAPITAL_SOCIAL", "PORTE_EMPRESA"]
        anexar_csv(sel, AUX_EMPRESAS, encoding="latin1")
        total += len(sel)
    return total


em_levas([f"Empresas{i}.zip" for i in range(10)], URL_RF,
         "ETAPA 2 — Empresas (razão social e capital)", processar_empresas)


# ----------------------------------------------------------------
# ETAPA 3 — SOCIOS
# ----------------------------------------------------------------
def processar_socios(caminho):
    total = 0
    for chunk in ler_zip_em_chunks(caminho):
        chunk[0] = chunk[0].str.zfill(8)
        res = chunk[chunk[0].isin(cnpjs_rs)]
        if res.empty:
            continue
        sel = res[[0, 1, 2, 3, 4]].copy()
        sel.columns = ["CNPJ_BASICO", "IDENTIFICADOR_SOCIO", "NOME_SOCIO",
                       "CPF_CNPJ_SOCIO", "QUALIF_SOCIO"]
        anexar_csv(sel, AUX_SOCIOS)
        total += len(sel)
    return total


em_levas([f"Socios{i}.zip" for i in range(10)], URL_RF,
         "ETAPA 3 — Sócios", processar_socios)


# ----------------------------------------------------------------
# ETAPA 4 — PGFN (dividas)
# ----------------------------------------------------------------
# Cada zip da PGFN e um tipo de divida. Agrega por CNPJ ja filtrando pelo RS,
# senao carregaria os ~6,7M de devedores do Brasil inteiro na memoria.
def fazer_processador_pgfn(coluna):
    def processar(caminho):
        parciais = []
        for chunk in ler_zip_em_chunks(caminho):
            if 0 not in chunk.columns or 4 not in chunk.columns:
                continue
            cnpj = chunk[0].str.replace(r"\D", "", regex=True).str.zfill(14).str[:8]
            valor = pd.to_numeric(chunk[4].str.replace(",", ".", regex=False),
                                  errors="coerce").fillna(0.0)
            bloco = pd.DataFrame({"CNPJ_BASICO": cnpj, coluna: valor})
            bloco = bloco[bloco["CNPJ_BASICO"].isin(cnpjs_rs)]
            if not bloco.empty:
                parciais.append(bloco.groupby("CNPJ_BASICO", as_index=False)[coluna].sum())

        if not parciais:
            return 0
        agregado = pd.concat(parciais, ignore_index=True)
        agregado = agregado.groupby("CNPJ_BASICO", as_index=False)[coluna].sum()
        agregado.to_csv(OUT / f"_divida_{coluna}.csv", sep=";", index=False)
        return len(agregado)

    return processar


for arquivo_pgfn, coluna in PGFN_ARQUIVOS.items():
    em_levas([arquivo_pgfn], URL_PGFN, f"ETAPA 4 — {coluna}",
             fazer_processador_pgfn(coluna))

df_dividas = pd.DataFrame({"CNPJ_BASICO": sorted(cnpjs_rs)})
for coluna in COLS_DIVIDA:
    parcial = OUT / f"_divida_{coluna}.csv"
    if parcial.exists():
        df_dividas = df_dividas.merge(
            pd.read_csv(parcial, sep=";", dtype={"CNPJ_BASICO": str}),
            on="CNPJ_BASICO", how="left")
    else:
        df_dividas[coluna] = 0.0
df_dividas[COLS_DIVIDA] = df_dividas[COLS_DIVIDA].fillna(0.0)
df_dividas["DIVIDA_TOTAL"] = df_dividas[COLS_DIVIDA].sum(axis=1)
df_dividas.to_csv(AUX_DIVIDAS, sep=";", index=False)

com_divida = int((df_dividas["DIVIDA_TOTAL"] > 0).sum())
print(f"\n💰 {com_divida:,} empresas do RS com dívida ativa")


# ----------------------------------------------------------------
# ETAPA 5 — CONSOLIDACAO
# ----------------------------------------------------------------
print(f"\n{'='*70}\nETAPA 5 — Consolidação\n{'='*70}")

df_emp = pd.read_csv(AUX_EMPRESAS, sep=";", encoding="latin1", dtype=str)
master = df_estab.merge(df_emp, on="CNPJ_BASICO", how="left")
master = master.merge(df_dividas, on="CNPJ_BASICO", how="left")

master["CAPITAL_SOCIAL"] = pd.to_numeric(
    master["CAPITAL_SOCIAL"].str.replace(",", ".", regex=False), errors="coerce").fillna(0.0)
master["DATA_FUNDACAO"] = pd.to_datetime(master["DATA_FUNDACAO"], format="%Y%m%d",
                                         errors="coerce")
for coluna in COLS_DIVIDA + ["DIVIDA_TOTAL"]:
    master[coluna] = master[coluna].fillna(0.0)

master.to_csv(ARQUIVO_FINAL, sep=";", index=False, encoding="latin1")
print(f"✅ {len(master):,} empresas consolidadas -> {ARQUIVO_FINAL}")


# ----------------------------------------------------------------
# ETAPA 6 — SUPABASE
# ----------------------------------------------------------------
if DATABASE_URL:
    print(f"\n{'='*70}\nETAPA 6 — Supabase\n{'='*70}")
    from sqlalchemy import create_engine

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    master.to_sql("dados_empresas", engine, if_exists="replace",
                  index=False, chunksize=5000, method="multi")
    print(f"✅ dados_empresas: {len(master):,} linhas")

    if AUX_SOCIOS.exists():
        df_socios = pd.read_csv(AUX_SOCIOS, sep=";", dtype=str)
        df_socios.to_sql("dados_socios", engine, if_exists="replace",
                         index=False, chunksize=5000, method="multi")
        print(f"✅ dados_socios: {len(df_socios):,} linhas")
else:
    print("\n⚠️  DATABASE_URL não definida — dados ficaram só em CSV.")


# ----------------------------------------------------------------
# RESUMO
# ----------------------------------------------------------------
print(f"\n{'='*70}\n✅ CONCLUÍDO\n{'='*70}")
print(f"  Fonte RF ............. {MES_RF}")
print(f"  Fonte PGFN ........... {TRIMESTRE}")
print(f"  Matrizes ativas RS ... {len(master):,}")
print(f"  Com dívida ........... {com_divida:,}")
for coluna in COLS_DIVIDA + ["DIVIDA_TOTAL"]:
    print(f"  {coluna:.<21} R$ {master[coluna].sum():,.2f}")
print(f"  Arquivo .............. {ARQUIVO_FINAL}")
print("\n  Para reprocessar do zero, apague:", ESTADO)
