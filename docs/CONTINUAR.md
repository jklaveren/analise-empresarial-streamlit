# Por onde continuar

**Estado em 2026-09-30.** Este arquivo é **sobrescrito** a cada sessão — ele
responde *"o que eu faço agora"*, não *"o que aconteceu"*. O histórico fica em
[`DIARIO.md`](DIARIO.md); o mapa e as regras, em [`../CLAUDE.md`](../CLAUDE.md).

Quem encerrar uma sessão reescreve este arquivo antes de sair.

---

## Estado atual

`main` = `675ff53`. Suíte **41/41 verde**, `tsc --noEmit` limpo, `next build`
compila as 18 rotas. Nada pendente na árvore de trabalho.

**Cuidado antes de tocar em Configurações:** a SYVP ainda **não tem remetente
cadastrado**. Depois do fix `0dff4f3` chegar em produção, a tela dela vai
passar a dizer "não configurado" e parar de enviar — isso é o comportamento
correto, não uma regressão nova.

## Próximo passo

**1. Fechar a Carteira** — é a única frente que muda o que dá para vender.

Backend pronto e nunca ligado: `endpoints_carteira.py` tem 5 rotas, incluindo
importador de CSV (até 5.000 linhas, aceita variações de cabeçalho e Latin-1 do
Excel BR). O frontend já se adapta a `escopo_base == "carteira"`
(`layout.tsx:37` esconde Sócios). Falta só a tela.

Em ordem, dentro desta frente:

- [ ] **Desarmar `db/config.py:497`** — a linha `UPDATE organizacoes SET
      escopo_base = 'carteira' WHERE slug = 'jehjuh'` roda a cada boot e vai
      **desfazer a escolha do admin**. Tem que virar seed de uma vez só (há
      tabela `app_config` para guardar a marca) ou sair.
- [ ] **UI do seletor** de fonte de prospecção, em Configurações → admin. O
      endpoint já existe: `PUT /organizacoes/{id}` aceita `escopo_base`, sob
      `require_admin` (admin global — é decisão de contrato).
- [ ] **Tela da Carteira**: importador CSV, lista, categorias.

Dois defeitos conhecidos no backend da carteira, a decidir antes de botar tela
em cima:
- A importação é síncrona e linha a linha. 5.000 linhas = 5.000 chamadas dentro
  de um request; no Render é candidato a timeout, e sem transação o que estourar
  no meio deixa a carteira pela metade.
- `POST /carteira` recebe `data: Dict` cru, sem Pydantic — é o único endpoint do
  módulo sem validação, e é justamente o caminho "adicionar na mão" que a tela
  vai usar mais.

## Fila, na ordem combinada

2. **Arrancar o Brevo** (~9 lugares: `endpoints_webhooks.py` inteiro,
   `BREVO_WEBHOOK_SECRET`, `brevo_api_key` nas integrações, uma seção inteira de
   UI em Configurações). ⚠️ Some com a **detecção de bounce assíncrono** — só o
   webhook dava isso, e pixel não enxerga bounce. Decidir o substituto.
3. **Gmail OAuth por usuário.** Hoje é uma conta global (`GMAIL_OAUTH_*` em env,
   gerada rodando `scripts/autorizar_gmail.py` na mão) e só o cabeçalho `From`
   muda — o Gmail recusa ou marca como spam quando se envia como endereço que a
   conta autenticada não possui.
4. **Cobertura de log nos endpoints.** `security/audit.py` funciona e
   `AuditAction` prevê 22 ações; existem **4 chamadas** no backend inteiro (3 de
   login, 1 de "viu empresa"). Campanha, lote, CRM e carteira não deixam rastro.
   ❓ **Decidir primeiro:** auditoria (quem fez o quê, em tabela, para LGPD) ou
   log operacional (rastro em arquivo, para depurar)? São desenhos diferentes.

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
