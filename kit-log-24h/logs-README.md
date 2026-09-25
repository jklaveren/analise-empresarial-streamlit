# Logs e backups de sessão — retenção de 24h

Tudo que for feito neste repo é registrado como backup por **24h**,
depois **eliminado automaticamente** e substituído por registros novos.

- Detalhe por ação: `logs/sessoes/YYYYMMDD_HHMMSS_<slug>.md`
- Índice central (JSONL): `logs/acoes.log`
- Ambos são **gitignored** (só este README é versionado).
- Comandos: `python scripts/backup_sessao.py --acao "..." --detalhe "..."`
  `--listar` · `--limpar` · `--exit` (apaga tudo e encerra).
- Não grave segredos (tokens, salts, `.env`) nem dados LGPD nos logs.
