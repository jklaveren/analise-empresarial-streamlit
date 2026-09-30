# WhoDados — leia antes de mexer

Plataforma B2B de inteligência empresarial **em produção** (NRA Advocacia):
investigação de sócios e dívidas ativas, CRM, campanhas por e-mail e WhatsApp.
Multiempresa: NRA, SYVP, JehJuh.

> **Três arquivos, três perguntas.** Este responde *o que existe e quais são as
> regras*. [`docs/CONTINUAR.md`](docs/CONTINUAR.md) responde *por onde eu
> continuo*. [`docs/DIARIO.md`](docs/DIARIO.md) responde *o que já se descobriu*
> — consulte antes de investigar algo do zero, a resposta pode já estar lá.

## Mapa

Todo o stack vive em `whodados/`:

| Onde | O quê |
|---|---|
| `whodados/frontend/` | Next.js → Vercel (`whodados-jet.vercel.app`) |
| `whodados/backend/` | FastAPI → Render (`whodados-backend.onrender.com`) |
| Supabase | PostgreSQL |
| `whodados/backend/endpoints_*.py` | Um arquivo por domínio, agregados em `endpoints.py` |
| `whodados/backend/db/config.py` | **O schema inteiro** (ver armadilhas) |
| `whodados/backend/security/` | Auditoria, rate limit, headers, visitante |

## Armadilhas que já custaram tempo

- **Rode os testes com o Python do venv**, sempre:
  `whodados/.venv/Scripts/python.exe -m pytest whodados/backend/tests -q`
  O Python do sistema está sob política de Controle de Aplicativo do Windows e
  não carrega `psycopg2` — a suíte falha no import e parece que "não roda aqui".
  Roda.
- **`whodados/frontend/.env.local` aponta para o backend de PRODUÇÃO.**
  `npm run dev` não é ambiente de teste. Botão de disparo ali manda e-mail de
  verdade.
- **Não há migrations.** O schema nasce de `CREATE TABLE IF NOT EXISTS` em
  `db/config.py` (`ensure_tables()` + `_run_ensure_multiempresa()`), rodado a
  cada boot. Tabela nova entra ali, e só existe depois do próximo deploy.
- **`security/` é pacote, não arquivo.** `ls security.py` falha e engana.
- **Brevo saiu.** Ainda há resíduo em ~9 lugares. O envio hoje é Gmail API, que
  tem prioridade sobre SMTP e curto-circuita (o Render bloqueia 587/465).

## Regras do projeto

1. **Testar antes de commitar.** Há hook em `.claude/settings.json` que barra
   `git commit` com a suíte vermelha. Ele cobre só o backend deste repo — o
   front é `tsc --noEmit` + `npm run build`, na mão.
2. **Empresa sem remetente próprio não envia e-mail.** Nunca cair na config
   global: já saiu e-mail da SYVP assinado como NRA por causa disso. A regra
   vive num lugar só, em `enviar_email` (`mailer/service.py`), antes de escolher
   transporte — transporte novo passa por ela obrigatoriamente. Não repita a
   checagem por caminho: foi assim que o vazamento aconteceu.
3. **Registre o que descobriu** em `docs/DIARIO.md` e atualize
   `docs/CONTINUAR.md` antes de encerrar. O custo caro não é o conserto, é
   redescobrir.
4. **Suíte vermelha se conserta, não se contorna.** Teste velho parado no
   vermelho ensina todo mundo a ignorar vermelho.
5. **Comentário que cita tecnologia antiga é suspeito.** O guard do remetente
   citava o Brevo, tinha sido escrito para o caminho SMTP, e não cobria mais o
   caminho real. Comentário órfão costuma marcar uma defesa que ficou para trás.

## Convenções

Código e commits em português, sem acento (`e'` para "é", `--` para travessão).
Comentário explica **por quê**, não o quê. Commits em Conventional Commits, com
o motivo no corpo.
