# Diário do WhoDados

Registro do que foi **descoberto, decidido e corrigido** em cada sessão de
trabalho. Existe para ninguém precisar reler o código e a documentação inteira
para redescobrir o que já se soube uma vez.

> Este é o **histórico**. O mapa e as regras estão em
> [`../CLAUDE.md`](../CLAUDE.md); por onde continuar, em
> [`CONTINUAR.md`](CONTINUAR.md).

**Regras:**

- É **versionado de propósito.** Registro que fica só na máquina de quem
  escreveu não poupa o tempo de mais ninguém.
- Só entra aqui o que **não é óbvio no código**: o motivo de uma decisão, uma
  armadilha que custou tempo, um diagnóstico. O que o `git log` já conta não
  se repete aqui.
- Append-only, mais recente no topo. Não se reescreve entrada antiga — se algo
  se provou errado depois, a entrada nova corrige e diz qual.
- Log operacional (ruidoso, por execução) **não** vem para cá: vai em `logs/`,
  que é gitignorado.

---

## 2026-09-30 (parte 3) — Brevo fora, auditoria por middleware, telas auditadas

### Decidido

- **Auditoria por middleware, não endpoint a endpoint.** São 128 rotas e nascem
  rotas novas toda semana: lista manual garante que alguém esquece a próxima, e
  provavelmente a que importa. Mesmo argumento que o `VisitanteMiddleware` já
  faz no próprio docstring, e a mesma lição do vazamento de remetente — regra
  que vale para tudo mora num ponto por onde tudo passa.
- **Só escrita é auditada.** A tela de Empresas dispara várias leituras por
  mexida de filtro; afogar a tabela em `GET` tornaria a auditoria inútil
  justamente quando alguém precisasse procurar nela.
- **Duas menções ao Brevo ficaram de propósito** — a que explica de onde veio o
  número 300, e a que diz por que `registrar_evento_email` não tem chamador.
  Apagá-las perderia o motivo, que é o que o código sozinho não conta.

### Corrigido

| Commit | O quê |
|---|---|
| `367261c` | Brevo arrancado de 9 lugares |
| `b85add7` | Auditoria automática de toda escrita (7 testes novos) |
| `60ac55f` | `socios` e `whatsapp` deixavam de avisar quando o serviço caía |

Em `socios`, a falha exibia *"Nenhum sócio para este filtro"* — escondia a queda
**e** culpava a escolha de quem estava usando, que iria mexer no filtro tentando
consertar um serviço fora do ar. Em `whatsapp`, virava *"Nenhuma conversa
ainda"*: numa caixa de entrada, dizer que ninguém escreveu é o pior engano
possível, porque a pessoa para de procurar.

### O teste achou o que a leitura não achou

A primeira versão do middleware não registrava requisição que estourava: a
exceção subia antes da gravação, então a requisição que mais interessa auditar
era exatamente a que não ficava no registro. Um dos 7 testes novos pegou. É o
segundo caso no mesmo dia — o outro foi o gráfico que sumia com dados fora de
ordem.

### Deixado de fora, conscientemente

**Gmail OAuth por usuário.** Depende de cliente OAuth no Google Cloud e de
variáveis no Render que só a dona do projeto cria — sem isso o fluxo não roda
nem uma vez, nem para testar. Entregar às cegas um caminho de autenticação de
e-mail em produção quebraria sem aviso. Detalhe em [`CONTINUAR.md`](CONTINUAR.md).

---

## 2026-09-30 (parte 2) — Carteira fechada de ponta a ponta

### Descoberto

O interruptor não bastava. Mesmo depois de `escopo_base` virar configurável, a
**linha do boot desfazia a escolha**: `db/config.py:497` rodava a cada deploy.
O estado real morava no código, não no banco — um admin trocaria a fonte pela
tela e veria a mudança sumir sem aviso nenhum.

### Decidido

- **Seed de uma vez só**, marcado em `app_config`. A partir da primeira
  execução quem manda é o banco. Padrão reaproveitável para qualquer outro
  seed que hoje rode a cada boot.
- **A tela da Carteira aparece só para empresa de carteira**, espelhando o que
  já se fazia com Sócios (só para base Receita). Mesma ideia, sinal invertido.
- **Empresa de receita que chegar na URL da Carteira lê uma explicação**, não
  uma tela vazia. Tela vazia parece defeito; texto que diz por que está vazia e
  onde se troca a fonte resolve a dúvida sem suporte.

### Corrigido

| Commit | O quê |
|---|---|
| `a9b4c35` | Seletor de fonte em Configurações → Empresas; seed da JehJuh vira único |
| `247b9b7` | Tela `/dashboard/carteira`: total, categorias e importador de CSV |

O texto da tela carrega o que só existia no docstring do backend: só o CNPJ é
obrigatório, resubir atualiza em vez de duplicar, coluna vazia não apaga o
preenchido. E o `<details>` lista os cabeçalhos aceitos, porque a pergunta de
quem importa é sempre "meu cabeçalho serve?".

### Em aberto

