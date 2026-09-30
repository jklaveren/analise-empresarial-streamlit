#!/usr/bin/env bash
# Bloqueia `git commit` enquanto a suite do backend nao estiver verde.
#
# Existe porque a regra "sempre testar antes de commitar" so' vale se algo a
# impuser: lembrar dela falha exatamente no dia corrido. Roda a suite e, se
# algum teste quebrar, nega o commit devolvendo o motivo.
#
# Usa o Python do venv do projeto de proposito: o Python do sistema nesta
# maquina esta sob politica de Controle de Aplicativo e nao carrega psycopg2,
# o que faz a suite "falhar" por motivo errado.
set -uo pipefail

raiz="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
cd "$raiz" 2>/dev/null || exit 0

py="whodados/.venv/Scripts/python.exe"
[ -x "$py" ] || py="$(command -v python3 || command -v python)"
[ -n "$py" ] || exit 0   # sem Python nao da' pra checar; nao trava o trabalho

saida=$("$py" -m pytest whodados/backend/tests -q 2>&1)
codigo=$?
[ $codigo -eq 0 ] && exit 0

printf '%s' "$saida" | "$py" -c '
import json, sys
bruto = sys.stdin.read()
quebrados = [l for l in bruto.splitlines() if l.startswith(("FAILED", "ERROR"))][:10]
placar = next((l for l in reversed(bruto.splitlines()) if "passed" in l or "failed" in l), "")
motivo = ("Commit bloqueado: a suite do backend nao esta verde.\n\n"
          + placar + "\n\n" + "\n".join(quebrados)
          + "\n\nConserte os testes (ou o codigo) antes de commitar.")
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": motivo}}))
'
exit 0
