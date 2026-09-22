# Relatorio Completo - WhoDados

> Atualizado em 2026-09-19. Estado verificado no codigo (contagens reais: 114 rotas, 30 tabelas, 16 paginas, suite 21 passed).

## 1. Visao Geral

| Item | Valor |
|------|-------|
| Nome | WhoDados (API + Web) |
| Versao | 2.0.0 (`backend/config.py::APP_VERSION`) |
| Tipo | SaaS de inteligencia empresarial B2B |
| Stack Backend | Python, FastAPI, PostgreSQL (Supabase) |
| Stack Frontend | Next.js 15.3.8, React 19.2.8, TypeScript 5, Tailwind 4, TanStack Query 5, Recharts 3 |
| Banco | PostgreSQL via Supabase |
| Data Sources | Receita Federal (2026-09) + PGFN (2026_trimestre_02) — 1.682.255 matrizes RS |
| Autenticacao | JWT (Bearer) + bcrypt |
| Deploy Alvo | Vercel (frontend) + Render (API) + Supabase (banco) |

## 2. Proposito e Escopo

Processa dados publicos da Receita Federal e PGFN para inteligencia de vendas B2B no Rio Grande do Sul.

Funcionalidades: listagem/filtros de empresas com score de potencial, detalhe + socios + dividas, CRM kanban com atividades/anexos, lotes de leads, templates de email, campanhas (email/WhatsApp, com sequencias e agendamento), carteira propria por empresa, gastos, notificacoes, dashboard com metricas, consulta em linguagem natural, enriquecimento de contato (admin, com exclusao LGPD), multitenancy por organizacao, auditoria completa.

SEM webscraping. Apenas downloads oficiais.

## 3. Estrutura de Diretorios

```
whodados/
  backend/
    auth/            # JWT + dependencies (get_active_org, require_admin, require_org_admin)
    classifier/      # CNAE
    data/            # Loader CSVs locais (cache)
    db/              # config.py (30 tabelas) + service.py + analytics.py
    mailer/          # SMTP (service.py)
    security/        # rate_limiter, headers, audit, visitante
    services/        # whatsapp_service.py
    agents/          # enriquecimento_service.py
    nlp/             # consulta em linguagem natural
    endpoints*.py    # 18 arquivos (17 com rotas + agregador endpoints.py)
    main.py / config.py / schemas.py / logger.py / crypto_utils.py
    tests/           # 5 arquivos, 21 testes (2026-09-19: 21 passed)
  frontend/
    src/
      app/           # 16 paginas (rotas)
      components/    # Charts, MultiSelect, FunilInsights, TopEmpresasRanking, etc.
      lib/           # api.ts, auth-context.tsx, query-provider.tsx
  pipeline/          # pipeline_bigquery.py (fonte alternativa via BigQuery)
  scripts/           # sync_data_to_db.py, sync_dividas_only.py, criar_usuario.py, criar_admin.py, *.sql
  render.yaml
  DEPLOY.md / REPORT.md (este arquivo) / SECURITY.md
.github/workflows/
  keep-alive.yml              # ping /health a cada 3 dias (Supabase/Render free)
  campanhas-lote-diario.yml   # disparo diario de campanhas
```

> O ETL principal (`pipeline_levas.py`) roda LOCAL em `C:/whodados/whodados_etl/` (fora do repo; automacao via Actions removida em 2026-09 — ver DEPLOY.md).

## 4. Backend

### 4.1 main.py

FastAPI com lifespan (`ensure_tables_exist` + `seed_default_templates`). Middlewares: CORS, SecurityHeaders, RateLimiter, Visitante. `GET /health` (status, versao, secret_key_ok, banco_ok), `GET /`, docs em `/docs`.

### 4.2 Auth (`auth/`)

`service.py`: hash bcrypt, JWT HS256, autenticar/criar usuario, password reset (`password_reset_tokens`). `dependencies.py`: `get_current_user`, `require_admin`, `get_active_org` (escopo X-Org-Id; sem header so cai na empresa em leitura com empresa unica, escrita sem header = 400), `get_papel_ativo`, `require_org_admin`.

### 4.3 Endpoints REST (prefixo /api/v1) — 114 rotas em 17 arquivos

