# 🛡️ WhoDados

Sistema de análise e prospecção empresarial com dados públicos (Receita Federal + PGFN).

> 📦 **Todo o stack da aplicação está em [`whodados/`](./whodados/)** — Next.js + FastAPI + Supabase.

---

## 📌 Visão Geral

O WhoDados é uma plataforma de inteligência empresarial que permite:
- Analisar empresas do Rio Grande do Sul e outros dados cadastrais
- Investigar sócios e grupos econômicos
- Visualizar dívidas ativas (FGTS, Previdenciário, Não Previdenciário)
- Gerenciar leads e CRM
- Acessar de qualquer lugar, na nuvem

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  VERCEL (Next.js) - Frontend (`whodados/frontend/`)          │
│  ✅ Login, Dashboard, Detalhe, Gráficos (Recharts)          │
└──────────────────────┬──────────────────────────────────────┘
                       │  API REST
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  RENDER (FastAPI) - Backend (`whodados/backend/`)           │
│  ✅ JWT Auth, Endpoints de dados + CRM                      │
└──────────────────────┬──────────────────────────────────────┘
                       │  SQLAlchemy
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  SUPABASE (PostgreSQL) - Banco de dados                     │
│  ✅ Empresas, Sócios, Dívidas, CRM, Usuários                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Estrutura do Projeto (`whodados/`)

```
whodados/
├── backend/                      # FastAPI (deploy no Render)
│   ├── main.py                   # Entry point
│   ├── endpoints.py              # Endpoints da API (/empresas, /crm, etc.)
│   └── requirements.txt          # Dependências da API
├── frontend/                     # Next.js (deploy na Vercel)
│   ├── src/app/                  # Páginas (Dashboard, Login, etc.)
│   ├── src/components/           # Componentes UI
│   └── package.json              # Dependências do frontend
├── pipeline/                     # Pipeline ETL de dados
│   ├── pipeline.py               # Script principal / subcomandos ETL
│   ├── raw/                      # Zips baixados (.gitignored)
│   └── out/                      # CSVs gerados (.gitignored)
├── scripts/                      # Scripts utilitários e sync para DB
│   └── sync_data_to_db.py        # Sincroniza CSVs para o Supabase
├── render.yaml                   # Configuração do Render
└── DEPLOY.md                     # Guia de deploy detalhado
```

---

## 🚀 Guia Rápido de Deploy

Consulte o guia completo em [`whodados/DEPLOY.md`](./whodados/DEPLOY.md).

1. **Supabase**: Provisionar banco PostgreSQL e copiar connection string.
2. **Render (API)**: Conectar repositório, usar `whodados/render.yaml` (Root Directory: `whodados`), configurar `DATABASE_URL`.
3. **Vercel (Frontend)**: Conectar repositório, Root Directory: `whodados/frontend`, configurar `NEXT_PUBLIC_API_URL`.

---

## 💻 Desenvolvimento Local

### 1. Backend (FastAPI)
```bash
pip install -r whodados/backend/requirements.txt
uvicorn whodados.backend.main:app --reload --port 8000
```
Docs: `http://localhost:8000/docs`

### 2. Frontend (Next.js)
```bash
cd whodados/frontend
npm install
npm run dev
```
App: `http://localhost:3000`

### 3. Criar Usuário Admin
```bash
python whodados/scripts/criar_usuario.py admin --admin
```

---

## 📞 Contato

**Jessica Van Klaveren**
- GitHub: [@jehzi](https://github.com/jehzi)
