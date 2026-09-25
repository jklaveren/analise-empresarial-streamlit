# KIT LOG 24h — colar em qualquer projeto (3 passos)

## Passo 1 — copiar 2 arquivos para o repo destino

```
kit-log-24h/backup_sessao.py → <repo>/scripts/backup_sessao.py
kit-log-24h/instalar_log.sh  → <repo>/scripts/instalar_log.sh   (opcional)
```

## Passo 2 — colar no `.gitignore` do repo destino

```
# Logs/sessoes efemeros — retencao 24h, nunca versionados
logs/sessoes/
logs/acoes.log
!logs/README.md
!logs/.gitkeep
```

## Passo 3 — primeiro registro

```bash
mkdir -p logs/sessoes && touch logs/.gitkeep
python scripts/backup_sessao.py --acao "log 24h ativado" --detalhe "kit instalado"
```

## Regras (valem em todos os repos)

1. **Tudo que for feito** (código + resumo de cada conversa) vira backup em
   `logs/sessoes/YYYYMMDD_HHMMSS_<slug>.md` + 1 linha em `logs/acoes.log`.
2. **Retenção 24h:** passou de 24h, apaga sozinho na próxima chamada.
3. **Comandos:**
   - `--acao "..." --detalhe "..."` → registra
   - `--listar` → mostra vigentes · `--limpar` → purga expirados
   - **`--exit` (`/.exit`) → apaga TUDO e encerra a sessão**
4. **Despedida:** "vou dormir / vou sair / boa noite" → fechar sessão com
   resumo + atualizar o diário permanente do repo (se houver).
5. **Proibido nos logs:** tokens, salts, `.env`, dados LGPD identificáveis.