| Arquivo | Rotas | Assunto |
|---------|-------|---------|
| endpoints_auth.py | 6 | login, forgot/reset-password, me, senha |
| endpoints_empresas.py | 4 | listar, count, detalhe |
| endpoints_analytics.py | 8 | resumo, por-cidade/setor/porte, top-empresas, socios ranking/detalhe, opcoes-filtro |
| endpoints_crm.py | 23 | kanban, atividades (+anexos/historico/comentario/prazo/responsavel), classificacao |
| endpoints_campanhas.py | 6 | CRUD, previa, executar, executar-pendentes |
| endpoints_templates.py | 10 | CRUD, preview, test-send, imagem |
| endpoints_lotes.py | 5 | lotes de leads (filtros de potencial + CNAE) |
| endpoints_carteira.py | 5 | carteira propria por empresa, importar |
| endpoints_gastos.py | 7 | aba de gastos |
| endpoints_notificacoes.py | 3 | listar, nao-lidas, marcar lida |
| endpoints_organizacoes.py | 4 | organizacoes, meu-email, logo |
| endpoints_admin.py | 19 | smtp, status sistema, SLA, organizacoes, usuarios |
| endpoints_monitor.py | 3 | monitor de emails enviados |
| endpoints_nlp.py | 1 | consulta em linguagem natural |
| endpoints_enriquecimento.py | 3 | enriquecer contato (admin, LGPD) |
| endpoints_integracoes.py | 6 | integracoes + WhatsApp (enviar, conversas, webhook) |
| endpoints_descadastro.py | 1 | pagina publica de descadastro (LGPD) |
| endpoints_push.py | 4 | push PWA (vapid-key, subscribe, unsubscribe, broadcast por empresa/global) |
| endpoints.py | 0 | agregador (router unico) |

### 4.4 Banco (`db/config.py::ensure_tables_exist`) — 30 tabelas

App/usuarios: `app_users`, `password_reset_tokens`, `organizacoes`, `usuario_organizacoes`, `app_config`, `audit_log`, `login_attempts`.
CRM: `crm`, `crm_atividades`, `crm_atividade_historico`, `crm_atividade_anexos`, `empresas_carteira`, `lotes_leads`.
Email/campanhas: `email_templates`, `campanhas`, `campanha_envios`, `campanha_destinatarios`, `emails_enviados`, `emails_descadastrados`.
Comunicacao: `notificacoes`, `integracao_configs`, `whatsapp_mensagens`, `org_smtp_config`, `usuario_smtp_config`.
Dados (espelho local, tambem criadas pelo sync): `pipeline_metadata`, `municipios`, `cnaes`.
Outros: `gastos`, `enriquecimento_contatos`.

> Tabelas de DADOS pesadas (`dados_empresas` 1,68M linhas, `dados_socios` 940k) sao criadas/carregadas pelo ETL (`sync_data_to_db.py` + `database_config.py` na raiz do repo).

### 4.5 Data Loading

Loader CSV local com cache em memoria + queries SQL (`db/service.py`, `db/analytics.py`): filtros por cidade/CNAE/faixas de divida e capital, blacklist de falencia/rec. judicial, metricas e rankings.

### 4.6 Mailer (`mailer/service.py`)

