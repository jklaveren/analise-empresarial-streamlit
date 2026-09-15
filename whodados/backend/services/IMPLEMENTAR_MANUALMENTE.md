# PENDÊNCIAS — Integrações (para implantar manualmente ou com outra IA)

## 1. Twilio WhatsApp — limitação externa (não é código)
O envio real depende de credenciais válidas e do modo da conta Twilio:

- **Sandbox (grátis, para teste):**
  1. Criar conta em https://www.twilio.com/whatsapp
  2. Console → Messaging → Try it out → Send a WhatsApp message
  3. **Todo número de destino precisa se registrar no sandbox** enviando
     `join <código-do-sandbox>` por WhatsApp para o número do sandbox.
     Sem isso, o envio falha (erro 63016/63003).
- **Produção:** precisa de número WhatsApp Business aprovado pela Meta
  (via Twilio ou 360Dialog). Número fixo do sandbox `whatsapp:+14155238886`
  NÃO funciona para clientes reais em volume.

- Variáveis esperadas (Render → Environment):
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_WHATSAPP_NUMBER` (ex.: `whatsapp:+5511...`)

## 2. Tabela `integracao_configs` (painel de credenciais no app)
SQL para rodar no Supabase (SQL Editor) caso a criação automática na
inicialização do backend não tenha acontecido:

```sql
CREATE TABLE IF NOT EXISTS integracao_configs (
    id SERIAL PRIMARY KEY,
    chave VARCHAR(100) UNIQUE NOT NULL,
    valor TEXT,
    descricao VARCHAR(255),
    ativo BOOLEAN DEFAULT FALSE,
    atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

Chaves usadas: `brevo_api_key`, `twilio_account_sid`, `twilio_auth_token`,
`twilio_whatsapp_number`.

## 3. Brevo (e-mail)
Já configurado anteriormente (`BREVO_API_KEY` no Render). Nada pendente de código.
