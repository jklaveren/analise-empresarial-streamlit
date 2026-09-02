# 🛡️ WhoDados

Sistema de análise e prospecção empresarial com dados públicos (Receita Federal + PGFN).

> 📦 **O stack de produção (cloud) está em [`whodados/`](./whodados/)** — Next.js + FastAPI + Supabase + GitHub Actions.
> A raiz do repo contém o protótipo Streamlit legacy (mantido por compatibilidade).

---

## 📌 Visão Geral

O WhoDados é uma plataforma de inteligência empresarial que permite:
- Analisar empresas do Rio Grande do Sul
- Investigar sócios e grupos econômicos
- Visualizar dívidas ativas (FGTS, Previdenciário, Não Previdenciário)
- Gerenciar leads e CRM
- Acessar de qualquer lugar, na nuvem

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  VERCEL (Next.js) - Frontend                                │
│  web/                                                        │
│  ✅ Login, Dashboard, Detalhe, Gráficos (Recharts)          │
└──────────────────────┬──────────────────────────────────────┘
                       │  API REST
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  RENDER (FastAPI) - Backend                                 │
│  api/                                                        │
│  ✅ JWT Auth, Endpoints de dados + CRM                      │
└──────────────────────┬──────────────────────────────────────┘
                       │  SQLAlchemy
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  SUPABASE (PostgreSQL) - Banco de dados                     │
│  ✅ Empresas, Sócios, Dívidas, CRM, Usuários                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  GITHUB ACTIONS - Pipeline ETL automático                    │
│  ✅ Atualiza dados mensalmente (dia 1 do mês)               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Estrutura do Projeto

```
analise-empresarial-streamlit/
├── app_main.py                 # App Streamlit (desenvolvimento local)
├── api/                        # API FastAPI (backend)
├── web/                        # Frontend Next.js (produção)
├── data_extraction/            # Pipeline de extração de dados
│   ├── pipeline.py             # Script ETL (substitui o Colab)
│   ├── raw/                    # Arquivos baixados (não commitado)
│   └── out/                    # CSVs gerados (não commitado)
├── scripts/                    # Scripts utilitários
├── paginas/                    # Páginas do Streamlit
├── requirements.txt            # Dependências principais
├── requirements-dev.txt        # Dependências do pipeline ETL
├── render.yaml                 # Configuração do Render
├── vercel.json                 # Configuração da Vercel
├── DEPLOY.md                   # Guia de deploy completo
└── README.md                   # Este arquivo
```

---

## 🚀 Deploy Rápido

### 1. Provisionar o Supabase (5 min)
1. Acesse [supabase.com](https://supabase.com) → "New Project"
2. Nome: `whodados`, Region: `South America (São Paulo)`
3. Copie a **Connection String** em Settings → Database

### 2. Configurar Secrets no GitHub
- Settings → Secrets and variables → Actions → New secret:
  - `RF_SHARE_TOKEN` = seu token da Receita Federal
- Settings → Secrets and variables → Variables → New variable:
  - `SUPABASE_CONNECTION_STRING` = connection string do Supabase

### 3. Deploy da API no Render (5 min)
1. [render.com](https://render.com) → "New" → "Blueprint"
2. Conecte o GitHub e selecione o repositório
3. O Render detecta `render.yaml` automaticamente
4. Configure `DATABASE_URL` com a connection string do Supabase
5. Deploy → anote a URL gerada

### 4. Deploy do Frontend na Vercel (5 min)
1. [vercel.com](https://vercel.com) → "Import Project"
2. Selecione o repositório
3. **Root Directory**: `web`
4. Environment Variable: `NEXT_PUBLIC_API_URL` = URL da API do Render
5. Deploy

### 5. Ativar ETL Automático
1. GitHub → Actions → "Atualizar Dados (Pipeline ETL)"
2. Clique em "Run workflow"
3. Aguarde ~10-20 min na primeira execução

---

## 📋 Detalhes por Etapa

### Pipeline ETL (substitui o Colab)
```bash
# Rodar manualmente
python data_extraction/pipeline.py

# Via GitHub Actions (automático todo dia 1 do mês)
```

### Banco de Dados
```bash
# Sincronizar CSVs para o Supabase
DATABASE_URL="<sua-connection-string>" python scripts/sync_data_to_db.py
```

### Desenvolvimento Local
```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar app Streamlit
streamlit run app_main.py

# Rodar API localmente
cd api && uvicorn main:app --reload
```

---

## 📊 Dados Esperados

O pipeline baixa e processa:
- **Receita Federal**: Empresas, Estabelecimentos, Sócios, CNAEs, Municípios
- **PGFN**: Dívidas ativas (FGTS, Previdenciário, Não Previdenciário)

Arquivos gerados em `data_extraction/output/`:
- `subset_rs_final_completo.csv` — Empresas com dívidas e contato
- `socios_rs.csv` — Sócios das matrizes RS

---

## 🔧 Configuração

### Variáveis de Ambiente
| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DATABASE_URL` | Connection string do Supabase | `postgresql://...` |
| `DATA_SOURCE` | `files` (CSV) ou `database` | `database` |
| `NEXT_PUBLIC_API_URL` | URL da API FastAPI | `https://whodados-api.onrender.com` |
| `RF_SHARE_TOKEN` | Token da Receita Federal | `gn672Ad4CF8N6TK` |

### Custos
| Serviço | Plano | Custo |
|---------|-------|-------|
| Vercel | Free | R$ 0 |
| Render | Free | R$ 0 |
| Supabase | Free | R$ 0 |
| GitHub Actions | Free | R$ 0 |

---

## ❓ Troubleshooting

| Problema | Solução |
|----------|---------|
| Dados não atualizam | Verifique a aba Actions no GitHub |
| API retorna 401 | Token expirado — refaça login |
| App não conecta com API | Confirme `NEXT_PUBLIC_API_URL` |
| Banco vazio | Execute o workflow ETL manualmente |

---

## 📞 Contato

**Jessica Van Klaveren**
- GitHub: [@jehzi](https://github.com/jehzi)