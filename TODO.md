# TODO — WhoDados

Estado em 2026-09-28. Marcar `[x]` ao concluir.

## Bloqueando o primeiro disparo

- [ ] **Brevo: desativar restrição de IP** (Settings → SMTP & API → Autorização de IP).
      Envio falha com `525 5.7.1 Unauthorized IP address`. Render free não tem
      IP fixo, então desativar é melhor que listar. — *Jessica*
- [ ] Confirmar **rastreamento de cliques** ativo no Brevo. Sem ele o evento
      `click` nunca dispara. — *Jessica*

## Segurança (vazaram no chat em 2026-09-28)

- [ ] Trocar senha do Postgres/Supabase e atualizar `DATABASE_URL` no Render.
- [ ] Trocar `BREVO_WEBHOOK_SECRET` (Render + URL no Brevo).

## Campanhas — buracos conhecidos

- [ ] **Supressão global de já-contatado.** Hoje `campanha_envios` só evita
      repetir dentro da *mesma* campanha. Campanha nova reenvia para quem já
      recebeu.
- [ ] **Criar lote a partir do Monitor** (recebeu mas não abriu / não clicou),
      para reenvio depois de N dias. Dados existem; falta o caminho.
- [ ] **Pausar/retomar campanha.** Hoje só existe apagar.
- [ ] Lotes agrupados por setor automaticamente (hoje é um lote por vez).
- [ ] Data prevista de conclusão da campanha (com 300/dia, quando termina).

## Inconsistência a decidir

- [ ] `incluir_inativas` tem default oposto: `endpoints_empresas.py:75` e
      `endpoints_lotes.py:38` usam `True` (incluem falência/RJ),
      `endpoints_analytics.py:36` usa `False`. O contador e a tabela discordam
      dos gráficos, e **o lote inclui falência/RJ**, o oposto do pedido.
      Decidir e uniformizar.

## Base

- [ ] Mover exclusão de CNAE 69 para o pipeline no próximo ETL (hoje é filtro
      de query em `CNAE_DIVISOES_EXCLUIDAS`).
- [ ] Decidir MEI: `CORTAR_MEI=0` no próximo ETL traz os MEIs de volta.
      Motivo de querer: em MEI o contato é o próprio empreendedor.
- [ ] Reinserir empresa de teste após cada ETL (`scripts/inserir_empresa_teste.py`)
      — `sync_data_to_db.py` usa `to_sql(if_exists="replace")` e apaga a linha.

## Infra

- [ ] Sair do plano free do Render (cold start de 30-60s; também derruba a
      confiabilidade do cron diário).
- [ ] `CAMPANHAS_CRON_SECRET` (GitHub) precisa ter o mesmo valor de
      `CRON_SECRET` (Render). Conferir.

## Fora deste repo

- [ ] `C:\DataBricks`: merge pendente (2 commits locais x 2 remotos).
- [ ] Clonar os 10 repos pessoais que faltam em `C:\projetos`.
- [ ] `C:\whodados\whodados_etl` sem backup nenhum — criar repo (privado) e
      `.gitignore` barrando `dados/` antes do primeiro commit.
- [ ] Twilio caro — avaliar alternativa para WhatsApp.
- [ ] Validar número de WhatsApp (hoje `validar_whatsapp` só confere formato).

## Docs restantes

- [ ] Revisar `whodados/REPORT.md` (13,7 KB, não revisado).
- [ ] Decidir sobre `kit-log-24h/` (3 docs, parecem scratch).
- [ ] Root `README.md` / `DEPLOY.md` descrevem o Streamlit legado, que o
      `.gitignore:82` exclui do versionamento.

---

## Feito em 2026-09-28

- [x] Gate de filtro obrigatório no dashboard (7 queries sobre 1,68M → 0 na abertura)
- [x] Botão "Criar lote deste filtro" (manda o filtro inteiro, não os 6 campos)
- [x] Fila com teto de 300/dia na conta inteira (`EMAIL_LIMITE_DIARIO`)
- [x] Webhook Brevo: entrega, abertura, clique, bounce + `Message-ID` no envio
- [x] Saudação legível a partir da razão social (28,3% da base não tem sócio)
- [x] `buscar_socios_principais`: só pessoa física
- [x] Exclusão de CNAE 69 (jurídico + contábil), nos dois construtores de WHERE
- [x] Conferência automática do lote antes do disparo (regras, sem custo de LLM)
- [x] Índices trigram: busca por nome saiu de timeout para ~5s
- [x] Docs com erro factual corrigidos (`IMPLEMENTAR_MANUALMENTE`, `SECURITY`,
      `README`, `DEPLOY`); `TAREFA_ENXERTO.md` removido
- [x] Empresa de teste inserida na base (CNPJ 50552952000196)
