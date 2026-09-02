# WhoDados — Cloud Stack (`whodados/`)

Stack completo de produção: **Next.js** (Vercel) + **FastAPI** (Render) + **Supabase** (Postgres) + **GitHub Actions** (ETL mensal).

> 📖 Este é o stack **novo (WhoDados)**. Para o app Streamlit legacy (raiz do repo), consulte o `README.md` principal.

---

## 🏗️ Arquitetura

```
Navegador
    │
    ▼
Vercel (Next.js 15) ──────► Render (FastAPI) ──────► Supabase (Postgres)
  /dashboard                   /empresas               dados_empresas
  /login                       /crm                   dados_socios
                                /auth                  app_users
                                                        crm
    │
    ▼
GitHub Actions (ETL mensal)
  1. python whodados/pipeline/pipeline.py
  2. python whodados/scripts/sync_data_to_db.py
```

---

## 📁 Estrutura

```
whodados/
├── backend/                      # FastAPI (deploy no Render)
│   ├── main.py                   # entry point (uvicorn backend.main:app)
│   ├── endpoints.py              # /empresas, /empresas/{cnpj}, /crm
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                     # Next.js 15 (deploy na Vercel)
│   ├── src/app/                  # app/page, login/page, dashboard/*
│   ├── src/components/           # MultiSelect, AnalyticsCharts
│   ├── src/lib/                  # api.ts (cliente HTTP), auth-context.tsx
│   ├── package.json
│   ├── next.config.ts
│   └── .env.example
│
├── pipeline/                     # Pipeline ETL
│   ├── pipeline.py               # baixa RF + PGFN, gera CSVs
│   ├── raw/                      # zips baixados (.gitignored)
│   ├── out/                      # CSVs gerados (.gitignored)
│   └── requirements-dev.txt
│
├── scripts/
│   ├── sync_data_to_db.py        # CSVs → Supabase
│   └── criar_usuario.py          # CLI: cria usuário admin
│
├── .github/workflows/
│   └── etl.yml                   # cron mensal + workflow_dispatch
│
├── render.yaml                   # Render Blueprint
├── requirements.txt              # deps da API
└── DEPLOY.md                     # guia passo-a-passo
```

> O frontend tem seu próprio `vercel.json` em `whodados/frontend/`.

---

## 🚀 Desenvolvimento Local

### 1. Setup do ambiente Python

```bash
# Raiz do projeto (whodados/)
pip install -r whodados/pipeline/requirements-dev.txt   # ETL
pip install -r whodados/backend/requirements.txt        # API
```

### 2. Setup do ambiente Node

```bash
cd whodados/frontend
npm install
```

### 3. Variáveis de ambiente

```bash
# API
cp whodados/backend/.env.example whodados/backend/.env
# Edite DATABASE_URL e SECRET_KEY

# Web
cp whodados/frontend/.env.example whodados/frontend/.env.local
# Edite NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4. Rodar API

```bash
# Raiz do projeto
uvicorn backend.main:app --reload --port 8000
# OU (da raiz do repo): uvicorn whodados.backend.main:app --reload --port 8000
# Docs: http://localhost:8000/docs
```

### 5. Rodar Web

```bash
cd whodados/frontend
npm run dev
# App: http://localhost:3000
```

### 6. Criar primeiro usuário

```bash
python whodados/scripts/criar_usuario.py admin --admin
```

---

## 📥 Pipeline ETL (dados)

### Rodar localmente

```bash
python whodados/pipeline/pipeline.py
```

Os arquivos baixados vão para `whodados/pipeline/raw/` e os CSVs gerados para `whodados/pipeline/out/`.

### Sincronizar para o Supabase

```bash
DATABASE_URL="postgresql://..." python whodados/scripts/sync_data_to_db.py
```

### Automático (GitHub Actions)

O workflow `whodados/.github/workflows/etl.yml` roda todo dia **1 do mês às 02h UTC** (cron `0 2 1 * *`). Configure `SUPABASE_CONNECTION_STRING` como variável do repositório no GitHub.

---

## 🔐 Autenticação

O sistema usa **JWT Bearer token**. Não existe cadastro público — o dono cria usuários com:

```bash
python whodados/scripts/criar_usuario.py meuusuario --admin
```

---

## 📋 Pré-requisitos

- Python 3.11+
- Node.js 20+
- curl e wget (para o pipeline)
- Conta no Supabase (PostgreSQL)
- Conta no Render.com
- Conta na Vercel

---

## 💰 Custo

Zero no plano gratuito de todos os serviços para uso pessoal leve.
