"""DB Config - WhoDados."""
from __future__ import annotations
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
try:
    from ..config import settings
except ImportError:
    import os as _os
    class _S:
        DATABASE_URL = _os.getenv("DATABASE_URL", "")
        DB_POOL_SIZE = int(_os.getenv("DB_POOL_SIZE", "5"))
        DB_POOL_TIMEOUT = int(_os.getenv("DB_POOL_TIMEOUT", "30"))
    settings = _S()
try:
    from ..logger import get_logger
except ImportError:
    import logging
    get_logger = lambda x: logging.getLogger(x)
log = get_logger(__name__)
_pool = None

def init_pool():
    global _pool
    if _pool: return _pool
    if not settings.DATABASE_URL: return None
    try:
        _pool = pool.ThreadedConnectionPool(1, settings.DB_POOL_SIZE, dsn=settings.DATABASE_URL, connect_timeout=settings.DB_POOL_TIMEOUT)
        return _pool
    except Exception as e: raise

@contextmanager
def get_conn():
    if _pool is None: init_pool()
    if _pool is None: raise RuntimeError("DB unavailable")
    c = _pool.getconn()
    try:
        yield c; c.commit()
    except:
        c.rollback(); raise
    finally:
        _pool.putconn(c)

@contextmanager
def get_cur(d=True):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor if d else None)
        try: yield cur
        finally: cur.close()

