"""
Extracao de dados de Divida Ativa da Uniao (PGFN).

Baixa e consolida os 3 zips publicados a cada trimestre em
https://dadosabertos.pgfn.gov.br/{ano}_trimestre_{NN}/ :

  - Dados_abertos_Nao_Previdenciario.zip  (divida federal / receita federal)
  - Dados_abertos_Previdenciario.zip      (divida previdenciaria / INSS)
  - Dados_abertos_FGTS.zip                (divida de FGTS / Caixa)

Gera aux_dividas_pgfn.csv com uma linha por CNPJ_BASICO e as colunas
DIVIDA_FEDERAL, DIVIDA_PREVIDENCIARIA, DIVIDA_FGTS e DIVIDA_TOTAL (soma
das 3). O estagio de merge (pipeline.py) junta esse aux com as empresas
do RS.

Este modulo *nao* toca em dados da Receita Federal (empresa/estab/socios)
-- isso e responsabilidade de pipeline_rf.py.

Diferente do pipeline_rf, aqui o trimestre e detectado automaticamente
sondando o servidor da PGFN de tras pra frente (assim nao precisa
atualizar PGFN_TRIMESTRE manualmente todo trimestre novo).

LOCAL: whodados/pipeline/pipeline_pgfn.py
Roda com: python whodados/pipeline/pipeline_pgfn.py <estagio>
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import time
import zipfile
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
URL_BASE_PGFN_INDEX = "https://dadosabertos.pgfn.gov.br/"

# Mapeamento (arquivo publicado) -> (tipo de divida na tabela final).
# A ordem determina como as colunas DIVIDA_* saem no CSV.
MAPEAMENTO_ARQUIVOS = [
    ("Dados_abertos_Nao_Previdenciario.zip", "federal"),
    ("Dados_abertos_Previdenciario.zip", "previdenciaria"),
    ("Dados_abertos_FGTS.zip", "fgts"),
]

PGFN = [nome for nome, _ in MAPEAMENTO_ARQUIVOS]

# Colunas de saida geradas por consolidar_dividas_pgfn (na ordem gravada
# no CSV auxiliar). Reexportadas pra pipeline.py usar no merge sem duplicar.
COLUNAS_DIVIDA = [
    "CNPJ_BASICO",
    "DIVIDA_FEDERAL",
    "DIVIDA_PREVIDENCIARIA",
    "DIVIDA_FGTS",
    "DIVIDA_TOTAL",
]


def _trimestre_de(hoje: datetime) -> tuple[int, int]:
    """Devolve (ano, trimestre 1..4) a partir de uma data."""
    return hoje.year, (hoje.month - 1) // 3 + 1


def detectar_trimestre_pgfn() -> str:
    """Detecta o trimestre mais recente publicado pela PGFN.

    Prioridade (mesmo esquema do RF em pipeline_rf.py):
    1. Variavel de ambiente PGFN_TRIMESTRE, se definida.
    2. Deteccao automatica: sonda o servidor da PGFN comecando pelo
       trimestre corrente e recuando (ate 5 trimestres -- ~15 meses),
       usando HEAD + fallback pra GET-range (ver diagnosticar_url).
    3. Se nenhum trimestre responder 200/206, FALHA (nao cai mais no
       fallback silencioso 2026_trimestre_01 -- isso mascarava o problema
       real. Pra debug pontual: PGFN_ALLOW_FALLBACK=1 e PGFN_FALLBACK_TRIMESTRE).
    """
    from pipeline_common import diagnosticar_url

    override = os.environ.get("PGFN_TRIMESTRE", "").strip().strip("/")
    if override:
        print(f"  [INFO] Trimestre PGFN fixado manualmente via PGFN_TRIMESTRE: {override}", file=sys.stderr)
        return f"{override}/"

    tentativas: list[tuple[str, str]] = []
    ano, tri = _trimestre_de(datetime.utcnow())
    for _ in range(5):
        candidato = f"{ano:04d}_trimestre_{tri:02d}"
        url_teste = f"{URL_BASE_PGFN_INDEX}{candidato}/Dados_abertos_FGTS.zip"
        diag = diagnosticar_url(url_teste)
        tentativas.append((candidato, diag.codigo))
        print(f"  [SONDA] {candidato} -> HTTP {diag.codigo}", file=sys.stderr)
        if diag.ok:
            print(f"  [OK] Trimestre PGFN detectado automaticamente: {candidato}", file=sys.stderr)
            return f"{candidato}/"
        tri -= 1
        if tri == 0:
            tri, ano = 4, ano - 1

    resumo = ", ".join(f"{c}={h}" for c, h in tentativas)
    permite_fallback = os.environ.get("PGFN_ALLOW_FALLBACK", "").strip().lower() in ("1", "true", "yes")
    if permite_fallback:
        fallback = os.environ.get("PGFN_FALLBACK_TRIMESTRE", "").strip() or "2026_trimestre_01"
        print(f"  [WARN] Nenhum trimestre PGFN respondeu 200 ({resumo}); usando fallback {fallback} (PGFN_ALLOW_FALLBACK=1).", file=sys.stderr)
        return f"{fallback}/"

    hint = ""
    codigos = {c for _, c in tentativas}
    if codigos.issubset({"000", "erro", "no-curl"}):
        hint = " (todos timeout/erro -- servidor da PGFN fora ou rede do runner)"
    elif codigos.issubset({"404", "403"}):
        hint = " (todos 404/403 -- URL/schema pode ter mudado no servidor da PGFN)"

    raise SystemExit(
        f"Nao foi possivel detectar o trimestre PGFN automaticamente. Tentativas: {resumo}.{hint} "
        f"Pra rodar mesmo assim, defina PGFN_ALLOW_FALLBACK=1 (com PGFN_FALLBACK_TRIMESTRE opcional) "
        f"ou passe PGFN_TRIMESTRE=<AAAA_trimestre_NN> pra fixar um trimestre especifico."
    )


ULTIMO_TRIMESTRE = detectar_trimestre_pgfn()


# ----------------------------------------------------------------
# DOWNLOAD
# ----------------------------------------------------------------
def baixar_pgfn(arquivo: str) -> Path:
    """Baixa um arquivo da PGFN com retomada e retentativas.

    Usa curl com o mesmo esquema do pipeline_rf (nao mais wget silencioso)
    pra que download falhado seja detectavel: quem chama (stage_download_pgfn)
    revalida os zips no fim e falha o estagio se algum ficou invalido.

    Nao levanta excecao: apenas devolve o caminho, integro ou nao."""
    destino = RAW / arquivo
    if zip_valido(destino):
        print(f"  [PULO] {arquivo} ja existe e esta integro.")
        return destino

    url = URL_BASE_PGFN_INDEX + ULTIMO_TRIMESTRE + arquivo
    tentativas = max(1, int(os.environ.get("PGFN_DOWNLOAD_RETRIES", "4")))
    for tentativa in range(1, tentativas + 1):
        cmd = [
            "curl", "-L", "-C", "-",
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
            print(f"  [RETRY] {arquivo}: baixou mas o zip esta corrompido "
                  f"(tentativa {tentativa}/{tentativas}); rebaixando do zero.")
            if destino.exists():
                destino.unlink()
        else:
            print(f"  [RETRY] {arquivo}: interrompido (exit {resultado.returncode}, "
                  f"tentativa {tentativa}/{tentativas}); vai retomar.")
            time.sleep(3)

    print(f"  [ERRO] {arquivo}: falhou apos {tentativas} tentativas.")
    return destino


# ----------------------------------------------------------------
# PROCESSAMENTO
# ----------------------------------------------------------------
def consolidar_dividas_pgfn() -> pd.DataFrame:
    """Consolida dividas ativas da PGFN, separando por tipo (NAO_PREVIDENCIARIA,
    PREVIDENCIARIA, FGTS). Gera colunas DIVIDA_FEDERAL, DIVIDA_PREVIDENCIARIA,
    DIVIDA_FGTS e DIVIDA_TOTAL (soma de todas)."""
    print("\n[Etapa] Consolidando Divida Ativa (PGFN)...")

    por_tipo: dict[str, list[pd.DataFrame]] = {
        "federal": [],
        "previdenciaria": [],
        "fgts": [],
    }

    for arq_pgfn, tipo in MAPEAMENTO_ARQUIVOS:
        arq_zip_path = RAW / arq_pgfn
        if not arq_zip_path.exists():
            print(f"  [PULO] {arq_pgfn} nao encontrado, pulando {tipo}.")
            continue
        print(f"  Lendo PGFN ({tipo}): {arq_pgfn}")
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

    # Consolida cada tipo separadamente.
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

    for col in ("DIVIDA_FEDERAL", "DIVIDA_PREVIDENCIARIA", "DIVIDA_FGTS"):
        if col in df_dividas.columns:
            df_dividas[col] = df_dividas[col].fillna(0.0)
        else:
            df_dividas[col] = 0.0

    df_dividas["DIVIDA_TOTAL"] = (
        df_dividas["DIVIDA_FEDERAL"]
        + df_dividas["DIVIDA_PREVIDENCIARIA"]
        + df_dividas["DIVIDA_FGTS"]
    )

    df_dividas = df_dividas[COLUNAS_DIVIDA]

    df_dividas.to_csv(OUT / "aux_dividas_pgfn.csv", sep=";", index=False, encoding="utf-8")
    print(f"OK Dividas consolidadas: {len(df_dividas)} empresas.")
    print(f"   - Federal: {totais_tipo['federal']} | Previdenciaria: {totais_tipo['previdenciaria']} | FGTS: {totais_tipo['fgts']}")
    return df_dividas


def carregar_dividas_aux() -> pd.DataFrame:
    """Le aux_dividas_pgfn.csv (saida de consolidar_dividas_pgfn). Se nao
    existir (estagio PGFN nunca rodou), devolve vazio -- o merge segue sem
    dados de divida em vez de quebrar."""
    caminho = OUT / "aux_dividas_pgfn.csv"
    if not caminho.exists():
        print(f"  [AVISO] {caminho.name} nao encontrado -- master sem dados de divida.")
        return pd.DataFrame(columns=COLUNAS_DIVIDA)
    return pd.read_csv(caminho, sep=";", encoding="utf-8", dtype=str)


# ----------------------------------------------------------------
# ESTAGIOS
# ----------------------------------------------------------------
def _preflight_pgfn() -> None:
    """Antes de baixar os 3 zips grandes, testa se a URL do primeiro ja
    responde. Se der 404 (trimestre errado) ou 5xx (servidor fora),
    aborta com diagnostico -- sem gastar retries em vao."""
    faltando = [a for a in PGFN if not zip_valido(RAW / a)]
    if not faltando:
        print(f"  [PREFLIGHT] Todos os {len(PGFN)} arquivos PGFN ja estao em cache. Pulando.")
        return
    alvo = faltando[0]
    url = URL_BASE_PGFN_INDEX + ULTIMO_TRIMESTRE + alvo
    print(f"  [PREFLIGHT] Testando acesso: {alvo}")
    diag = diagnosticar_url(url)
    imprimir_diagnostico(alvo, url, diag)
    if not diag.ok:
        # Dica extra: 404 no PGFN quase sempre e trimestre desatualizado.
        if diag.codigo == "404":
            print(
                f"  [DICA] Trimestre atual configurado: {ULTIMO_TRIMESTRE.rstrip('/')}. "
                f"A deteccao automatica pode estar apontando pra um trimestre que ja "
                f"saiu do ar. Confira em {URL_BASE_PGFN_INDEX} qual trimestre esta "
                f"listado atualmente.",
                file=sys.stderr,
            )
        abortar_com_diagnostico("DOWNLOAD PGFN", url, diag)


def stage_download_pgfn() -> None:
    """Baixa os 3 arquivos da PGFN, com preflight que aborta cedo em erro
    nao-transitorio, e falha o estagio se algum ficar invalido.

    Diferente da versao antiga que so imprimia [WARN] em erro (mascarando
    dividas zeradas no master), agora um download quebrado quebra o estagio
    -- e a variavel de ambiente PGFN_ALLOW_EMPTY permite passar mesmo assim
    (caso seja proposital rodar sem dividas)."""
    cabecalho("DOWNLOAD PGFN", {"Trimestre PGFN": ULTIMO_TRIMESTRE.rstrip("/")})
    _preflight_pgfn()

    sucessos: list[str] = []
    falhas: list[str] = []
    for arq in PGFN:
        try:
            baixar_pgfn(arq)
        except Exception as e:
            print(f"  [ERRO] Excecao inesperada ao baixar {arq}: {e}")
        if zip_valido(RAW / arq):
            sucessos.append(arq)
        else:
            falhas.append(arq)

    print(f"\n[RESUMO] PGFN: {len(sucessos)} ok, {len(falhas)} falhas.")
    if falhas:
        permite_vazio = os.environ.get("PGFN_ALLOW_EMPTY", "").strip().lower() in ("1", "true", "yes")
        alvo = falhas[0]
        url = URL_BASE_PGFN_INDEX + ULTIMO_TRIMESTRE + alvo
        print(f"[FALHA] Investigando '{alvo}' pra reportar o motivo real:")
        diag = diagnosticar_url(url)
        imprimir_diagnostico(alvo, url, diag)
        msg = (
            f"Download PGFN incompleto -- {len(falhas)} zip(s) invalido(s): {falhas}. "
            f"Trimestre usado: {ULTIMO_TRIMESTRE.rstrip('/')}. Motivo mais provavel: "
            f"{diag.motivo} ({diag.detalhe})."
        )
        if permite_vazio:
            print(f"  [WARN] {msg} (PGFN_ALLOW_EMPTY=1, seguindo mesmo assim)")
        else:
            raise SystemExit(msg)
    print(f"OK Download PGFN concluido ({len(sucessos)} zips integros).")


def stage_process_pgfn() -> None:
    """Consolida as dividas em aux_dividas_pgfn.csv (soma por CNPJ_BASICO)."""
    cabecalho("PROCESS PGFN", {"Trimestre PGFN": ULTIMO_TRIMESTRE.rstrip("/")})
    consolidar_dividas_pgfn()
    print("\nOK Processamento PGFN concluido.")


_STAGES = {
    "download-pgfn": stage_download_pgfn,
    "process-pgfn": stage_process_pgfn,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline ETL WhoDados -- PGFN (divida ativa)."
    )
    parser.add_argument(
        "stage", choices=list(_STAGES),
        help="Estagio a executar.",
    )
    _STAGES[parser.parse_args().stage]()
