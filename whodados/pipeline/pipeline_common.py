"""
Utilitarios compartilhados entre pipeline_rf.py e pipeline_pgfn.py.

Fica aqui tudo que os dois modulos de origem de dados precisam usar em
comum: descoberta do BASE_DIR (raiz do projeto), pastas raw/ e out/,
tamanho de chunk pra leitura em streaming e helpers de validacao de zip
e log.

LOCAL: whodados/pipeline/pipeline_common.py
"""
from __future__ import annotations
import os
import sys
import zipfile
from pathlib import Path


# ----------------------------------------------------------------
# CONFIGURACAO DE PATHS
# ----------------------------------------------------------------
# WHO_PROJECT_DIR e definida pelo workflow (${{ github.workspace }}/whodados)
# e tambem por rodar localmente via scripts .bat/.ps1. Como fallback, sobe
# arvore procurando o marcador do projeto.
if "WHO_PROJECT_DIR" in os.environ:
    BASE_DIR = Path(os.environ["WHO_PROJECT_DIR"])
else:
    _candidato = Path(__file__).resolve().parent.parent
    _RAIZ_ENCONTRADA = False
    while _candidato.parent != _candidato:
        if (_candidato / "setup.py").exists() or (_candidato / "backend").exists():
            BASE_DIR = _candidato
            _RAIZ_ENCONTRADA = True
            break
        _candidato = _candidato.parent
    if not _RAIZ_ENCONTRADA:
        print("ERROR: Nao foi possivel localizar o diretorio raiz do projeto.")
        print("Defina a variavel de ambiente WHO_PROJECT_DIR apontando para a pasta whodados/.")
        sys.exit(1)

RAW = BASE_DIR / "pipeline" / "raw"
OUT = BASE_DIR / "pipeline" / "out"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

# Tamanho do chunk usado por pd.read_csv nos zips gigantes da Receita/PGFN.
# 500k linhas costuma caber tranquilo em memoria (~200-400 MB dependendo do
# numero de colunas) e da bom throughput.
CHUNK_SIZE = 500_000


def zip_valido(caminho: Path) -> bool:
    """Confere se o arquivo existe e e um zip integro.

    Um download interrompido deixa um .zip truncado que passaria pelo teste
    'destino.exists()' e depois quebraria na leitura -- ou pior, seria salvo
    no cache do GitHub Actions e contaminaria as proximas execucoes."""
    if not caminho.exists() or caminho.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(caminho) as z:
            return z.testzip() is None
    except zipfile.BadZipFile:
        return False


def cabecalho(titulo: str, extras: dict | None = None) -> None:
    """Log de cabecalho de estagio (paths, periodo de referencia, etc.)."""
    print("=" * 60)
    print(f"PIPELINE RS MASTER 2026 — {titulo}")
    print(f"Raw: {RAW}  |  Out: {OUT}")
    if extras:
        for chave, valor in extras.items():
            print(f"{chave}: {valor}")
    print("=" * 60)
