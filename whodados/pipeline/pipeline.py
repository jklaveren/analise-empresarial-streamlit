# =================================================================
# PIPELINE DE EXTRACAO RS MASTER 2026 -- Orquestrador
# LOCAL: whodados/pipeline/pipeline.py
#
# Este arquivo virou fino: a logica esta em pipeline_rf.py e pipeline_pgfn.py
# (fracionado por origem do dado). Aqui ficam apenas:
#   - o dispatch da CLI (mantido igual pra nao quebrar o workflow existente),
#   - o estagio 'detect' que exporta variaveis pros estagios seguintes,
#   - o estagio 'merge' que junta os dois lados (empresa+divida).
#
# Roda com: python whodados/pipeline/pipeline.py <estagio>
# =================================================================
from __future__ import annotations
import argparse
import json
from datetime import datetime

import pandas as pd

from pipeline_common import (
    OUT, cabecalho, diagnosticar_url, imprimir_diagnostico,
)
import pipeline_rf
import pipeline_pgfn


# ----------------------------------------------------------------
# DETECCAO CONSOLIDADA
# ----------------------------------------------------------------
def stage_detect() -> None:
    """Imprime em stdout as variaveis de referencia detectadas, no formato
    KEY=VALUE (o workflow faz 'pipeline.py detect | grep ... >> $GITHUB_ENV'
    pra fixar mes/trimestre nos estagios seguintes e nao ficar sondando os
    servidores da Receita/PGFN de novo a cada passo).

    Como pipeline_rf e pipeline_pgfn detectam no import, basta imprimir o
    que ja ficou nos modulos."""
    print(f"RF_MES_REFERENCIA={pipeline_rf.MES_REFERENCIA_RF}")
    print(f"PGFN_TRIMESTRE={pipeline_pgfn.ULTIMO_TRIMESTRE.rstrip('/')}")


def stage_diagnose() -> None:
    """Bateria rapida de auto-diagnostico -- roda em ~30s e imprime o
    estado de tudo que o pipeline depende:

    - Token RF (existe? bate no servidor da Receita? qual HTTP code?)
    - URL RF (Empresas0.zip do mes detectado)
    - URL PGFN (FGTS.zip do trimestre detectado)
    - DATABASE_URL (existe? consegue conectar ao Supabase?)

    Nao baixa nada. Nao muda nada. Serve pra saber se vale a pena disparar
    a run completa (2h+) ou se ja tem um problema conhecido a resolver
    antes (renovar token, ajustar variavel, etc.).

    Roda com: python pipeline.py diagnose
    """
    cabecalho(
        "AUTO-DIAGNOSTICO",
        {
            "Mes RF": pipeline_rf.MES_REFERENCIA_RF,
            "Trimestre PGFN": pipeline_pgfn.ULTIMO_TRIMESTRE.rstrip("/"),
        },
    )
    problemas: list[str] = []

    # -------- Token RF --------
    token = pipeline_rf.TOKEN_COMPARTILHAMENTO
    if not token:
        problemas.append("RF_SHARE_TOKEN vazio (sem token)")
        print("  !! Token RF: nao configurado (RF_SHARE_TOKEN vazio).")
    else:
        # Nao imprimir o token inteiro (mesmo em log de CI): so tamanho.
        print(f"  OK Token RF: presente ({len(token)} chars).")

    # -------- Endpoint RF --------
    url_rf = pipeline_rf.BASE_URL_RF + "Empresas0.zip"
    print(f"\n  Sondando RF: {url_rf}")
    diag_rf = diagnosticar_url(url_rf, auth=f"{token}:")
    imprimir_diagnostico("RF Empresas0.zip", url_rf, diag_rf)
    if not diag_rf.ok:
        problemas.append(f"RF nao acessivel ({diag_rf.motivo})")

    # -------- Endpoint PGFN --------
    url_pgfn = (
        pipeline_pgfn.URL_BASE_PGFN_INDEX
        + pipeline_pgfn.ULTIMO_TRIMESTRE
        + "Dados_abertos_FGTS.zip"
    )
    print(f"\n  Sondando PGFN: {url_pgfn}")
    diag_pgfn = diagnosticar_url(url_pgfn)
    imprimir_diagnostico("PGFN FGTS.zip", url_pgfn, diag_pgfn)
    if not diag_pgfn.ok:
        problemas.append(f"PGFN nao acessivel ({diag_pgfn.motivo})")

    # -------- DATABASE_URL --------
    import os
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("\n  -- DATABASE_URL nao configurada. Sync com Supabase seria pulada.")
    else:
        print("\n  Testando conexao com Supabase...")
        try:
            import psycopg2  # importa so aqui pra diagnose funcionar sem a dep
            conn = psycopg2.connect(db_url, connect_timeout=10)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            conn.close()
            print("  OK Supabase: conexao OK.")
        except Exception as e:
            print(f"  !! Supabase: falha ao conectar -- {e}")
            problemas.append("Supabase inacessivel")

    # -------- Resumo --------
    print("\n" + "=" * 60)
    if problemas:
        print(f"[DIAGNOSTICO] {len(problemas)} problema(s) encontrado(s):")
        for p in problemas:
            print(f"  - {p}")
        print("\nCorriga os itens acima antes de disparar a run completa.")
        raise SystemExit(1)
    else:
        print("[DIAGNOSTICO] Tudo OK. Pode disparar a run completa.")


