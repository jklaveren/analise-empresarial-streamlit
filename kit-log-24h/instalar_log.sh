#!/usr/bin/env bash
# Instala o kit de log 24h (docs/REGRAS_DE_LOG.md) em qualquer outro repo.
# Uso: bash scripts/instalar_log.sh /caminho/do/outro-repo
set -euo pipefail

DEST="${1:?Uso: instalar_log.sh /caminho/do/repo-destino}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$DEST/scripts" "$DEST/logs/sessoes" "$DEST/docs"
cp "$SRC/scripts/backup_sessao.py" "$DEST/scripts/backup_sessao.py"
cp "$SRC/docs/REGRAS_DE_LOG.md" "$DEST/docs/REGRAS_DE_LOG.md"
touch "$DEST/logs/.gitkeep"

if ! grep -q "Logs/sessoes efemeros" "$DEST/.gitignore" 2>/dev/null; then
  cat >> "$DEST/.gitignore" <<'EOF'

# Logs/sessoes efemeros — retencao 24h, nunca versionados (ver docs/REGRAS_DE_LOG.md)
logs/sessoes/
logs/acoes.log
!logs/README.md
!logs/.gitkeep
EOF
fi

echo "Kit de log 24h instalado em $DEST"
echo "Teste: python $DEST/scripts/backup_sessao.py --listar"