def ensure_tables():
    if not settings.DATABASE_URL: return
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS app_users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, email VARCHAR(255), is_admin BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS password_reset_tokens (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, token_hash VARCHAR(255) NOT NULL, expires_at TIMESTAMP WITH TIME ZONE NOT NULL, used BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash ON password_reset_tokens(token_hash)")
        cur.execute("CREATE TABLE IF NOT EXISTS crm (id SERIAL PRIMARY KEY, cnpj VARCHAR(18) UNIQUE NOT NULL, status VARCHAR(50), notas TEXT, data_atualizacao TIMESTAMP WITH TIME ZONE DEFAULT NOW(), criado_por VARCHAR(50))")
        cur.execute("CREATE TABLE IF NOT EXISTS email_templates (id SERIAL PRIMARY KEY, nome VARCHAR(100) NOT NULL, assunto VARCHAR(200) NOT NULL, corpo_html TEXT NOT NULL, corpo_texto TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), criado_por VARCHAR(50))")
        # Adiciona coluna categoria_cnae se nao existir (suporte a templates por CNAE)
        cur.execute("ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS categoria_cnae VARCHAR(50) DEFAULT 'todos'")
        # Card/imagem do template (enviada no corpo do email via {{imagem}})
        cur.execute("ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS imagem_data BYTEA")
        cur.execute("ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS imagem_mime VARCHAR(50)")
        cur.execute("ALTER TABLE email_templates ADD COLUMN IF NOT EXISTS tem_imagem BOOLEAN DEFAULT FALSE")
        cur.execute("CREATE TABLE IF NOT EXISTS campanhas (id SERIAL PRIMARY KEY, nome VARCHAR(200) NOT NULL, template_id INTEGER, filtros JSONB, status VARCHAR(50) DEFAULT 'rascunho', total_destinatarios INTEGER DEFAULT 0, enviados INTEGER DEFAULT 0, erros INTEGER DEFAULT 0, eh_sequencia BOOLEAN DEFAULT FALSE, dias_sequencia JSONB, agendada_para TIMESTAMP WITH TIME ZONE, iniciada_em TIMESTAMP WITH TIME ZONE, concluida_em TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), created_by VARCHAR(50))")
        # Canal (email/whatsapp) + envio em lotes diarios (o limite de
        # mensagens/dia do WhatsApp e' do Twilio, nao nosso -- tamanho_lote
        # deixa a campanha respeitar isso e ir mandando aos poucos em vez de
        # estourar o limite tentando mandar tudo de uma vez).
        cur.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS canal VARCHAR(20) DEFAULT 'email'")
        cur.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS mensagem TEXT")
        cur.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS tamanho_lote INTEGER")
        cur.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS repetir_ate DATE")
        cur.execute("ALTER TABLE campanhas ADD COLUMN IF NOT EXISTS ultimo_lote_em TIMESTAMP WITH TIME ZONE")
        # Ledger generico de quem ja foi contatado por qual campanha -- usado
        # pra calcular o "proximo lote" (quem do filtro ainda nao foi
        # contatado), independente do canal.
        cur.execute("""CREATE TABLE IF NOT EXISTS campanha_envios (
            id SERIAL PRIMARY KEY,
            campanha_id INTEGER NOT NULL REFERENCES campanhas(id) ON DELETE CASCADE,
            cnpj VARCHAR(18) NOT NULL,
            canal VARCHAR(20) NOT NULL,
            status VARCHAR(30) DEFAULT 'enviado',
            criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE (campanha_id, cnpj)
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_campanha_envios_campanha ON campanha_envios(campanha_id)")
        cur.execute("CREATE TABLE IF NOT EXISTS emails_enviados (id SERIAL PRIMARY KEY, campaign_id INTEGER, cnpj VARCHAR(18) NOT NULL, email_destino VARCHAR(255) NOT NULL, assunto VARCHAR(200), status VARCHAR(50) DEFAULT 'pendente', erro TEXT, sequencia_passo INTEGER DEFAULT 0, enviado_em TIMESTAMP WITH TIME ZONE, aberto_em TIMESTAMP WITH TIME ZONE, criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW())")
        cur.execute("CREATE TABLE IF NOT EXISTS notificacoes (id SERIAL PRIMARY KEY, tipo VARCHAR(50) NOT NULL, titulo VARCHAR(200) NOT NULL, mensagem TEXT, cnpj VARCHAR(18), user_id VARCHAR(50), lida BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())")        
        cur.execute("CREATE TABLE IF NOT EXISTS audit_log (id BIGSERIAL PRIMARY KEY, action VARCHAR(100) NOT NULL, user_id VARCHAR(50), ip_address INET, user_agent TEXT, resource_type VARCHAR(50), resource_id VARCHAR(100), details JSONB DEFAULT '{}'::jsonb, success BOOLEAN DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC)")
        cur.execute("CREATE TABLE IF NOT EXISTS login_attempts (id BIGSERIAL PRIMARY KEY, username VARCHAR(50) NOT NULL, ip_address INET, success BOOLEAN DEFAULT FALSE, attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW())")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON login_attempts(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_time ON login_attempts(attempted_at DESC)")
        # Metadata do pipeline de ETL (mes RF, trimestre PGFN, ultima sincronizacao,
        # contagens) -- tambem criada por database_config.py::ensure_app_tables no
        # lado do script de sincronizacao; criada aqui tambem pra API sempre
        # conseguir ler (retornando vazio) mesmo que o pipeline nunca tenha rodado.
        cur.execute("CREATE TABLE IF NOT EXISTS pipeline_metadata (chave VARCHAR(100) PRIMARY KEY, valor TEXT, atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW())")
        # Configuracoes gerais da aplicacao (regras do CRM/Monitor, etc.) --
        # mesmo esquema de chave-valor do pipeline_metadata, mas para
        # ajustes feitos pelo usuario pela tela de Configuracoes.
        cur.execute("CREATE TABLE IF NOT EXISTS app_config (chave VARCHAR(100) PRIMARY KEY, valor TEXT, atualizado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW())")
        # Tabelas de lookup dos dados do ETL (municipios: cod->nome; cnaes:
        # codigo->descricao da atividade). Criadas aqui (vazias) pra os JOINs
        # dos endpoints de empresas/analytics nunca quebrarem, mesmo antes do
        # primeiro sync. O scripts/sync_data_to_db.py recria com os dados
        # reais (to_sql if_exists="replace") quando o pipeline roda.
        cur.execute("CREATE TABLE IF NOT EXISTS municipios (cod_municipio VARCHAR(10) PRIMARY KEY, nome_municipio VARCHAR(200))")
        cur.execute("CREATE TABLE IF NOT EXISTS cnaes (codigo_cnae VARCHAR(10) PRIMARY KEY, descricao_cnae VARCHAR(300))")
        # Potencial pre-calculado (nao recalculado a cada consulta -- com
        # 1.68M+ linhas em dados_empresas, o CASE de potencial combinado com
        # filtros grandes (ex.: lista de 200+ CNAEs) estourava o timeout do
        # banco). Repopulada inteira via atualizar_potencial_empresas() --
        # rodar isso de novo sempre que o ETL recarregar dados_empresas
        # (a carga usa to_sql replace, entao a tabela e' recriada do zero).
        # CHAR(14), nao VARCHAR -- tem que bater exatamente com o tipo de
        # dados_empresas."CNPJ_COMPLETO" (CHAR, do to_sql do pandas), senao
        # o JOIN faz cast implicito linha a linha e ignora os indices dos
        # dois lados (era o gargalo real por tras da consulta lenta).
        cur.execute("""CREATE TABLE IF NOT EXISTS empresas_potencial (
            cnpj_completo CHAR(14) PRIMARY KEY,
            potencial_score NUMERIC,
            potencial_tier VARCHAR(10),
            categoria_cnae VARCHAR(20)
        )""")
        cur.execute("ALTER TABLE empresas_potencial ADD COLUMN IF NOT EXISTS categoria_cnae VARCHAR(20)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_empresas_potencial_tier ON empresas_potencial(potencial_tier)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_empresas_potencial_categoria ON empresas_potencial(categoria_cnae)")
        conn.commit(); cur.close()
    _ensure_enriquecimento_table()
    _ensure_multiempresa()


def _ensure_multiempresa():
    """Multi-tenant (empresas NRA / SYVP). Fase aditiva: cria as tabelas de
    organizacao, o vinculo usuario<->empresa e a config SMTP por empresa,
    adiciona a coluna organizacao_id (nullable) nas tabelas de controle e faz
    a migracao (tudo que ja existe vira NRA). NAO mexe no UNIQUE do CRM nem no
    scoping das queries -- isso vem junto com o codigo que depende, para esta
    etapa nao quebrar nada. Idempotente: roda a cada boot sem efeito colateral.
    Ver plano multi-empresa (memoria: whodados-multiempresa-nra-syvp).

    Envolvido em try/except: se algo falhar, apenas loga e segue (o app nao
    cai por causa da migracao) -- como e idempotente, re-tenta no proximo boot."""
    import os
    try:
        _run_ensure_multiempresa(os)
    except Exception as e:
        log.error(f"Falha na migracao multi-empresa (sera retentada no proximo boot): {e}")


def _run_ensure_multiempresa(os):
    with get_conn() as conn:
        cur = conn.cursor()

        # --- Tabelas de organizacao ---
        cur.execute("""CREATE TABLE IF NOT EXISTS organizacoes (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(120) NOT NULL,
            slug VARCHAR(60) UNIQUE NOT NULL,
            ativo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS usuario_organizacoes (
            user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
            organizacao_id INTEGER NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (user_id, organizacao_id)
        )""")
        # Papel do usuario DENTRO dessa empresa (hierarquia: Operador Global
        # [app_users.is_admin] > admin [por empresa] > membro > visitante).
        # 'admin' aqui e' escopado a ESSA organizacao -- diferente do
        # is_admin global, que da acesso a todas. 'visitante' e' bloqueado
        # em quase tudo pelo VisitanteMiddleware (main.py) e ve dados
        # mascarados nas Empresas -- pensado pra dar acesso a alguem de
        # fora (ex.: recrutador) sem expor dado real de cliente.
        cur.execute("ALTER TABLE usuario_organizacoes ADD COLUMN IF NOT EXISTS papel VARCHAR(20) DEFAULT 'membro'")
        cur.execute("""CREATE TABLE IF NOT EXISTS org_smtp_config (
            organizacao_id INTEGER PRIMARY KEY REFERENCES organizacoes(id) ON DELETE CASCADE,
            smtp_host VARCHAR(200),
            smtp_port INTEGER DEFAULT 587,
            smtp_username VARCHAR(200),
            smtp_password VARCHAR(255),
            smtp_use_tls BOOLEAN DEFAULT TRUE,
            email_from VARCHAR(255),
            email_from_name VARCHAR(120),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""")
        # Assinatura de e-mail por empresa: HTML livre (com {{logo}}) + logo.
        cur.execute("ALTER TABLE org_smtp_config ADD COLUMN IF NOT EXISTS assinatura_html TEXT")
        cur.execute("ALTER TABLE org_smtp_config ADD COLUMN IF NOT EXISTS logo_data BYTEA")
        cur.execute("ALTER TABLE org_smtp_config ADD COLUMN IF NOT EXISTS logo_mime VARCHAR(50)")

        # --- Seed das empresas (idempotente por slug) ---
        cur.execute("INSERT INTO organizacoes (nome, slug) VALUES ('NRA', 'nra') ON CONFLICT (slug) DO NOTHING")
        cur.execute("INSERT INTO organizacoes (nome, slug) VALUES ('SYVP', 'syvp') ON CONFLICT (slug) DO NOTHING")
        # JehJuh nao usa a base da Receita Federal -- tem base propria. A flag
        # e' por empresa (nao por usuario): quem entra nela nao ve Prospeccao.
        cur.execute("ALTER TABLE organizacoes ADD COLUMN IF NOT EXISTS usa_base_receita BOOLEAN DEFAULT TRUE")
        cur.execute("INSERT INTO organizacoes (nome, slug, usa_base_receita) VALUES ('JehJuh', 'jehjuh', FALSE) ON CONFLICT (slug) DO NOTHING")

        # --- jehzinha (admin) tem acesso as duas ---
        cur.execute("""INSERT INTO usuario_organizacoes (user_id, organizacao_id)
            SELECT u.id, o.id FROM app_users u CROSS JOIN organizacoes o
            WHERE u.username = 'jehzinha'
            ON CONFLICT DO NOTHING""")

        # Juliana opera somente a JehJuh (admin de la' dentro).
        cur.execute("""INSERT INTO usuario_organizacoes (user_id, organizacao_id, papel)
            SELECT u.id, o.id, 'admin' FROM app_users u CROSS JOIN organizacoes o
            WHERE u.username = 'juliana' AND o.slug = 'jehjuh'
            ON CONFLICT DO NOTHING""")

        # --- Coluna organizacao_id (nullable) + indice nas tabelas de controle ---
        for tabela in ("crm", "email_templates", "campanhas", "emails_enviados", "notificacoes"):
            cur.execute(f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS organizacao_id INTEGER")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{tabela}_org ON {tabela}(organizacao_id)")

        # --- Migracao: tudo que ja existe vira NRA ---
        for tabela in ("crm", "email_templates", "campanhas", "emails_enviados", "notificacoes"):
            cur.execute(
                f"UPDATE {tabela} SET organizacao_id = "
                f"(SELECT id FROM organizacoes WHERE slug = 'nra') "
                f"WHERE organizacao_id IS NULL"
            )

        # --- CRM: troca o UNIQUE(cnpj) global pelo UNIQUE(empresa, cnpj) ---
        # O antigo impedia as duas empresas terem CRM do mesmo CNPJ. Rodado
        # depois do backfill (coluna ja preenchida). Idempotente. O ON CONFLICT
        # em create_or_update_crm depende deste indice composto.
        cur.execute("ALTER TABLE crm DROP CONSTRAINT IF EXISTS crm_cnpj_key")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_crm_org_cnpj ON crm(organizacao_id, cnpj)")

        # --- CRM: classificacao de perfil (ideal / possivel / fora do perfil) ---
        # Criado automaticamente no boot; nao perde dados nem quebra nada.
        cur.execute("ALTER TABLE crm ADD COLUMN IF NOT EXISTS classificacao VARCHAR(30)")
        cur.execute("ALTER TABLE crm ADD COLUMN IF NOT EXISTS motivo VARCHAR(255)")
        cur.execute("ALTER TABLE crm ADD COLUMN IF NOT EXISTS parceiro BOOLEAN DEFAULT FALSE")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_classificacao ON crm(classificacao)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_parceiro ON crm(parceiro)")

        # --- Migra o SMTP global (.env) para a NRA como valor inicial ---
        smtp_host = os.getenv("SMTP_HOST", "").strip()
        if smtp_host:
            cur.execute(
                """INSERT INTO org_smtp_config
                     (organizacao_id, smtp_host, smtp_port, smtp_username,
                      smtp_password, smtp_use_tls, email_from, email_from_name)
                   SELECT o.id, %s, %s, %s, %s, %s, %s, %s
                     FROM organizacoes o WHERE o.slug = 'nra'
                   ON CONFLICT (organizacao_id) DO NOTHING""",
                (
                    smtp_host,
                    int(os.getenv("SMTP_PORT", "587") or "587"),
                    os.getenv("SMTP_USERNAME", "").strip(),
                    os.getenv("SMTP_PASSWORD", "").strip(),
                    os.getenv("SMTP_USE_TLS", "true").lower() == "true",
                    os.getenv("EMAIL_FROM", "").strip(),
                    os.getenv("EMAIL_FROM_NAME", "").strip(),
                ),
            )

        # --- Tabela de integracoes externas (Brevo, Twilio) ---
        cur.execute(
            """CREATE TABLE IF NOT EXISTS integracao_configs (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                descricao VARCHAR(255),
                ativo BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )"""
        )

        # --- WhatsApp (Twilio): historico de mensagens enviadas/recebidas.
        # organizacao_id fica nullable pra nao quebrar mensagens antigas sem
        # org resolvida; cnpj e' um best-effort match pelo telefone (pode ficar
        # NULL se nao achar nenhuma empresa com esse numero).
        cur.execute(
            """CREATE TABLE IF NOT EXISTS whatsapp_mensagens (
                id SERIAL PRIMARY KEY,
                organizacao_id INTEGER REFERENCES organizacoes(id) ON DELETE SET NULL,
                cnpj VARCHAR(18),
                telefone VARCHAR(20) NOT NULL,
                direcao VARCHAR(10) NOT NULL,
                corpo TEXT,
                status VARCHAR(30) DEFAULT 'recebida',
                twilio_sid VARCHAR(64),
                lida BOOLEAN DEFAULT FALSE,
                criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_msg_telefone ON whatsapp_mensagens(telefone)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_msg_criado ON whatsapp_mensagens(criado_em DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_msg_org ON whatsapp_mensagens(organizacao_id)")

        # Atividades/tarefas do CRM -- atribuiveis a um usuario da mesma
        # organizacao (ex.: os socios da SVYP dividindo follow-ups entre si).
        # cnpj e' OPCIONAL: boa parte das tarefas entre socios nao tem empresa
        # nenhuma envolvida ("revisar proposta", "ligar pro contador"), e
        # exigir empresa obrigava a entrar num cliente antes de criar tarefa.
        cur.execute("""CREATE TABLE IF NOT EXISTS crm_atividades (
            id SERIAL PRIMARY KEY,
            organizacao_id INTEGER REFERENCES organizacoes(id) ON DELETE CASCADE,
            cnpj VARCHAR(18),
            titulo VARCHAR(200) NOT NULL,
            tipo VARCHAR(30) DEFAULT 'tarefa',
            descricao TEXT,
            responsavel_user_id INTEGER REFERENCES app_users(id) ON DELETE SET NULL,
            prazo DATE,
            status VARCHAR(20) DEFAULT 'pendente',
            criado_por VARCHAR(50),
            criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            concluido_em TIMESTAMP WITH TIME ZONE
        )""")
        # A tabela pode ja existir com cnpj NOT NULL (versao anterior).
        cur.execute("ALTER TABLE crm_atividades ALTER COLUMN cnpj DROP NOT NULL")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_atividades_cnpj ON crm_atividades(cnpj)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_atividades_responsavel ON crm_atividades(responsavel_user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_atividades_org ON crm_atividades(organizacao_id)")

        # Historico da atividade: comentario escrito pelo usuario E registro
        # automatico de mudanca de status/prazo ("Juliana moveu para Em
        # andamento", "Juliana mudou o prazo para 20/09"). Uma linha por
        # evento -- e' o acompanhamento da tarefa, nao da empresa.
        cur.execute("""CREATE TABLE IF NOT EXISTS crm_atividade_historico (
            id SERIAL PRIMARY KEY,
            atividade_id INTEGER NOT NULL REFERENCES crm_atividades(id) ON DELETE CASCADE,
            tipo VARCHAR(20) NOT NULL DEFAULT 'comentario',
            texto TEXT,
            de VARCHAR(50),
            para VARCHAR(50),
            autor VARCHAR(50),
            criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_atv_hist_atividade ON crm_atividade_historico(atividade_id)")

        # Descadastro de e-mail (LGPD/opt-out) -- GLOBAL, nao por empresa: se
        # alguem pede pra nao receber mais, isso vale pra NRA e SYVP, nao so'
        # pra quem mandou o e-mail que ela descadastrou. Toda campanha de
        # e-mail tem que respeitar isso (ver mailer/service.py) -- e' regra
        # do negocio, nao op'cao de template.
        cur.execute("""CREATE TABLE IF NOT EXISTS emails_descadastrados (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            cnpj VARCHAR(18),
            motivo TEXT,
            criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )""")

        conn.commit(); cur.close()


def _ensure_enriquecimento_table():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS enriquecimento_contatos (
            id SERIAL PRIMARY KEY,
            cnpj VARCHAR(18) NOT NULL,
            tipo_alvo VARCHAR(20) NOT NULL,
            nome_alvo VARCHAR(255),
            campo VARCHAR(30) NOT NULL,
            valor TEXT,
            fonte_url TEXT,
            fonte_titulo TEXT,
            base_legal VARCHAR(50) NOT NULL DEFAULT \'legitimo_interesse_dados_publicos\',
            coletado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            coletado_por VARCHAR(100),
            removido_em TIMESTAMP WITH TIME ZONE
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_enriquecimento_cnpj ON enriquecimento_contatos(cnpj)")
        conn.commit(); cur.close()

def check_health():
    try:
        with get_conn() as conn:
            cur = conn.cursor(); cur.execute("SELECT 1"); cur.close(); return True
    except: return False

ensure_tables_exist = ensure_tables
check_database_health = check_health
get_db_cursor = get_cur
