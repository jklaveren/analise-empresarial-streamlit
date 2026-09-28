# PENDÊNCIAS — Integrações

## 1. Twilio WhatsApp — limitação externa (não é código)

O envio real depende de credenciais válidas e do modo da conta Twilio:

- **Sandbox (grátis, para teste):**
  1. Criar conta em https://www.twilio.com/whatsapp
  2. Console → Messaging → Try it out → Send a WhatsApp message
  3. **Todo número de destino precisa se registrar no sandbox** enviando
     `join <código-do-sandbox>` por WhatsApp para o número do sandbox.
     Sem isso, o envio falha (erro 63016/63003).
- **Produção:** precisa de número WhatsApp Business aprovado pela Meta
  (via Twilio ou 360Dialog). O número fixo do sandbox `whatsapp:+14155238886`
  NÃO funciona para clientes reais em volume.

### Onde ficam as credenciais

Por empresa, na tabela `integracao_configs` (coluna `organizacao_id`), editável
pelo painel do app em **Configurações → Integrações**. As variáveis de ambiente
abaixo são apenas o último recurso, quando não há linha no banco:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_NUMBER`

### Validação de número

`validar_whatsapp()` em `services/whatsapp_service.py` só confere formato
(`+55` e comprimento). **Não verifica se o número existe nem se tem WhatsApp.**
Para isso seria preciso a Twilio Lookup v2, que é cobrada por consulta.

## 2. Tabela `integracao_configs`

O backend cria a tabela sozinho no boot (`db/config.py::ensure_tables_exist`).
Só rode o SQL abaixo se a criação automática tiver falhado:

```sql
CREATE TABLE IF NOT EXISTS integracao_configs (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL,
    value TEXT,
    descricao VARCHAR(255),
    ativo BOOLEAN DEFAULT FALSE,
    organizacao_id INTEGER REFERENCES organizacoes(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

As colunas são `key`/`value` — é assim que `whatsapp_service.py` consulta.
`key` não é UNIQUE sozinha: a mesma chave existe uma vez por empresa, e uma
linha com `organizacao_id NULL` vale como padrão global.

Chaves usadas pelo código (`_ENV` em `whatsapp_service.py`):
`twilio_sid`, `twilio_token`, `twilio_wa_number`, `brevo_api_key`.

## 3. Brevo (e-mail)

Envio por SMTP relay, configurado por empresa em **Configurações → Integrações**
ou via `SMTP_*` no ambiente. Nada pendente de código.

### Webhook de eventos

`POST /api/v1/webhooks/brevo?token=<BREVO_WEBHOOK_SECRET>` recebe entrega,
abertura, clique e bounce, e preenche `emails_enviados`. Exige:

1. `BREVO_WEBHOOK_SECRET` no Render;
2. o webhook cadastrado no Brevo (Transacional, webhook de saída) com os
   eventos `delivered`, `opened`, `click`, `hard_bounce`, `soft_bounce`,
   `blocked`, `spam`;
3. **rastreamento de cliques ativado** no Brevo — sem isso ele não reescreve
   os links e o evento `click` nunca dispara.

Sem o secret configurado o endpoint responde 403 e fica desligado.
