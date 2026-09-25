"""Backup/log de sessoes com retencao de 24h.

Regra (valida "daqui pra frente"):
- Toda acao/conversa relevante no repo gera um arquivo em logs/sessoes/
  + uma linha no indice central logs/acoes.log (JSONL).
- Tudo com mais de 24h e automaticamente eliminado na proxima chamada
  (e via --limpar / agendador).

Uso:
    python scripts/backup_sessao.py --acao "descricao curta" --detalhe "texto livre..." --autor opencode
    python scripts/backup_sessao.py --listar
    python scripts/backup_sessao.py --limpar
    python scripts/backup_sessao.py --limpar --retencao-horas 24
    python scripts/backup_sessao.py --exit   # /.exit: apaga TUDO e encerra
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs" / "sessoes"
INDICE_PATH = REPO_ROOT / "logs" / "acoes.log"
RETENCAO_PADRAO_HORAS = 24


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _slug(texto: str, limite: int = 50) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", texto.strip().lower()).strip("-")
    return (base[:limite] or "sessao").strip("-")


def registrar(acao: str, detalhe: str = "", autor: str = "opencode") -> Path:
    """Registra uma acao e ja purga expirados. Retorna o path do arquivo criado."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    INDICE_PATH.parent.mkdir(parents=True, exist_ok=True)

    agora = _agora()
    stamp = agora.strftime("%Y%m%d_%H%M%S")
    caminho = LOG_DIR / f"{stamp}_{_slug(acao)}.md"
    # Evita colisao no mesmo segundo
    i = 1
    while caminho.exists():
        caminho = LOG_DIR / f"{stamp}_{_slug(acao)}_{i}.md"
        i += 1

    conteudo = (
        f"# {acao}\n\n"
        f"- **quando (UTC):** {agora.isoformat()}\n"
        f"- **autor:** {autor}\n"
        f"- **repo:** {REPO_ROOT.name}\n\n"
        f"## Detalhe\n\n{detalhe or '(sem detalhe)'}\n"
    )
    caminho.write_text(conteudo, encoding="utf-8")

    try:
        arquivo_rel = caminho.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        arquivo_rel = caminho.name
    registro = {
        "ts": agora.isoformat(),
        "acao": acao,
        "autor": autor,
        "arquivo": arquivo_rel,
        "detalhe": (detalhe or "")[:2000],
    }
    with INDICE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    limpar_expirados(RETENCAO_PADRAO_HORAS)
    return caminho


def _parse_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def limpar_expirados(retencao_horas: int = RETENCAO_PADRAO_HORAS) -> dict:
    """Remove arquivos do indice + .md mais antigos que a retencao. Retorna estatistica."""
    corte = _agora() - timedelta(hours=retencao_horas)
    removidos, mantidos, erros = 0, 0, 0

    registros_validos: list[str] = []
    if INDICE_PATH.exists():
        for linha in INDICE_PATH.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            try:
                reg = json.loads(linha)
                dt = _parse_ts(reg.get("ts", ""))
                rel = (reg.get("arquivo", "") or "").lstrip("/")
                candidatos = [REPO_ROOT / rel, LOG_DIR / Path(rel).name]
            except (json.JSONDecodeError, TypeError, AttributeError):
                erros += 1
                continue
            if dt is None or dt < corte:
                # Expirado: apaga o .md correspondente
                apagou = False
                for arq in candidatos:
                    try:
                        # So apaga dentro do LOG_DIR (protecao contra path traversal)
                        dentro = LOG_DIR == arq.resolve().parent or LOG_DIR in arq.resolve().parents
                    except OSError:
                        continue
                    try:
                        if dentro and arq.exists():
                            arq.unlink()
                            apagou = True
                    except OSError:
                        erros += 1
                removidos += 1
            else:
                registros_validos.append(linha)
                mantidos += 1
        INDICE_PATH.write_text(
            ("\n".join(registros_validos) + "\n") if registros_validos else "",
            encoding="utf-8",
        )

    # Varredura de orfaos: .md sem entrada no indice (ou com mtime antigo)
    if LOG_DIR.exists():
        for md in LOG_DIR.glob("*.md"):
            if md.name.upper() == "README.md":
                continue
            mtime = datetime.fromtimestamp(md.stat().st_mtime, tz=timezone.utc)
            if mtime < corte:
                try:
                    md.unlink()
                    removidos += 1
                except OSError:
                    erros += 1

    return {"removidos": removidos, "mantidos": mantidos, "erros": erros}


def limpar_tudo() -> dict:
    """/.exit: apaga TODOS os backups de sessao + zera o indice. Irreversivel."""
    removidos, erros = 0, 0
    if LOG_DIR.exists():
        for md in LOG_DIR.glob("*.md"):
            if md.name.upper() == "README.md":
                continue
            try:
                md.unlink()
                removidos += 1
            except OSError:
                erros += 1
    try:
        if INDICE_PATH.exists():
            INDICE_PATH.write_text("", encoding="utf-8")
    except OSError:
        erros += 1
    return {"removidos": removidos, "erros": erros}


def listar() -> list[dict]:
    if not INDICE_PATH.exists():
        return []
    out = []
    for linha in INDICE_PATH.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            try:
                out.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Log/backup de sessoes com retencao de 24h.")
    parser.add_argument("--acao", help="Descricao curta da acao/conversa")
    parser.add_argument("--detalhe", default="", help="Texto livre do que foi feito")
    parser.add_argument("--autor", default="opencode")
    parser.add_argument("--listar", action="store_true", help="Lista entradas vigentes (<24h)")
    parser.add_argument("--limpar", action="store_true", help="Apenas purga expirados (>24h) e sai")
    parser.add_argument("--exit", action="store_true", help="/.exit: apaga TUDO (todos os backups + indice) e sai")
    parser.add_argument("--retencao-horas", type=int, default=RETENCAO_PADRAO_HORAS)
    args = parser.parse_args()

    if args.exit:
        stats = limpar_tudo()
        print(f"/.exit: {stats['removidos']} backups apagados, indice zerado, {stats['erros']} erros. Sessao encerrada.")
        return

    if args.limpar:
        stats = limpar_expirados(args.retencao_horas)
        print(f"Limpeza 24h: {stats['removidos']} removidos, {stats['mantidos']} mantidos, {stats['erros']} erros.")
        return

    if args.listar:
        for reg in listar():
            print(f"{reg.get('ts')} | {reg.get('autor')} | {reg.get('acao')} | {reg.get('arquivo')}")
        return

    if not args.acao:
        parser.error("--acao e obrigatorio (ou use --listar / --limpar)")
    caminho = registrar(args.acao, args.detalhe, args.autor)
    print(f"Registrado: {caminho.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    sys.exit(main())