A Carteira subiu com **dívida conhecida no backend** — importação síncrona
linha a linha (candidata a timeout no Render, sem transação) e `POST /carteira`
sem validação Pydantic. Nenhuma das duas bloqueia o uso hoje; as duas viram
problema com o primeiro cliente de lista grande. Detalhe em
[`CONTINUAR.md`](CONTINUAR.md).

---

## 2026-09-30 — Vazamento de remetente entre empresas, falhas silenciosas e processo

### Descoberto

**Um e-mail da SYVP saiu assinado como NRA.** Clicar "testar e-mail" logada na
SYVP entregava e-mail com remetente da NRA. A proteção contra isso **já
existia** em `_smtp_da_org` (empresa sem config devolve remetente vazio de
propósito, com comentário explicando o risco) — mas ela cobria só o caminho
SMTP, e o Gmail API entrou **na frente** dela refazendo o fallback com
`cfg.get("email_from") or settings.EMAIL_FROM`. Como em produção o Gmail está
sempre configurado, o guard virou código morto no dia em que o Gmail entrou.

O comentário do guard cita "o Brevo é um por empresa" — ou seja, ele foi
escrito na era do Brevo e ninguém voltou para ver se ainda cobria. **Comentário
órfão é a melhor pista que existe: ele descreve uma defesa que ficou para trás
da porta nova.**

**A carteira não era escolhível.** `escopo_base` não era escrito por nenhum
endpoint — só por uma linha do bootstrap (`UPDATE ... WHERE slug = 'jehjuh'`),
que roda a cada boot. Toda empresa nova nascia `receita`, e mudar no banco não
sobrevivia ao próximo deploy. Na prática os 5 endpoints de `/carteira` tinham
um único cliente possível.

**A suíte sempre rodou.** Concluí (e repeti) que `psycopg2` estava bloqueado
pela política do Windows. Estava — no Python **do sistema**. Com
`whodados/.venv/Scripts/python.exe` a suíte roda. Faltava só `pytest` no venv.

**Auditoria existe e quase não é usada.** `security/audit.py` grava em
`audit_log` e o enum `AuditAction` prevê 22 ações. Há **4 chamadas** no backend
inteiro: 3 de login e 1 de "viu uma empresa". Campanha, lote, CRM e carteira
não deixam rastro.

**O front não estava cheio de coisa parada** — ao contrário do esperado. Zero
páginas órfãs, zero componentes não importados, zero `TODO`. O buraco é outro:
a Carteira inteira tem backend pronto e nenhuma tela.

### Decidido

- **Regra do remetente fica num lugar só**, em `enviar_email`, antes de
  escolher transporte. Transporte novo passa por ela obrigatoriamente — foi
  exatamente a repetição da checagem por caminho que causou o vazamento.
- **Empresa sem remetente próprio não envia.** Preferimos parar de enviar a
  enviar assinado por outro cliente.
- **Trocar a fonte de prospecção é decisão de contrato**, então só admin
  global vira a chave — não o admin da empresa.
- **Registro durável é versionado; log operacional é gitignorado.** São coisas
  diferentes. O `kit-log-24h` que existia no repo apagava tudo com mais de 24h
  — serve para backup efêmero, não para memória de projeto.

### Corrigido

| Commit | O quê |
|---|---|
| `4f1cb9b` | Pesquisa fixada no banco; cidade em caixa alta (`PORTO ALEGRE` → `Porto Alegre`) no e-mail e no WhatsApp; `--` virando travessão |
| `0dff4f3` | Vazamento de remetente entre empresas |
| `bd333b9` | Hook que barra commit com suíte vermelha; `test_where_vazio` destravado |
| `6ccd107` | `escopo_base` deixa de ser hardcoded |
| `74e1b64` | Quatro falhas silenciosas no front |

As quatro falhas do front eram da mesma família — **erro se disfarçando de
estado normal**: `catch {}` em Configurações fazia o default aparecer como
salvo (e Salvar gravaria 2/5 por cima da regra real); erro em Notificações
virava "Nenhuma notificação pendente"; `pct()` mandava 0% real para o mesmo
"—" de "sem dado"; e o gráfico "Volume por dia" omitia os dias sem envio,
comprimindo o tempo justamente no gráfico feito para mostrar regularidade.

### Armadilhas para a próxima pessoa

- `whodados/frontend/.env.local` aponta para o backend de **produção**.
  `npm run dev` não é ambiente de teste.
- `security/` é **pacote**, não arquivo. `ls security.py` falha e engana.
- Não há migrations: schema nasce de `CREATE TABLE IF NOT EXISTS` em
  `db/config.py`, rodado a cada boot.
- `db/config.py:497` ainda refaz a JehJuh como carteira a cada deploy, e vai
  desfazer a escolha feita pelo admin. **Precisa ser desarmado junto com a UI
  do seletor.**

### Em aberto

1. Tela da Carteira (importador CSV) + UI do seletor + desarmar o boot
2. Arrancar o Brevo (9 lugares) — perde detecção de bounce assíncrono
3. Gmail OAuth por usuário, no lugar da conta global
4. Cobertura de log/auditoria nos endpoints
5. Auditoria das telas: faltam campanhas, crm, templates, socios, whatsapp,
   gastos, atividades e a ficha da empresa