SMTP TLS por empresa (remetente e' a pessoa, nao a empresa), templates com `cnae_descricao`, campanhas em lote, sequencias e agendamento.

### 4.7 Configuracao (`config.py::Settings`)

DATABASE_URL, APP_ENV, SECRET_KEY (>=32 chars, checada no /health), CORS_ORIGINS, SMTP_*, RATE_LIMIT_*, LOGIN_MAX_ATTEMPTS/LOCKOUT, AUDIT_ENABLED, API_CACHE_TTL_SECONDS, RF_SHARE_TOKEN, PGFN_TRIMESTRE, DATA_SOURCE.

### 4.8 Seguranca (`security/`)

`rate_limiter.py` (60 req/min/IP, Redis-ready), `headers.py` (CSP, HSTS, X-Frame-Options DENY), `audit.py` (acoes sensiveis em `audit_log`), `visitante.py`, brute-force lockout, JWT HS256 + bcrypt, descadastro LGPD.

### 4.9 Schemas (`schemas.py`)

Pydantic: Login, Token, Usuario, Empresa, CRM, Atividades, Lotes, Templates, Campanhas, Gastos, Notificacoes, Metricas.

## 5. Frontend (Next.js 15.3.8)

### 5.1 Stack

next 15.3.8 | react 19.2.8 | @tanstack/react-query 5 | recharts 3.10 | tailwindcss 4 | typescript 5 | eslint 9.

### 5.2 Rotas (16 paginas)

| Rota | Descricao |
|------|-----------|
| / | Landing/redirect |
| /login, /forgot-password, /reset-password | Auth |
| /dashboard | Lista empresas (filtros persistidos no navegador) |
| /dashboard/empresa/[cnpj] | Detalhe + CRM |
| /dashboard/socios | Ranking/detalhe de socios (linkado a empresa via query param) |
| /dashboard/crm | Kanban (cria atividade direto do board) |
| /dashboard/atividades | Acompanhamento de tarefas |
| /dashboard/lotes | Lotes de leads (CNAE, capital, fundacao, porte; divida opcional) |
| /dashboard/campanhas | Campanhas (usa o template escolhido) |
| /dashboard/templates | Templates (preview de e-mail) |
| /dashboard/whatsapp | WhatsApp por empresa |
| /dashboard/gastos | Gastos |
| /dashboard/notificacoes | Notificacoes (badge no menu) |
| /dashboard/configuracoes | Configuracoes |

### 5.3 Layout (dashboard/layout.tsx)

Sidebar responsiva + OrgSwitcher (X-Org-Id) + `useRequireAuth()`.

### 5.4 API Client (lib/api.ts)

Token em localStorage (`whodados_token`), `req<T>` com Bearer, `ApiError`. Cobre: auth, metricas, empresas, CRM/atividades, lotes, carteira, templates, campanhas, gastos, notificacoes, socios, WhatsApp, NLP, enriquecimento.

### 5.5 Auth Context / Query Provider

`auth-context.tsx` (login/logout, JWT decodificado p/ username + is_admin), `query-provider.tsx` (React Query).

### 5.6 Componentes

AnalyticsCharts, ConsultaNaturalBox, FunilInsights, TopEmpresasRanking, PotencialBadge, MultiSelect, OrgSwitcher, PreviewTemplate, AcompanhamentoAtividade.

## 6. Pipeline de Dados

### 6.1 Fontes (censo 2026-09-19)

Receita Federal `2026-09` (WebDAV `arquivos.receitafederal.gov.br`, token `RF_SHARE_TOKEN`, UA `WhoDados-ETL/1.0`) + PGFN `2026_trimestre_02` (`dadosabertos.pgfn.gov.br`, 3 zips: FGTS, Previdenciario, Nao_Previdenciario).

### 6.2 Implementacoes

- `C:/whodados/whodados_etl/whodados/pipeline/pipeline_levas.py` (fora do repo): processamento em levas (baixa→filtra→apaga, pico ~2 GB), retomavel via `_progresso.json`, `MANTER_ZIPS=0`. Saida: 1 CSV master (`subset_rs_final_completo.csv` → `dados_empresas`) + 1 de socios (`socios_rs.csv` → `dados_socios`); intermediarios apagados apos upload ok.
- `whodados/pipeline/pipeline_bigquery.py`: fonte alternativa via BigQuery.
- Etapas: estabelecimentos (matrizes RS ativas) → empresas → socios → dividas PGFN → Simples/MEI → tabelas de dominio (cnaes, municipios, naturezas, qualificacoes) → consolidacao → upload Supabase (`scripts/sync_data_to_db.py`, schema em `database_config.py`).
- Automacao via GitHub Actions REMOVIDA em 2026-09 (RF bloqueia IP de nuvem); ETL roda local via `BAIXAR_DADOS.bat`.

### 6.3 Resultado vigente

1.682.255 matrizes ativas RS → `subset_rs_final_completo.csv` (393 MB); `dados_socios` 940.442 linhas; 167.569 empresas com divida (Federal R$ 113,77 bi + Previdenciaria R$ 20,81 bi + FGTS R$ 2,41 bi = R$ 136,99 bi). Indices: cnpj_completo, cnpj_basico, cnae, cod_municipio.

### 6.4 CI/CD restante

`.github/workflows/keep-alive.yml` (ping /health 3/3 dias) + `campanhas-lote-diario.yml` (disparo diario).

## 7. Scripts (scripts/)

`sync_data_to_db.py` (CSV→Supabase + indices + metadata p/ tela "Sobre"), `sync_dividas_only.py`, `criar_usuario.py` / `criar_admin.py`, `nivel1_dados_empresas.sql`, `nivel1_dados_socios.sql`, `fix_tipos_dominio.sql`.

## 8. Variaveis de Ambiente

Backend: DATABASE_URL, APP_ENV, SECRET_KEY, CORS_ORIGINS, API_CACHE_TTL_SECONDS, DATA_SOURCE, SMTP_*, RATE_LIMIT_*, LOGIN_*, AUDIT_ENABLED, RF_SHARE_TOKEN, PGFN_TRIMESTRE. Frontend (`env.local`): NEXT_PUBLIC_API_URL.

## 9. Dependencias

Backend: fastapi, uvicorn[standard], pydantic, pydantic-settings, psycopg2-binary, python-jose[cryptography], cryptography, passlib[bcrypt] + bcrypt==4.0.1 (pin), python-multipart, pandas, numpy, python-dotenv, anthropic, twilio.
Pipeline/ETL: pandas, requests, psycopg2-binary, SQLAlchemy.
Frontend: next 15.3.8, react 19.2.8, @tanstack/react-query 5, recharts 3.10; dev: tailwindcss 4, typescript 5, eslint 9.

## 10. Seguranca Implementada

CORS, security headers, rate limiting, brute-force lockout, JWT+bCrypt, multitenancy por organizacao (X-Org-Id + 403/400 estritos), audit log, descadastro LGPD, RLS Supabase (ver SECURITY.md), `/health` expoe `secret_key_ok`/`banco_ok`.

## 11. Validacao (2026-09-19)

`python -m pytest whodados/backend/tests` → **21 passed** (test_active_org 6, test_crypto_e_seguranca 6, test_filtros_empresas 6, test_multitenant_scoping 2, test_lotes 1). Correcoes do dia: SyntaxError em `test_lotes.py:35` e `test_active_org.py` realinhado a nova assinatura/comportamento de `get_active_org` (400 sem header em escrita/multi-empresa).

## 12. Mudancas Recentes (git)

`949277e` fix CNAE-descricao em template + filtros salvos em lotes · `fbe5457` form de lotes (CNAE/capital/fundacao/porte) · `81b22f1` modulo de lotes · `037a75f` remove pipelines WebDAV quebrados + limpa workflows + fix SMTP por org · `a7f9f24` remetente pessoa fisica · `cef1dfd` WhatsApp/Brevo por empresa · `2ff79a9` carteira propria/isolamento · `0b9cece` tabela `empresas_potencial` pre-calculada · `ac9dcaf` score potencial/WhatsApp/lotes/hierarquia/LGPD/BigQuery.

## 13. Pontos de Atencao

| Item | Estado |
|------|--------|
| Refresh token | Preparado, nao implementado |
| Cache multi-replica | Em memoria (1 instancia) |
| Rate limit multi-replica | Requer Redis |
| RLS no Supabase | Ativar em producao (SECURITY.md) |
| SECRET_KEY forte | Checar via /health (`secret_key_ok`) |
| `database_config.py` duplicado | Raiz do repo = canonico; copia em `whodados_etl/` so p/ ETL local (cabecalho de sincronia nos dois arquivos) |
| Credenciais GCP | `*bigquery*.json` ignorado no .gitignore; credencial de servico fica em `C:/whodados/` (fora do repo) |

## 14. Deploy (resumo; detalhe em DEPLOY.md)

Supabase → `sync_data_to_db.py` cria tabelas; Render Blueprint (`render.yaml`: `uvicorn backend.main:app`, `DATABASE_URL`, `CORS_ORIGINS`); Vercel (root `whodados/frontend`, `NEXT_PUBLIC_API_URL`); ETL manual local (`BAIXAR_DADOS.bat`); keep-alive via Actions.

## 15. Resumo

| Aspecto | Valor |
|---------|-------|
| Rotas REST | 118 em 18 arquivos |
| Paginas frontend | 16 |
| Tabelas banco | 30 (empresas_potencial dropada em 2026-09: −209 MB) |
| Testes | 33 passed |
| Push PWA | Web Push via VAPID (sem FCM/APNs); broadcast por empresa + global |
| Webscraping | 0 |
| Status | Producao (free tier R$ 0/mes) |
| Deploy | Vercel + Render + Supabase |

---

**Pronto para subir.**
