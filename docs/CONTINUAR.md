# Por onde continuar

**Estado em 2026-09-30.** Este arquivo é **sobrescrito** a cada sessão — ele
responde *"o que eu faço agora"*, não *"o que aconteceu"*. O histórico fica em
[`DIARIO.md`](DIARIO.md); o mapa e as regras, em [`../CLAUDE.md`](../CLAUDE.md).

Quem encerrar uma sessão reescreve este arquivo antes de sair.

---

## Estado atual

`main` = `60ac55f`. Suíte **48/48 verde**, `tsc --noEmit` limpo, `next build`
compila as 19 rotas. Árvore limpa.

Fechados nesta sessão: Carteira de ponta a ponta · Brevo arrancado · auditoria
automática de toda escrita · as 13 telas auditadas.

**Antes de configurar o e-mail da SYVP**, ver a seção abaixo — a ordem importa.

## Próximo passo: Gmail OAuth por usuário

**Deixado de fora de propósito.** É a única frente que eu não consigo entregar
e verificar sozinho, e entregar às cegas um caminho de autenticação de e-mail
em produção é o tipo de coisa que quebra sem aviso.

O que trava, e só você resolve:

- Um **cliente OAuth no Google Cloud Console** com a URI de redirect apontando
  para o backend em produção (`/api/v1/auth/gmail/callback`, a criar)
- `GMAIL_OAUTH_CLIENT_ID` e `GMAIL_OAUTH_CLIENT_SECRET` no Render
- A tela de consentimento publicada (ou os três usuários como testers)

Sem isso, o fluxo não roda nem uma vez — nem para eu testar.

O que muda quando vier: hoje é **uma conta global** (`GMAIL_OAUTH_*` em env,
gerada rodando `scripts/autorizar_gmail.py` na mão) e só o cabeçalho `From`
varia. O Gmail recusa ou marca como spam quando se envia como endereço que a
conta autenticada não possui — então "e-mail individual" hoje é só aparência.
O certo é botão "Conectar Gmail" por pessoa, refresh token guardado por
usuário/empresa, e `gmail_api.enviar` usando a credencial de quem dispara.

⚠️ **Isto afeta a configuração da SYVP.** Se cadastrar o remetente agora sob o
esquema global e depois migrar para OAuth por usuário, o cadastro é refeito.
Decidir se configura agora (funciona, com a ressalva do `From`) ou espera.

## Fila

- **Dívida da Carteira:** importação síncrona linha a linha (5.000 linhas =
  5.000 chamadas num request; candidata a timeout no Render, sem transação) e
  `POST /carteira` sem Pydantic. Nenhuma bloqueia hoje; viram problema com o
  primeiro cliente de lista grande.
- **Bounce sem substituto.** Arrancar o Brevo tirou a única fonte de
  `hard_bounce`/`soft_bounce`/`blocked`/`spam`. As colunas `bounce_*` em
  `emails_enviados` existem e ninguém preenche. `registrar_evento_email` ficou
  no lugar, marcado como sem chamador, para quando isso voltar pela Gmail API.
- **`EMAIL_LIMITE_DIARIO = 300`** é política nossa, não limite técnico — o
  Gmail dá 500/dia (2.000 no Workspace). Pode estar limitando à toa.

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
