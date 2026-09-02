# 🚀 Guia de Deploy — WhoDados em Cloud

> 📦 **Consulte o guia atualizado em [`whodados/DEPLOY.md`](./whodados/DEPLOY.md).**
> Todo o stack foi reorganizado: `whodados/backend/`, `whodados/frontend/`, `whodados/pipeline/`, `whodados/scripts/`.

Este guia mostra como colocar o app inteiro na nuvem. O resultado final é:
- **Frontend** rodando na Vercel
- **API** rodando na Render
- **Banco** rodando no Supabase
- **Dados** atualizados automaticamente via GitHub Actions

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
   - Formato: `postgresql://postgres:[SENHA]@db.xxx.supabase.co:5432/postgres`
6. (Opcional) Vá em **Settings → API** e copie:
   - **Project URL**: `https://xxx.supabase.co`
   - **anon public key**: necessário para integração direta do frontend
   - **service_role key**: ⚠️ NÃO use no frontend (acesso total)

### Tabelas necessárias
As tabelas serão criadas automaticamente na primeira execução via:
```bash
DATABASE_URL="<sua-connection-string>" python scripts/sync_data_to_db.py
```

---

## 2️⃣ Configurar Secrets no GitHub

1. Acesse o repositório no GitHub
2. Vá em **Settings → Secrets and variables → Actions**
3. Clique em **"New repository secret"** e adicione:
   - **Name**: `RF_SHARE_TOKEN`
   - **Value**: seu token da Receita Federal (público: `gn672Ad4CF8N6TK` funciona)

4. Vá em **Settings → Secrets and variables → Variables** (não Secrets!)
5. Clique em **"New repository variable"** e adicione:
   - **Name**: `SUPABASE_CONNECTION_STRING`
   - **Value**: a connection string do Supabase (passo 1.5)

---

## 3️⃣ Deploy da API no Render.com

1. Acesse [render.com](https://render.com) e crie uma conta (grátis)
2. Conecte sua conta do GitHub
3. Clique em **"New" → "Blueprint"** (Infrastructure as Code)
4. Selecione o repositório `analise-empresarial-streamlit`
5. O Render vai detectar o `render.yaml` automaticamente
6. Configure as variáveis de ambiente:
   - `DATABASE_URL`: a connection string do Supabase
   - `CORS_ORIGINS`: a URL do seu app Vercel (ex: `https://whodados.vercel.app`)
7. Clique em **"Apply"** e aguarde o deploy (~3-5 min)
8. Anote a URL gerada (ex: `https://whodados-api.onrender.com`)

### Teste a API
Acesse `https://whodados-api.onrender.com/docs` — você deve ver a documentação Swagger.

---

## 4️⃣ Deploy do Frontend na Vercel

1. Acesse [vercel.com](https://vercel.com) e crie uma conta (grátis)
2. Conecte sua conta do GitHub
3. Clique em **"Add New" → "Project"**
4. Selecione o repositório `analise-empresarial-streamlit`
5. Configure:
   - **Root Directory**: `web` ← IMPORTANTE!
   - **Framework Preset**: Next.js (detectado automaticamente)
6. Em **Environment Variables**, adicione:
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: a URL da API no Render (passo 3.8)
7. Clique em **"Deploy"** e aguarde (~2-3 min)
8. Acesse a URL gerada — seu app está no ar! 🎉

---

## 5️⃣ Ativar o ETL Automático

1. Vá no GitHub → aba **Actions**
2. Clique em **"Atualizar Dados (Pipeline ETL)"**
3. Clique em **"Run workflow" → "Run workflow"**
4. Acompanhe a execução (~10-20 min na primeira vez, mais rápido nas seguintes)
5. Quando terminar, os dados estarão no Supabase e visíveis no app

### Agendamento automático
O workflow já está agendado para rodar todo **dia 1 do mês às 02h UTC** (cron `0 2 1 * *`). Os dados serão atualizados mensalmente sem você precisar fazer nada.

---

## 🔧 Configuração Adicional (Opcional)

### Custom Domain
- **Vercel**: Project Settings → Domains → Add Domain
- **Render**: Service Settings → Custom Domain

### Aumentar Cache da API
A API tem cache de 300s (5 min) por padrão. Para ajustar:
- No painel do Render, altere `API_CACHE_TTL_SECONDS` (ex: `3600` = 1 hora)

### Monitoramento
- **Render**: Dashboard mostra CPU, memória, requisições
- **Vercel**: aba "Analytics" mostra performance
- **Supabase**: Dashboard mostra queries, espaço usado

---

## ❓ Troubleshooting

| Problema | Solução |
|----------|---------|
| API retorna 401 | Token JWT expirado — faça login novamente |
| Dados não aparecem | Verifique se o ETL rodou sem erros (aba Actions) |
| App não conecta com API | Confirme `NEXT_PUBLIC_API_URL` na Vercel |
| Banco vazio | Rode o workflow do ETL manualmente (passo 5) |

---

## 💰 Custos Esperados (free tier)

| Serviço | Limite Grátis | Uso Estimado |
|---------|---------------|--------------|
| Vercel | 100 GB bandwidth/mês | ~1-5 GB |
| Render | 750h/mês (1 serviço) | ~720h (24/7) |
| Supabase | 500 MB banco, 2 GB bandwidth | ~50-100 MB |
| GitHub Actions | 2.000 min/mês | ~60 min/mês |

**Total: R$ 0/mês** para uso pessoal/profissional leve.
