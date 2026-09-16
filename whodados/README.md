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
├── pipeline/                     # Pipeline ETL (fracionado em estágios)
│   ├── pipeline.py               # subcomandos: download-rf/pgfn, process-rf/pgfn, merge, detect, all
│   ├── raw/                      # zips baixados (.gitignored)
│   ├── out/                      # CSVs gerados (.gitignored)
│   └── requirements-dev.txt
│
├── scripts/
│   ├── sync_data_to_db.py        # CSVs → Supabase (empresas, socios, municipios, cnaes)
│   └── criar_usuario.py          # CLI: cria usuário admin
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

### Automático (GitHub Actions) — desativado

Existiam workflows (`whodados-etl.yml`, `whodados-etl-levas.yml`, `whodados-dividas.yml`) que rodavam o ETL automaticamente. Foram **removidos em 2026-09** porque as execuções no runner do GitHub Actions passaram a falhar sempre (travando em menos de 1 minuto, mesmo código que funciona local) — indício de bloqueio/anti-abuso da Receita Federal contra IPs de datacenter/nuvem. `teste-conectividade-rf.yml` continua no repo como diagnóstico (só testa alcance, não baixa dados).

Enquanto isso não é resolvido (self-hosted runner, proxy, ou outra fonte para os dados), rode o ETL **do seu computador**: `python whodados/pipeline/pipeline_levas.py` com `DATABASE_URL` no ambiente (veja `nra_etl/rodar_pipeline.cmd` para o fluxo usado hoje).

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
