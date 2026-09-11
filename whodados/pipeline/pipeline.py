# =================================================================
# PIPELINE DE EXTRACAO RS MASTER 2026
# Versao para ambientes nao-Colab (GitHub Actions / local)
# LOCAL: whodados/pipeline/pipeline.py
# Roda com: python whodados/pipeline/pipeline.py
# =================================================================
import argparse
import os
import sys
import subprocess
import time
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

import pandas as pd
import zipfile


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
       manualmente (ex: pra reprocessar um mes especifico), sem depender da
       deteccao automatica.
    2. Deteccao automatica: testa o mes atual e recua mes a mes (ate 6 meses)
       verificando no servidor da Receita Federal qual pasta existe de fato
       (a Receita costuma publicar com atraso, entao o mes corrente pode
       ainda nao estar disponivel).
    3. Se a deteccao falhar (sem rede, servidor fora do ar, etc.), cai no
       padrao fixo abaixo para o pipeline nao quebrar.
    """
    override = os.environ.get("RF_MES_REFERENCIA", "").strip().strip("/")
    if override:
        print(f"  [INFO] Mes RF fixado manualmente via RF_MES_REFERENCIA: {override}", file=sys.stderr)
        return override

    padrao_seguranca = "2026-05"
    ano, mes = datetime.utcnow().year, datetime.utcnow().month
    for _ in range(6):
        candidato = f"{ano:04d}-{mes:02d}"
        url_teste = (
            f"https://arquivos.receitafederal.gov.br/public.php/webdav/"
            f"Dados/Cadastros/CNPJ/{candidato}/Empresas0.zip"
        )
        try:
            resultado = subprocess.run(
                [
                    "curl", "-u", f"{TOKEN_COMPARTILHAMENTO}:", "-s", "-o", "/dev/null",
                    "-w", "%{http_code}", "-I", "-L", "--max-time", "15", url_teste,
                ],
                capture_output=True, text=True,
            )
            codigo = resultado.stdout.strip()
        except Exception as e:
            print(f"  [WARN] Falha ao verificar disponibilidade de {candidato}: {e}", file=sys.stderr)
            codigo = ""

        if codigo == "200":
            print(f"  [OK] Mes RF detectado automaticamente: {candidato}", file=sys.stderr)
            return candidato

        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1

    print(f"  [WARN] Nao foi possivel detectar o mes RF automaticamente; usando padrao {padrao_seguranca}.", file=sys.stderr)
    return padrao_seguranca


MES_REFERENCIA_RF = detectar_mes_rf()

BASE_URL_RF = (
    f"https://arquivos.receitafederal.gov.br/public.php/webdav/"
    f"Dados/Cadastros/CNPJ/{MES_REFERENCIA_RF}/"
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



def _zip_valido(caminho: Path) -> bool:
    """Confere se o arquivo existe e e um zip integro. Um download
    interrompido deixa um .zip truncado que passaria pelo teste
    'destino.exists()' e depois quebraria na leitura -- ou pior, seria
    salvo no cache do GitHub Actions e contaminaria as proximas execucoes."""
    if not caminho.exists() or caminho.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(caminho) as z:
            return z.testzip() is None
    except zipfile.BadZipFile:
        return False


def baixar_rf(arquivo: str) -> Path:
    """Baixa um arquivo da Receita com retomada e retentativas.

    - curl -C - retoma de onde parou (nao rebaixa o que ja veio).
    - --retry cobre erros transitorios de rede/HTTP do proprio curl.
    - Um laco externo revalida o zip: se o download terminou corrompido,
      apaga e rebaixa; se foi interrompido, mantem o parcial e retoma.
    - --no-progress-meter em vez de --progress-bar: com downloads paralelos
      as barras se misturavam e geravam dezenas de milhares de linhas de log.

    Nao levanta excecao: quem chama (stage_download_rf) faz a checagem final
    de integridade e decide se o estagio falhou."""
    destino = RAW / arquivo
    if _zip_valido(destino):
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
        if resultado.returncode == 0 and _zip_valido(destino):
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


def baixar_pgfn(arquivo: str) -> Path:
    destino = RAW / arquivo
    if destino.exists():
        print(f"  [PULSO] {arquivo} ja existe — pulando.")
        return destino
    url = URL_BASE_PGFN_INDEX + ultimo_trimestre + "/" + arquivo
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
    """Trimestre PGFN configurado por variavel de ambiente."""
    trimestre = os.environ.get("PGFN_TRIMESTRE", "2026_trimestre_01").strip().strip("/")
    if not trimestre:
        trimestre = "2026_trimestre_01"
    return f"{trimestre}/"


ultimo_trimestre = detectar_trimestre_pgfn()


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
                            selecao = res[[0, 1, 2, 3, 4]]
                            selecao.columns = [
                                "CNPJ_BASICO", "IDENTIFICADOR_SOCIO",
                                "NOME_SOCIO", "CPF_CNPJ_SOCIO", "QUALIF_SOCIO",
                            ]
                            modo = "w" if primeira_gravacao else "a"
                            cabecalho = primeira_gravacao
                            selecao.to_csv(destino, sep=";", index=False, encoding="utf-8", mode=modo, header=cabecalho)
                            primeira_gravacao = False
    print("✅ Sócios extraídos.")


def processar_municipios() -> None:
    """Extrai a tabela de codigo->nome de municipios (baixada em Municipios.zip)
    para out/municipios.csv. Usada para resolver COD_MUNICIPIO em nome da cidade."""
    print("\n\U0001F3D9  Etapa: Processando tabela de Municipios...")
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
    print(f"\u2705 Municipios processados: {len(df_mun)}")


def processar_cnaes() -> None:
    """Extrai a tabela de codigo->descricao de CNAEs (baixada em Cnaes.zip)
    para out/cnaes.csv. Usada para traduzir CNAE_PRINCIPAL (que vem so como
    codigo, ex: '6201100') no nome da atividade economica -- igual ao que o
    app legado (LegadoStream/engine_dados.py) fazia com um cnaes.csv fixo."""
    print("\n\U0001F4D6  Etapa: Processando tabela de CNAEs...")
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
    print(f"\u2705 CNAEs processados: {len(df_cnae)}")


def consolidar_dividas_pgfn() -> pd.DataFrame:
    """Consolida dividas ativas da PGFN, separando por tipo (NAO_PREVIDENCIARIA,
    PREVIDENCIARIA, FGTS). Gera colunas DIVIDA_FEDERAL, DIVIDA_PREVIDENCIARIA,
    DIVIDA_FGTS e DIVIDA_TOTAL (soma de todas)."""
    print("\n💰 Etapa: Consolidação de Dívida Ativa (PGFN)...")
    # Acumuladores por tipo de dívida
    por_tipo = {
        "federal": [],   # Dados_abertos_Nao_Previdenciario
        "previdenciaria": [],  # Dados_abertos_Previdenciario
        "fgts": [],      # Dados_abertos_FGTS
    }

    mapeamento_arquivos = [
        ("Dados_abertos_Nao_Previdenciario.zip", "federal"),
        ("Dados_abertos_Previdenciario.zip", "previdenciaria"),
        ("Dados_abertos_FGTS.zip", "fgts"),
    ]

    for arq_pgfn, tipo in mapeamento_arquivos:
        arq_zip_path = RAW / arq_pgfn
        if not arq_zip_path.exists():
            print(f"  [PULSO] {arq_pgfn} não encontrado, pulando {tipo}.")
            continue
        print(f"📦 Lendo PGFN ({tipo}): {arq_pgfn}")
        with zipfile.ZipFile(arq_zip_path) as z:
            for f_name in z.namelist():
                with z.open(f_name) as f:
                    chunks = pd.read_csv(
                        f, sep=";", encoding="latin1", header=None,
                        dtype=str, chunksize=CHUNK_SIZE, low_memory=False,
                    )
                    for chunk in chunks:
                        if 0 in chunk.columns and 4 in chunk.columns:
                            cnpj = (
                                chunk[0]
                                .astype(str)
                                .str.replace(r"\D", "", regex=True)
                                .str.zfill(14)
                                .str[:8]
                            )
                            valor = pd.to_numeric(
                                chunk[4].astype(str).str.replace(",", ".", regex=False),
                                errors="coerce",
                            ).fillna(0.0)
                            por_tipo[tipo].append(
                                pd.DataFrame({"CNPJ_BASICO": cnpj, "VALOR": valor})
                            )

    # Consolida cada tipo separadamente
    df_dividas = pd.DataFrame(columns=["CNPJ_BASICO"])
    totais_tipo = {}

    for tipo in ("federal", "previdenciaria", "fgts"):
        if por_tipo[tipo]:
            df_tipo = pd.concat(por_tipo[tipo], ignore_index=True)
            df_tipo = df_tipo.groupby("CNPJ_BASICO")["VALOR"].sum().reset_index()
            nome_coluna = f"DIVIDA_{tipo.upper()}"
            df_tipo.rename(columns={"VALOR": nome_coluna}, inplace=True)
            totais_tipo[tipo] = len(df_tipo)
            df_dividas = df_dividas.merge(df_tipo, on="CNPJ_BASICO", how="outer")
        else:
            df_dividas[f"DIVIDA_{tipo.upper()}"] = 0.0
            totais_tipo[tipo] = 0

    # Preenche NaN com 0 nas colunas de dívida
    for col in ("DIVIDA_FEDERAL", "DIVIDA_PREVIDENCIARIA", "DIVIDA_FGTS"):
        if col in df_dividas.columns:
            df_dividas[col] = df_dividas[col].fillna(0.0)
        else:
            df_dividas[col] = 0.0

    # DIVIDA_TOTAL = soma dos 3 tipos
    df_dividas["DIVIDA_TOTAL"] = (
        df_dividas["DIVIDA_FEDERAL"]
        + df_dividas["DIVIDA_PREVIDENCIARIA"]
        + df_dividas["DIVIDA_FGTS"]
    )

    # Reordena colunas
    df_dividas = df_dividas[
        ["CNPJ_BASICO", "DIVIDA_FEDERAL", "DIVIDA_PREVIDENCIARIA", "DIVIDA_FGTS", "DIVIDA_TOTAL"]
    ]

    # Persiste pro estágio de merge poder rodar isolado (pipeline fracionado).
    df_dividas.to_csv(OUT / "aux_dividas_pgfn.csv", sep=";", index=False, encoding="utf-8")
    print(f"✅ Dívidas consolidadas: {len(df_dividas)} empresas.")
    print(f"   - Federal: {totais_tipo['federal']} | Previdenciária: {totais_tipo['previdenciaria']} | FGTS: {totais_tipo['fgts']}")
    return df_dividas


def _carregar_empresas_aux() -> pd.DataFrame:
    """Le aux_nomes_empresas.csv (saida de filtrar_empresas). Usado pelo
    estagio de merge quando rodado isolado."""
    caminho = OUT / "aux_nomes_empresas.csv"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao encontrado. Rode antes o estagio 'process-rf'."
        )
    return pd.read_csv(caminho, sep=";", encoding="utf-8", dtype=str)


def _carregar_dividas_aux() -> pd.DataFrame:
    """Le aux_dividas_pgfn.csv (saida de consolidar_dividas_pgfn). Se nao
    existir (estagio PGFN nunca rodou), devolve vazio -- o merge segue sem
    dados de divida em vez de quebrar."""
    caminho = OUT / "aux_dividas_pgfn.csv"
    if not caminho.exists():
        print(f"  [AVISO] {caminho.name} nao encontrado -- master sem dados de divida.")
        return pd.DataFrame(columns=["CNPJ_BASICO", "DIVIDA_FEDERAL", "DIVIDA_PREVIDENCIARIA", "DIVIDA_FGTS", "DIVIDA_TOTAL"])
    return pd.read_csv(caminho, sep=";", encoding="utf-8", dtype=str)


def gerar_master(df_emp: pd.DataFrame = None, df_dividas: pd.DataFrame = None) -> pd.DataFrame:
    """Gera o arquivo final subset_rs_final_completo.csv.

    df_emp/df_dividas sao opcionais: se nao passados (estagio de merge rodando
    isolado), sao lidos dos CSVs auxiliares gravados pelos estagios anteriores.
    """
    print("\n🚀 Etapa Final: Gerando Master...")
    if df_emp is None:
        df_emp = _carregar_empresas_aux()
    if df_dividas is None:
        df_dividas = _carregar_dividas_aux()

    df_estab = pd.read_csv(OUT / "aux_estab_rs.csv", sep=";", encoding="latin1", dtype=str)

    master = df_estab.merge(df_emp, on="CNPJ_BASICO", how="left")
    master = master.merge(df_dividas, on="CNPJ_BASICO", how="left")

    master["CONTATO_FONE"] = "(" + master["DDD"].fillna("") + ") " + master["TELEFONE"].fillna("")
    master["CAPITAL_SOCIAL"] = pd.to_numeric(master["CAPITAL_SOCIAL"].astype(str).str.replace(",", "."), errors="coerce").fillna(0.0)
    master["DIVIDA_TOTAL"] = pd.to_numeric(master["DIVIDA_TOTAL"], errors="coerce").fillna(0.0)

    ARQUIVO_FINAL = OUT / "subset_rs_final_completo.csv"
    master.to_csv(ARQUIVO_FINAL, sep=";", index=False, encoding="latin1")
    print(f"\n✅ PROCESSO FINALIZADO! Total de Matrizes Ativas no RS: {len(master)}")
    print(f"📂 Local: {ARQUIVO_FINAL}")
    return master


def _escrever_metadata(total_matrizes: int) -> None:
    """Grava metadata da execucao (mes/trimestre usados, quantidade final)
    num JSON ao lado dos CSVs de saida. O script de sincronizacao
    (scripts/sync_data_to_db.py) le esse arquivo e registra no banco, pra a
    tela "Sobre" no frontend mostrar quando os dados foram atualizados por
    ultimo e com base em qual periodo de referencia."""
    metadata = {
        "mes_referencia_rf": MES_REFERENCIA_RF,
        "trimestre_pgfn": ultimo_trimestre.rstrip("/"),
        "gerado_em": datetime.utcnow().isoformat() + "Z",
        "total_matrizes": int(total_matrizes),
    }
    with open(OUT / "metadata_pipeline.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\n📝 Metadata gravado: {metadata}")


def _cabecalho(titulo: str) -> None:
    print("=" * 60)
    print(f"PIPELINE RS MASTER 2026 — {titulo}")
    print(f"Raw: {RAW}  |  Out: {OUT}")
    print(f"Mes RF: {MES_REFERENCIA_RF}  |  Trimestre PGFN: {ultimo_trimestre.rstrip('/')}")
    print("=" * 60)


# =================================================================
# ESTAGIOS -- o pipeline foi fracionado pra rodar por partes no GitHub
# Actions (ver .github/workflows/etl.yml). Cada estagio le a saida do
# anterior dos CSVs em out/, entao um estagio pode ser re-executado
# isolado sem refazer os 3h de download + processamento inteiros.
# =================================================================

def stage_detect() -> None:
    """Imprime em stdout as variaveis de referencia detectadas, no formato
    KEY=VALUE (o workflow faz 'pipeline.py detect | grep ... >> $GITHUB_ENV'
    pra fixar o mes/trimestre nos estagios seguintes e nao ficar sondando o
    servidor da Receita de novo a cada passo)."""
    print(f"RF_MES_REFERENCIA={MES_REFERENCIA_RF}")
    print(f"PGFN_TRIMESTRE={ultimo_trimestre.rstrip('/')}")


def _baixar_lista(titulo: str, arquivos: list) -> None:
    """Baixa uma lista de arquivos RF em paralelo (RF_DOWNLOAD_WORKERS conexoes)
    e falha o estagio se algum zip ficar invalido apos as retentativas -- assim
    o cache guarda so o que presta e o 'Re-run failed jobs' retoma so o que
    faltou. Usado pelos sub-estagios de download (empresas/estab/socios)."""
    _cabecalho(f"DOWNLOAD {titulo}")
    workers = max(1, int(os.environ.get("RF_DOWNLOAD_WORKERS", "5")))
    print(f"Baixando {len(arquivos)} arquivos com ate {workers} conexoes paralelas...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {executor.submit(baixar_rf, arq): arq for arq in arquivos}
        for fut in as_completed(futuros):
            arq = futuros[fut]
            try:
                fut.result()
            except Exception as e:  # baixar_rf nao levanta, mas por seguranca
                print(f"  [ERRO] Excecao inesperada ao baixar {arq}: {e}")

    invalidos = [a for a in arquivos if not _zip_valido(RAW / a)]
    if invalidos:
        raise SystemExit(f"Download {titulo} incompleto — zips invalidos: {invalidos}")
    print(f"\n🏁 Download {titulo} concluido (todos os zips integros).")


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
    """Baixa todos os arquivos RF -- wrapper dos 3 sub-estagios (modo 'all'
    local). No GitHub Actions cada sub-estagio roda separado, com timeout
    proprio e re-executavel isolado."""
    stage_download_rf_empresas()
    stage_download_rf_estab()
    stage_download_rf_socios()


def stage_download_pgfn() -> None:
    _cabecalho("DOWNLOAD PGFN")
    for arq in PGFN:
        baixar_pgfn(arq)
    print("\n🏁 Download PGFN concluido.")


def _carregar_cnpjs_rs() -> set:
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


def stage_process_aux() -> None:
    """Municipios + CNAEs -- lookups rapidos (extrai um zip pequeno cada)."""
    _cabecalho("PROCESS AUX (municipios + cnaes)")
    processar_municipios()
    processar_cnaes()
    print("\n🏁 Aux (municipios + cnaes) concluido.")


def stage_process_estab() -> None:
    """Filtra as matrizes ativas do RS (o mais pesado: le os 10 zips de
    Estabelecimentos). Gera aux_estab_rs.csv, base dos estagios seguintes."""
    _cabecalho("PROCESS ESTABELECIMENTOS")
    filtrar_estabelecimentos()
    print("\n🏁 Estabelecimentos concluido.")


def stage_process_empresas() -> None:
    """Nomes / capital social das matrizes RS (le os 10 zips de Empresas)."""
    _cabecalho("PROCESS EMPRESAS")
    filtrar_empresas(_carregar_cnpjs_rs())
    print("\n🏁 Empresas concluido.")


def stage_process_socios() -> None:
    """Socios das matrizes RS (le os 10 zips de Socios)."""
    _cabecalho("PROCESS SOCIOS")
    filtrar_socios(_carregar_cnpjs_rs())
    print("\n🏁 Socios concluido.")


def stage_process_rf() -> None:
    """Roda os 4 sub-estagios de processamento RF em sequencia. Util pro modo
    'all' (local); no GitHub Actions cada sub-estagio roda separado, com
    timeout proprio e re-executavel isolado."""
    stage_process_aux()
    stage_process_estab()
    stage_process_empresas()
    stage_process_socios()
    print("\n🏁 Processamento RF concluido.")


def stage_process_pgfn() -> None:
    _cabecalho("PROCESS PGFN")
    consolidar_dividas_pgfn()
    print("\n🏁 Processamento PGFN concluido.")


def stage_merge() -> None:
    _cabecalho("MERGE")
    master = gerar_master()
    _escrever_metadata(len(master))
    print("\n🏁 Merge concluido.")


def rodar_pipeline() -> None:
    """Executa todos os estagios em sequencia (comportamento monolitico --
    util pra rodar localmente com um comando so)."""
    stage_download_rf()
    stage_download_pgfn()
    stage_process_rf()
    stage_process_pgfn()
    stage_merge()
    print("\n🏁 Pipeline concluído com sucesso!")


_STAGES = {
    "all": rodar_pipeline,
    "detect": stage_detect,
    # download-rf roda os 3 abaixo em sequencia; no CI cada um roda separado.
    "download-rf": stage_download_rf,
    "download-rf-empresas": stage_download_rf_empresas,
    "download-rf-estab": stage_download_rf_estab,
    "download-rf-socios": stage_download_rf_socios,
    "download-pgfn": stage_download_pgfn,
    # process-rf roda os 4 abaixo em sequencia; no CI cada um roda separado.
    "process-rf": stage_process_rf,
    "process-aux": stage_process_aux,
    "process-estab": stage_process_estab,
    "process-empresas": stage_process_empresas,
    "process-socios": stage_process_socios,
    "process-pgfn": stage_process_pgfn,
    "merge": stage_merge,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline ETL WhoDados (RS Master 2026)."
    )
    parser.add_argument(
        "stage", nargs="?", default="all", choices=list(_STAGES),
        help="Estagio a executar. Padrao: 'all' (pipeline completo).",
    )
    _STAGES[parser.parse_args().stage]()