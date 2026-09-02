# 🚀 Guia de Deploy — WhoDados

Este guia mostra como colocar o app inteiro na nuvem. Todo o código deste stack está em `whodados/`.

O resultado final é:
- **Frontend** rodando na Vercel (`whodados/frontend/`)
- **API** rodando na Render (`whodados/backend/`)
- **Banco** rodando no Supabase
- **Dados** atualizados automaticamente via GitHub Actions (`whodados/.github/workflows/etl.yml`)

---

## 1️⃣ Provisionar o Supabase (PostgreSQL)

1. Acesse [supabase.com](https://supabase.com) e crie uma conta (grátis)
2. Clique em **"New Project"**
3. Preencha:
   - **Name**: `whodados` (ou o nome que preferir)
   - **Database Password**: uma senha forte (anote ela!)
   - **Region**: `South America (São Paulo)` (mais rápido para o Brasil)
4. Aguarde ~2 minutos enquanto o projeto é provisionado
5. Vá em **Settings → Database** e copie a **Connection String** (URI)

### Tabelas necessárias
As tabelas serão criadas automaticamente na primeira execução do ETL via:
```bash
DATABASE_URL="<sua-connection-string>" python whodados/scripts/sync_data_to_db.py
```

---

## 2️⃣ Configurar Secrets no GitHub

1. Settings → Secrets and variables → Actions → **New repository secret**:
   - `RF_SHARE_TOKEN` = seu token da Receita Federal (público: `gn672Ad4CF8N6TK`)
2. Settings → Secrets and variables → Actions → **Variables**:
   - `SUPABASE_CONNECTION_STRING` = connection string do Supabase

> 💡 O workflow do ETL está em `whodados/.github/workflows/etl.yml`.

---

## 3️⃣ Deploy da API no Render.com

1. Acesse [render.com](https://render.com) → conecte GitHub
2. **"New" → "Blueprint"** → selecione o repositório
3. O Render detecta `whodados/render.yaml` automaticamente
   - Se manual: Root Directory = `whodados`, Build = `pip install -r requirements.txt`, Start = `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Configure env: `DATABASE_URL`, `CORS_ORIGINS=https://whodados.vercel.app`
5. Aguarde ~3-5 min → anote a URL (ex: `https://whodados-api.onrender.com`)

**Teste:** `https://whodados-api.onrender.com/docs`

---

## 4️⃣ Deploy do Frontend na Vercel

1. Acesse [vercel.com](https://vercel.com) → conecte GitHub
2. **"Add New" → "Project"** → selecione o repositório
3. Configure:
   - **Root Directory**: `whodados/frontend` ← IMPORTANTE!
   - **Framework Preset**: Next.js
4. Environment Variables: `NEXT_PUBLIC_API_URL` = URL do Render (passo 3)
5. Aguarde ~2-3 min → app no ar! 🎉

---

## 5️⃣ Alimentar o banco (ETL)

**Manual:** GitHub → Actions → "Atualizar Dados (Pipeline ETL) — WhoDados" → Run workflow

**Agendamento:** todo **dia 1 do mês às 02h UTC** (cron `0 2 1 * *`)

---

## 🔧 Opcional

| O que | Como |
|-------|------|
| Custom Domain | Vercel: Project Settings → Domains / Render: Service Settings |
| Mais cache | Render: `API_CACHE_TTL_SECONDS=3600` |
| Monitorar | Render dashboard / Vercel Analytics / Supabase dashboard |

---

## ❓ Troubleshooting

| Problema | Solução |
|----------|---------|
| API retorna 401 | Token expirado — faça login novamente |
| Dados não aparecem | Verifique se ETL rodou sem erros (Actions) |
| App não conecta API | Confirme `NEXT_PUBLIC_API_URL` na Vercel |
| Render não encontra `backend.main` | `start_command` deve ter `backend.main:app` |

---

## 💰 Custos (free tier)

| Serviço | Grátis | Estimado |
|---------|--------|----------|
| Vercel | 100 GB/mês | ~1-5 GB |
| Render | 750h/mês | ~720h |
| Supabase | 500 MB | ~50-100 MB |
| GitHub Actions | 2.000 min/mês | ~60 min |

**Total: R$ 0/mês** para uso leve.