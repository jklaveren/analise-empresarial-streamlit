# Por onde continuar

**Estado em 2026-09-30.** Este arquivo é **sobrescrito** a cada sessão — ele
responde *"o que eu faço agora"*, não *"o que aconteceu"*. O histórico fica em
[`DIARIO.md`](DIARIO.md); o mapa e as regras, em [`../CLAUDE.md`](../CLAUDE.md).

Quem encerrar uma sessão reescreve este arquivo antes de sair.

---

## Estado atual

`main` = `247b9b7`. Suíte **41/41 verde**, `tsc --noEmit` limpo, `next build`
compila as 19 rotas. Nada pendente na árvore de trabalho.

**A Carteira está fechada de ponta a ponta.** Trocar a fonte em Configurações →
Empresas agora funciona e sobrevive ao deploy, e a tela `/dashboard/carteira`
(visível só para empresa de carteira) carrega a planilha.

**Cuidado antes de tocar em Configurações:** a SYVP ainda **não tem remetente
cadastrado**. Depois do fix `0dff4f3` chegar em produção, a tela dela vai
passar a dizer "não configurado" e parar de enviar — isso é o comportamento
correto, não uma regressão nova.

## Próximo passo

**Arrancar o Brevo.** É a frente 2 da ordem combinada, e é limpeza que
desbloqueia a frente 3 (Gmail por usuário) — as duas mexem na mesma tela de
Configurações.

Resíduo em ~9 lugares:
- `endpoints_webhooks.py` inteiro (o webhook já está inerte: 403 sem
  `BREVO_WEBHOOK_SECRET`)
- `BREVO_WEBHOOK_SECRET` em `config.py`
- `brevo_api_key` em `endpoints_integracoes.py` (`chaves_permitidas`)
- uma seção inteira de UI em `configuracoes/page.tsx` ("Brevo (E-mail)", com
  link de criar conta e campo de API key) e o rótulo da aba
  "Integrações (Brevo/Twilio)"
- comentários em `db/service.py`, `mailer/service.py`, `db/config.py`

⚠️ **Decidir antes de arrancar:** some a **detecção de bounce assíncrono**. Os
eventos `hard_bounce`/`soft_bounce`/`blocked`/`spam` só chegavam pelo webhook, e
pixel não enxerga bounce. O Gmail API pega a rejeição no momento do envio, mas
não a devolução que chega minutos depois. Numa operação de prospecção, e-mail
morto que se continua disparando é o que queima domínio.

Também corrigir: `EMAIL_LIMITE_DIARIO = 300` em `config.py` tem o comentário
"Brevo free = 300/dia". Com Gmail API o teto real é outro (500/dia conta comum,
2.000 Workspace) — pode estar limitando à toa.

## Fila, na ordem combinada

3. **Gmail OAuth por usuário.** Hoje é uma conta global (`GMAIL_OAUTH_*` em env,
   gerada rodando `scripts/autorizar_gmail.py` na mão) e só o cabeçalho `From`
   muda — o Gmail recusa ou marca como spam quando se envia como endereço que a
   conta autenticada não possui.
4. **Cobertura de log nos endpoints.** `security/audit.py` funciona e
   `AuditAction` prevê 22 ações; existem **4 chamadas** no backend inteiro (3 de
   login, 1 de "viu empresa"). Campanha, lote, CRM e carteira não deixam rastro.
   ❓ **Decidir primeiro:** auditoria (quem fez o quê, em tabela, para LGPD) ou
   log operacional (rastro em arquivo, para depurar)? São desenhos diferentes.

## Dívida conhecida na Carteira

A tela subiu, mas dois defeitos do backend seguem, e valem antes do primeiro
cliente com lista grande:

- **Importação síncrona, linha a linha.** 5.000 linhas = 5.000 chamadas de
  `salvar_na_carteira` dentro de um request. No Render é candidato a timeout, e
  sem transação o que estourar no meio deixa a carteira pela metade. Ou processa
  em lote, ou baixa o limite para um número que fecha com folga.
- **`POST /carteira` recebe `data: Dict` cru**, sem Pydantic — o único endpoint
  do módulo sem validação, e é o caminho "adicionar na mão". A tela hoje não usa
  esse endpoint (só o importador), então não é urgente, mas vira urgente no dia
  em que alguém adicionar o formulário de cadastro manual.

## Auditoria das telas — incompleta

Lidas: `notificacoes`, `envios`, `lotes`, e as partes críticas de
`configuracoes` e `dashboard/page.tsx`. **Faltam:** `campanhas`, `crm`,
`templates`, `socios`, `whatsapp`, `gastos`, `atividades` e `empresa/[cnpj]`.

Padrão que vale procurar nelas, porque apareceu em todas as lidas: **erro se
disfarçando de estado normal** — `catch` silencioso que vira lista vazia,
default exibido como se fosse valor salvo, zero real exibido como "sem dado".

## Testar de verdade ainda está bloqueado

Não há ambiente de teste: `.env.local` aponta para produção e o login exige
credencial. Para exercitar tela de verdade, a dona do projeto abre a sessão no
navegador e a IA dirige a partir dali — sem tocar em botão de disparo.
