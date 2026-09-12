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
import subprocess
import sys
import zipfile
from dataclasses import dataclass
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


# ----------------------------------------------------------------
# AUTO-DIAGNOSTICO DE URL / DOWNLOAD
# ----------------------------------------------------------------
@dataclass
class DiagUrl:
    """Resultado de uma sondagem HTTP: o suficiente pra saber se vale a
    pena tentar baixar, e pra imprimir uma msg de erro humana."""
    ok: bool
    codigo: str      # HTTP code como string (ex: "200", "401", "000")
    motivo: str      # slug estavel: ok|token|proibido|inexistente|servidor|rede|desconhecido
    detalhe: str     # frase humana explicando + o que fazer

_MAPEAMENTO_CODIGO = {
    "200": ("ok", "arquivo existe (servidor respondeu OK)"),
    "206": ("ok", "arquivo existe (servidor honrou o range: Partial Content)"),
    "401": ("token", "credencial invalida ou expirada. Renove o secret RF_SHARE_TOKEN em Settings > Secrets and variables > Actions."),
    "403": ("proibido", "acesso proibido. Pode ser bloqueio de IP (runner do GitHub bloqueado), politica nova, ou token sem permissao."),
    "404": ("inexistente", "URL nao existe no servidor. Confirme se o mes RF / trimestre PGFN configurado esta correto."),
    "429": ("servidor", "servidor esta rate-limitando o runner. Espere alguns minutos e tente de novo."),
    "500": ("servidor", "servidor com erro interno. Tente de novo mais tarde."),
    "502": ("servidor", "bad gateway. Tente de novo mais tarde."),
    "503": ("servidor", "servico indisponivel (fora do ar ou manutencao). Tente de novo mais tarde."),
    "504": ("servidor", "gateway timeout. Servidor lento; tente de novo mais tarde."),
}


def diagnosticar_url(url: str, auth: str | None = None, timeout: int = 15) -> DiagUrl:
    """Sonda uma URL com GET-de-1-byte e devolve diagnostico estruturado.

    Nao levanta excecao: retorna um DiagUrl com ok=False e motivo/detalhe
    que dizem o que fazer. Usado por (a) deteccao de mes/trimestre, (b)
    preflight antes de baixar em massa (falhar rapido em vez de queimar
    horas contra um servidor que ja rejeitou o primeiro pedido)."""
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L",
           "--range", "0-0", "--max-time", str(timeout)]
    if auth:
        cmd += ["-u", auth]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        codigo = (r.stdout or "").strip() or "000"
    except FileNotFoundError:
        return DiagUrl(False, "000", "rede", "curl nao esta instalado no ambiente.")
    except Exception as e:
        return DiagUrl(False, "erro", "rede", f"Excecao ao sondar: {e}")

    motivo, detalhe = _MAPEAMENTO_CODIGO.get(codigo, (None, None))
    if motivo == "ok":
        return DiagUrl(True, codigo, "ok", detalhe or "OK")
    if motivo:
        return DiagUrl(False, codigo, motivo, detalhe)
    if codigo == "000":
        return DiagUrl(False, codigo, "rede",
                       "sem resposta do servidor (timeout, DNS ou conexao caiu). "
                       "Verifique se o site esta no ar; runner do GitHub pode estar sem rota.")
    if codigo.startswith("4"):
        return DiagUrl(False, codigo, "desconhecido", f"erro do cliente HTTP {codigo}.")
    if codigo.startswith("5"):
        return DiagUrl(False, codigo, "servidor", f"erro do servidor HTTP {codigo}.")
    return DiagUrl(False, codigo, "desconhecido", f"codigo HTTP inesperado {codigo}.")


def imprimir_diagnostico(nome: str, url: str, diag: DiagUrl) -> None:
    """Formata o resultado de diagnosticar_url em log legivel."""
    marcador = "OK " if diag.ok else "!! "
    print(f"  {marcador}{nome}: HTTP {diag.codigo} ({diag.motivo}) -- {diag.detalhe}", file=sys.stderr)
    if not diag.ok:
        print(f"       URL: {url}", file=sys.stderr)


def abortar_com_diagnostico(estagio: str, url: str, diag: DiagUrl) -> None:
    """Encerra o estagio de forma limpa com mensagem estruturada. Usado
    pelo preflight dos estagios de download: em vez de queimar 40 min
    com curl -C - retry contra um servidor que ja disse 'nao', para
    aqui e diz por que."""
    linhas = [
        f"[FALHA] Estagio {estagio}: preflight nao passou.",
        f"        URL testada: {url}",
        f"        HTTP: {diag.codigo}  |  Motivo: {diag.motivo}",
        f"        Detalhe: {diag.detalhe}",
    ]
    raise SystemExit("\n".join(linhas))
