# Esboço: camada de IA sobre o WhoDados

Dois protótipos de código, pensados pra encaixar na estrutura real do
`whodados/` (a que aparece no `REPORT.md` do projeto: `backend/app/...`,
`frontend/src/...`). Nenhum arquivo aqui sobrescreve nada seu — são
arquivos novos, prontos para copiar para dentro do repositório e ajustar
os imports conforme o nome exato dos seus módulos existentes
(`auth/dependencies.py`, `data/loader.py` etc. — os nomes usados aqui são
os que aparecem no seu `REPORT.md`; confira se batem exatamente).

## Opção 1 — Lead scoring (`backend/app/ml/`)

| Arquivo | Onde entra |
|---|---|
| `backend/app/ml/train_lead_score.py` | Script batch, roda manualmente ou como step novo no `whodados/.github/workflows/etl.yml`, depois do `sync_data_to_db.py` |
| `backend/app/ml/lead_scoring_service.py` | Carrega o modelo treinado (`joblib`), com cache em memória |
| `backend/app/api/scoring.py` | Router novo — inclua em `backend/main.py` junto dos outros: `app.include_router(scoring_router, prefix="/api/v1")` |
| `frontend/src/components/ScoreBadge.tsx` | Badge no card do kanban do dashboard |

**O rótulo vem do seu próprio CRM** (`status = convertido` vira exemplo
positivo, `status = perdido` vira negativo). Isso resolve o problema de
"não tenho dataset" — mas também significa que nos primeiros meses você
vai ter poucos exemplos. O script já avisa quando isso acontece
(`n_positivos < 30`) e o endpoint devolve `score: null` em vez de quebrar
quando ainda não existe modelo treinado — é o "cold start" tratado como
estado normal, não como erro.

**Para a certificação AWS MLA-C02**: esse mesmo script, hoje salvando em
`joblib` local, é o material perfeito pra depois portar para
SageMaker (Model Registry + endpoint gerenciado) como exercício da
trilha de certificação — dois artefatos de portfólio a partir do mesmo
código.

## Opção 2 — Consulta em linguagem natural (`backend/app/nlp/`)

| Arquivo | Onde entra |
|---|---|
| `backend/app/nlp/schemas.py` | Schema Pydantic do filtro (fonte única de verdade) |
| `backend/app/nlp/nl_query_service.py` | Chama a API da Anthropic com **tool use forçado** — o modelo só pode preencher o schema, nunca escrever SQL livre |
| `backend/app/api/nl_query.py` | Router novo, reaproveita `filtrar_empresas()` que o pipeline já usa |
| `frontend/src/components/BuscaNatural.tsx` | Campo de busca no topo do `/dashboard` |

**Decisão de arquitetura que vale mencionar em entrevista**: o LLM nunca
gera SQL — ele preenche um objeto estruturado (`FiltroEmpresas`) validado
por Pydantic, e o backend é quem monta a query de fato. Isso elimina a
classe inteira de risco de prompt injection → SQL injection, e reaproveita
a mesma função de filtro que o resto do sistema já usa (uma fonte de
verdade, não duas implementações de "filtrar empresas" divergindo com o
tempo).

## Variáveis de ambiente novas

```
ANTHROPIC_API_KEY=sk-ant-...
```

Adicionar em `whodados/backend/.env.example` junto das que já existem
(`RF_SHARE_TOKEN`, `SMTP_*` etc.).

## Dependências novas

Ver `requirements-ia.txt` — adicionar essas 3 linhas ao
`whodados/backend/requirements.txt` existente.

## O que falta pra ficar "pronto para produção" (mesmo padrão do seu REPORT.md)

- Testes (`backend/tests/test_scoring.py`, `test_nl_query.py`), seguindo o
  padrão dos testes que já existem no projeto.
- Rate limit específico pra `/consulta-natural` já está no esboço
  (10/min, mais baixo que o padrão de 60/min) porque cada chamada custa
  uma requisição à API da Anthropic — vale monitorar custo.
- Cache das perguntas mais repetidas do chat, se o uso crescer.
- Job de retrain do modelo de scoring rodando junto do ETL mensal
  (hoje é `python backend/app/ml/train_lead_score.py`, manual).
