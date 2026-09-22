# 🚀 Guia de Deploy — WhoDados

Este guia mostra como colocar o app inteiro na nuvem. Todo o código deste stack está em `whodados/`.

O resultado final é:
- **Frontend** rodando na Vercel (`whodados/frontend/`)
- **API** rodando na Render (`whodados/backend/`)
- **Banco** rodando no Supabase
- **Dados** atualizados manualmente rodando o pipeline local (`whodados_etl/` ou `whodados/pipeline/pipeline_levas.py`) — a automação via GitHub Actions foi removida em 2026-09 porque parava de funcionar (provável bloqueio/anti-abuso da Receita Federal para downloads vindos de IP de nuvem); rodando do seu computador funciona normalmente

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

## 2️⃣ Variáveis e segredos

O ETL é manual/local (a automação via GitHub Actions foi removida em 2026-09 — falhava sempre, provável bloqueio da RF pra IP de nuvem). Não há secrets de ETL no GitHub. Tudo que o deploy precisa:

- **Render (API):** `DATABASE_URL` (connection string do Supabase), `SECRET_KEY` (forte, ≥32 chars — confira em `/health`), `CORS_ORIGINS`, `APP_ENV=production`.
- **Vercel (frontend):** `NEXT_PUBLIC_API_URL` (URL da API no Render).
- **Local (ETL):** `DATABASE_URL` no ambiente + `RF_SHARE_TOKEN` (padrão público: `gn672Ad4CF8N6TK`) ao rodar `BAIXAR_DADOS.bat`.

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

## 5️⃣ Alimentar o banco (ETL — manual, no seu computador)

A automação via GitHub Actions foi removida em 2026-09 (a Receita Federal bloqueia downloads vindos de IP de nuvem; do seu computador funciona normalmente).

1. Defina `DATABASE_URL` no ambiente (connection string do Supabase).
2. Rode `C:\whodados\whodados_etl\BAIXAR_DADOS.bat` (ou `rodar_pipeline.cmd`) — baixa RF + PGFN em levas, consolida em `dados\out\` e sobe para o Supabase.
3. Para reprocessar do zero, apague `dados\out\_progresso.json` antes de rodar.

Última carga vigente: RF `2026-09` + PGFN `2026_trimestre_02` — 1.682.255 matrizes RS.

---

## 5b️⃣ Avisos push no celular (PWA — sem loja, sem FCM/APNs)

O app já é instalável (manifest + ícones em `frontend/public/`) e o backend já envia Web Push via VAPID. Falta só gerar as chaves e configurar 3 envs:

1. Gere um par VAPID novo (uma vez só):
```bash
cd whodados
python -c "from backend.push import gerar_vapid; print(gerar_vapid())"
```
2. No **Render (API)**, adicione as envs:
   - `VAPID_PUBLIC_KEY` = `public` gerado
   - `VAPID_PRIVATE_KEY` = `private` gerado (nunca commite, nunca exponha)
   - `VAPID_SUBJECT` = `mailto:seu-email@empresa.com`
3. Redeploy a API (a tabela `push_subscriptions` é criada sozinha no boot).
4. No app: **Notificações → Ativar** neste aparelho. Admin vê também o composer **📣 Avisar** (própria empresa; geral pode marcar "todas as empresas").

Notas:
- iOS exige o app **instalado na tela de início** (Safari → Compartilhar → Adicionar à Tela de Início, iOS 16.4+) e um toque em Ativar.
- Cada aparelho recebe só os avisos da **empresa ativa no momento da ativação** (inscrição vinculada ao X-Org-Id).
- Sem VAPID configurado, o broadcast cai com 503 no subscribe e o aviso vai só pro sino interno — nada quebra.

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
| Dados não aparecem | Verifique se o ETL local rodou sem erros (`dados\download.log` / `upload_supabase.log`) |
| App não conecta API | Confirme `NEXT_PUBLIC_API_URL` na Vercel |
| Render não encontra `backend.main` | `start_command` deve ter `backend.main:app` |

---

## 💰 Custos (free tier)

| Serviço | Grátis | Estimado |
|---------|--------|----------|
| Vercel | 100 GB/mês | ~1-5 GB |
| Render | 750h/mês | ~720h |
| Supabase | 500 MB | ~500 MB (dados_empresas 1,68M + socios 940k) |
| GitHub Actions | 2.000 min/mês | ~negligível (só keep-alive + campanhas) |

**Total: R$ 0/mês** para uso leve.