# ----------------------------------------------------------------
# MERGE (junta as duas origens)
# ----------------------------------------------------------------
def gerar_master() -> pd.DataFrame:
    """Junta empresas RS (pipeline_rf) com dividas PGFN (pipeline_pgfn) em
    subset_rs_final_completo.csv. Le sempre dos CSVs auxiliares -- assim
    pode rodar isolado dos estagios de processamento."""
    print("\n[Etapa Final] Gerando Master...")

    df_emp = pipeline_rf.carregar_empresas_aux()
    df_dividas = pipeline_pgfn.carregar_dividas_aux()
    df_estab = pd.read_csv(OUT / "aux_estab_rs.csv", sep=";", encoding="latin1", dtype=str)

    master = df_estab.merge(df_emp, on="CNPJ_BASICO", how="left")
    master = master.merge(df_dividas, on="CNPJ_BASICO", how="left")

    master["CONTATO_FONE"] = "(" + master["DDD"].fillna("") + ") " + master["TELEFONE"].fillna("")
    master["CAPITAL_SOCIAL"] = pd.to_numeric(
        master["CAPITAL_SOCIAL"].astype(str).str.replace(",", "."), errors="coerce"
    ).fillna(0.0)
    # Converte as 4 colunas de divida (federal, previdenciaria, fgts, total)
    # de string pra numerico e preenche ausencias com 0 -- empresas sem divida
    # nao aparecem no aux_dividas_pgfn, entao viram NaN no merge.
    for col in ("DIVIDA_FEDERAL", "DIVIDA_PREVIDENCIARIA", "DIVIDA_FGTS", "DIVIDA_TOTAL"):
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors="coerce").fillna(0.0)
        else:
            master[col] = 0.0

    arquivo_final = OUT / "subset_rs_final_completo.csv"
    master.to_csv(arquivo_final, sep=";", index=False, encoding="latin1")
    print(f"\nOK PROCESSO FINALIZADO! Total de Matrizes Ativas no RS: {len(master)}")
    print(f"   Local: {arquivo_final}")
    return master


def _escrever_metadata(total_matrizes: int) -> None:
    """Grava metadata da execucao (mes/trimestre usados, quantidade final)
    num JSON ao lado dos CSVs de saida. O script de sincronizacao
    (scripts/sync_data_to_db.py) le esse arquivo e registra no banco, pra a
    tela "Sobre" no frontend mostrar quando os dados foram atualizados por
    ultimo e com base em qual periodo de referencia."""
    metadata = {
        "mes_referencia_rf": pipeline_rf.MES_REFERENCIA_RF,
        "trimestre_pgfn": pipeline_pgfn.ULTIMO_TRIMESTRE.rstrip("/"),
        "gerado_em": datetime.utcnow().isoformat() + "Z",
        "total_matrizes": int(total_matrizes),
    }
    with open(OUT / "metadata_pipeline.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\nOK Metadata gravado: {metadata}")


def stage_merge() -> None:
    cabecalho(
        "MERGE",
        {
            "Mes RF": pipeline_rf.MES_REFERENCIA_RF,
            "Trimestre PGFN": pipeline_pgfn.ULTIMO_TRIMESTRE.rstrip("/"),
        },
    )
    master = gerar_master()
    _escrever_metadata(len(master))
    print("\nOK Merge concluido.")


# ----------------------------------------------------------------
# WRAPPER MONOLITICO (util pra rodar local com um comando so)
# ----------------------------------------------------------------
def rodar_pipeline() -> None:
    """Executa todos os estagios em sequencia -- comportamento monolitico.
    No GitHub Actions cada estagio roda separado (ver .github/workflows/
    whodados-etl.yml)."""
    pipeline_rf.stage_download_rf()
    pipeline_pgfn.stage_download_pgfn()
    pipeline_rf.stage_process_rf()
    pipeline_pgfn.stage_process_pgfn()
    stage_merge()
    print("\nOK Pipeline concluido com sucesso!")


# ----------------------------------------------------------------
# CLI (mantida compativel com o workflow do GitHub Actions)
# ----------------------------------------------------------------
# Todos os estagios existentes continuam disponiveis por nome, so que agora
# rotam pros modulos corretos (RF ou PGFN) em vez de tudo estar aqui.
_STAGES = {
    "all": rodar_pipeline,
    "detect": stage_detect,
    "diagnose": stage_diagnose,
    # RF
    "download-rf": pipeline_rf.stage_download_rf,
    "download-rf-empresas": pipeline_rf.stage_download_rf_empresas,
    "download-rf-estab": pipeline_rf.stage_download_rf_estab,
    "download-rf-socios": pipeline_rf.stage_download_rf_socios,
    "process-rf": pipeline_rf.stage_process_rf,
    "process-aux": pipeline_rf.stage_process_aux,
    "process-estab": pipeline_rf.stage_process_estab,
    "process-empresas": pipeline_rf.stage_process_empresas,
    "process-socios": pipeline_rf.stage_process_socios,
    # PGFN
    "download-pgfn": pipeline_pgfn.stage_download_pgfn,
    "process-pgfn": pipeline_pgfn.stage_process_pgfn,
    # Merge junta as duas origens
    "merge": stage_merge,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline ETL WhoDados (RS Master 2026) -- orquestrador."
    )
    parser.add_argument(
        "stage", nargs="?", default="all", choices=list(_STAGES),
        help="Estagio a executar. Padrao: 'all' (pipeline completo).",
    )
    _STAGES[parser.parse_args().stage]()
