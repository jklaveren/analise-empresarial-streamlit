# MANUAL DA IA INSTALADORA — kit log 24h (leia e execute nesta ordem)

> Você é a IA instalando este kit no repositório atual.
> Execute os passos, faça o commit no git e reporte no final.

## Passo 0 — inspecionar (antes de tocar em nada)

1. `git status --short` e `git log --oneline -3` — entenda o estado.
2. Liste a raiz: confirme onde estão `scripts/`, `docs/`, `.gitignore`.
3. `python --version` — precisa de Python 3.10+ (só stdlib é usada).

## Passo 1 — copiar os arquivos do kit

```
kit-log-24h/backup_sessao.py → <repo>/scripts/backup_sessao.py
kit-log-24h/logs-README.md   → <repo>/logs/README.md
```

## Passo 2 — gitignore (sem duplicar)

Se o bloco abaixo ainda NÃO existir em `.gitignore`, acrescente ao final:

```
# Logs/sessoes efemeros — retencao 24h, nunca versionados
logs/sessoes/
logs/acoes.log
!logs/README.md
!logs/.gitkeep
```

## Passo 3 — ativar e verificar

```bash
mkdir -p logs/sessoes && touch logs/.gitkeep
python scripts/backup_sessao.py --acao "log 24h ativado" --detalhe "kit instalado pela IA"
python scripts/backup_sessao.py --listar   # deve mostrar 1 entrada
python scripts/backup_sessao.py --limpar   # deve responder 0 removidos
```

## Passo 4 — registrar no git (obrigatório)

```bash
git add scripts/backup_sessao.py logs/README.md logs/.gitkeep .gitignore
git status --short    # confira: só esses arquivos, NADA de logs/sessoes/ nem acoes.log
git commit -m "chore: instala kit log 24h (backup efemero + regra /.exit)"
```

NUNCA commite `logs/sessoes/` nem `logs/acoes.log`. Se aparecerem no status,
o gitignore está errado — corrija antes de commitar. NÃO dê push sem permissão.

## Passo 5 — reporte final (responda ao usuário)

- onde instalou (paths), resultado dos 3 comandos de verificação,
- hash do commit, e as regras que passam a valer (abaixo).

## Regras que passam a valer neste repo (cumpra daqui pra frente)

1. Toda ação + resumo de cada conversa → `logs/sessoes/*.md` + `logs/acoes.log`.
2. Retenção 24h com purga automática. `/.exit` (ou `--exit`) = apaga tudo e encerra.
3. Despedida ("vou dormir/sair/boa noite") = log final + diário permanente + confirmação.
4. Proibido nos logs: tokens, salts, `.env`, dados LGPD identificáveis.
