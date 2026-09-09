"""DB Service - WhoDados 2.0."""
from __future__ import annotations
import json
from typing import List, Dict, Optional, Any
try:
    from .config import get_db_cursor
except ImportError:
    from backend.db.config import get_db_cursor
try:
    from ..logger import get_logger
except ImportError:
    import logging
    get_logger = lambda x: logging.getLogger(x)
log = get_logger(__name__)

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM app_users WHERE username = %s", (username,))
        return cur.fetchone()

def create_user_record(username: str, password_hash: str, email: Optional[str] = None, is_admin: bool = False) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO app_users (username, password_hash, email, is_admin) VALUES (%s, %s, %s, %s) RETURNING *", (username, password_hash, email, is_admin))
        return cur.fetchone()


def salvar_enriquecimento(cnpj: str, itens: List[Dict[str, Any]], coletado_por: str) -> List[Dict[str, Any]]:
    """Grava os itens encontrados pelo agente de enriquecimento. Cada item
    precisa ter fonte_url -- nao gravamos nada sem proveniencia registrada."""
    salvos: List[Dict[str, Any]] = []
    with get_db_cursor() as cur:
        for item in itens:
            if not item.get("fonte_url"):
                continue
            cur.execute(
                """INSERT INTO enriquecimento_contatos
                   (cnpj, tipo_alvo, nome_alvo, campo, valor, fonte_url, fonte_titulo, coletado_por)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (
                    cnpj,
                    item.get("tipo_alvo", "empresa"),
                    item.get("nome_alvo"),
                    item.get("campo"),
                    item.get("valor"),
                    item.get("fonte_url"),
                    item.get("fonte_titulo"),
                    coletado_por,
                ),
            )
            salvos.append(cur.fetchone())
    return salvos

def listar_enriquecimento(cnpj: str) -> List[Dict[str, Any]]:
    """So retorna itens ainda nao removidos (removido_em IS NULL)."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM enriquecimento_contatos WHERE cnpj = %s AND removido_em IS NULL ORDER BY coletado_em DESC",
            (cnpj,),
        )
        return cur.fetchall()

def remover_enriquecimento(cnpj: str) -> int:
    """Direito de exclusao (LGPD): apaga o dado pessoal coletado (valor,
    fonte) mas mantem a linha com removido_em preenchido, como registro de
    auditoria de que a remocao aconteceu -- sem guardar o dado em si."""
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE enriquecimento_contatos
               SET valor = NULL, fonte_url = NULL, fonte_titulo = NULL, removido_em = NOW()
               WHERE cnpj = %s AND removido_em IS NULL RETURNING id""",
            (cnpj,),
        )
        return len(cur.fetchall())

def get_crm_by_cnpj(cnpj: str) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM crm WHERE cnpj = %s", (cnpj,))
        return cur.fetchone()

def get_crm_all() -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM crm ORDER BY data_atualizacao DESC")
        return cur.fetchall()

def create_or_update_crm(cnpj: str, status: Optional[str] = None, notas: Optional[str] = None, criado_por: Optional[str] = None) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute("""INSERT INTO crm (cnpj, status, notas, criado_por, data_atualizacao) VALUES (%s, %s, %s, %s, NOW()) ON CONFLICT (cnpj) DO UPDATE SET status = COALESCE(EXCLUDED.status, crm.status), notas = COALESCE(EXCLUDED.notas, crm.notas), data_atualizacao = NOW() RETURNING *""", (cnpj, status, notas, criado_por))
        return cur.fetchone()

# Colunas do template retornadas nas listagens (NUNCA inclui imagem_data -- ela e' pesada
# e so' e' buscada de fato pelo endpoint /templates/{id}/imagem).
_TEMPLATE_COLS = "id, nome, assunto, corpo_html, corpo_texto, categoria_cnae, criado_por, created_at, updated_at, tem_imagem"

def _com_imagem_url(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Adiciona o campo calculado imagem_url quando o template tem um card/imagem salvo."""
    if not row:
        return row
    if row.get("tem_imagem"):
        try:
            from ..config import settings
        except ImportError:
            from config import settings
        row["imagem_url"] = f"{settings.API_PUBLIC_URL}/api/v1/templates/{row['id']}/imagem"
    else:
        row["imagem_url"] = None
    return row

def create_template(nome: str, assunto: str, corpo_html: str, corpo_texto: Optional[str] = None, criado_por: Optional[str] = None, categoria_cnae: Optional[str] = "todos") -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute(f"INSERT INTO email_templates (nome, assunto, corpo_html, corpo_texto, criado_por, categoria_cnae) VALUES (%s, %s, %s, %s, %s, %s) RETURNING {_TEMPLATE_COLS}", (nome, assunto, corpo_html, corpo_texto, criado_por, categoria_cnae or "todos"))
        return _com_imagem_url(cur.fetchone())

def update_template(template_id: int, nome: Optional[str] = None, assunto: Optional[str] = None, corpo_html: Optional[str] = None, corpo_texto: Optional[str] = None, categoria_cnae: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        fields = []
        params = []
        if nome is not None: fields.append("nome = %s"); params.append(nome)
        if assunto is not None: fields.append("assunto = %s"); params.append(assunto)
        if corpo_html is not None: fields.append("corpo_html = %s"); params.append(corpo_html)
        if corpo_texto is not None: fields.append("corpo_texto = %s"); params.append(corpo_texto)
        if categoria_cnae is not None: fields.append("categoria_cnae = %s"); params.append(categoria_cnae)
        if not fields:
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE id = %s", (template_id,))
            return _com_imagem_url(cur.fetchone())
        fields.append("updated_at = NOW()")
        params.append(template_id)
        sql = "UPDATE email_templates SET " + ", ".join(fields) + f" WHERE id = %s RETURNING {_TEMPLATE_COLS}"
        cur.execute(sql, params)
        return _com_imagem_url(cur.fetchone())

def get_template(template_id: int) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE id = %s", (template_id,))
        return _com_imagem_url(cur.fetchone())

def get_all_templates() -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates ORDER BY created_at DESC")
        return [_com_imagem_url(r) for r in cur.fetchall()]

def delete_template(template_id: int) -> bool:
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM email_templates WHERE id = %s", (template_id,))
        return cur.rowcount > 0

def get_templates_by_categoria(categoria_cnae: str) -> List[Dict[str, Any]]:
    """Retorna templates filtrados por categoria. Se categoria = 'todos', traz todos."""
    with get_db_cursor() as cur:
        if categoria_cnae == "todos":
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE categoria_cnae = 'todos' ORDER BY created_at DESC")
        else:
            # Pega templates da categoria especifica + templates 'todos' (fallback)
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE categoria_cnae IN (%s, 'todos') ORDER BY categoria_cnae DESC, created_at DESC", (categoria_cnae,))
        return [_com_imagem_url(r) for r in cur.fetchall()]

def set_template_imagem(template_id: int, imagem_bytes: bytes, mime: str) -> Optional[Dict[str, Any]]:
    """Salva/substitui o card (imagem) de um template. Facilmente re-chamavel para trocar a imagem."""
    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE email_templates SET imagem_data = %s, imagem_mime = %s, tem_imagem = TRUE, updated_at = NOW() WHERE id = %s RETURNING {_TEMPLATE_COLS}",
            (imagem_bytes, mime, template_id),
        )
        return _com_imagem_url(cur.fetchone())

def get_template_imagem(template_id: int) -> Optional[Dict[str, Any]]:
    """Le os bytes crus da imagem -- usado apenas pelo endpoint publico que serve a imagem."""
    with get_db_cursor() as cur:
        cur.execute("SELECT imagem_data, imagem_mime FROM email_templates WHERE id = %s AND tem_imagem = TRUE", (template_id,))
        return cur.fetchone()

def clear_template_imagem(template_id: int) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE email_templates SET imagem_data = NULL, imagem_mime = NULL, tem_imagem = FALSE, updated_at = NOW() WHERE id = %s RETURNING {_TEMPLATE_COLS}",
            (template_id,),
        )
        return _com_imagem_url(cur.fetchone())
def create_campanha(nome: str, template_id: int, filtros: Dict, created_by: Optional[str] = None, eh_sequencia: bool = False, agendada_para: Optional[str] = None) -> Dict[str, Any]:
    status = "agendada" if agendada_para else "rascunho"
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO campanhas (nome, template_id, filtros, status, created_by, eh_sequencia, agendada_para) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *", (nome, template_id, json.dumps(filtros or {}), status, created_by, eh_sequencia, agendada_para))
        row = cur.fetchone()
        if row and row.get("filtros") and isinstance(row["filtros"], str):
            try: row["filtros"] = json.loads(row["filtros"])
            except: pass
        return row

def get_campanha(campanha_id: int) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM campanhas WHERE id = %s", (campanha_id,))
        row = cur.fetchone()
        if row and row.get("filtros") and isinstance(row["filtros"], str):
            try: row["filtros"] = json.loads(row["filtros"])
            except: pass
        return row

def get_all_campanhas() -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM campanhas ORDER BY created_at DESC")
        rows = cur.fetchall()
        for r in rows:
            if r and r.get("filtros") and isinstance(r["filtros"], str):
                try: r["filtros"] = json.loads(r["filtros"])
                except: pass
        return rows

def update_campanha_status(campanha_id: int, status: str, **kwargs) -> Optional[Dict[str, Any]]:
    sets = [f"{k} = %s" for k in kwargs.keys()]
    sets.append("status = %s")
    vals = list(kwargs.values()) + [status, campanha_id]
    with get_db_cursor() as cur:
        cur.execute(f"UPDATE campanhas SET {', '.join(sets)} WHERE id = %s RETURNING *", vals)
        row = cur.fetchone()
        if row and row.get("filtros") and isinstance(row["filtros"], str):
            try: row["filtros"] = json.loads(row["filtros"])
            except: pass
        return row

def create_email_enviado(campaign_id: Optional[int], cnpj: str, email_destino: str, assunto: Optional[str] = None, sequencia_passo: int = 0) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO emails_enviados (campaign_id, cnpj, email_destino, assunto, sequencia_passo) VALUES (%s, %s, %s, %s, %s) RETURNING *", (campaign_id, cnpj, email_destino, assunto, sequencia_passo))
        return cur.fetchone()

def update_email_enviado(email_id: int, status: str, erro: Optional[str] = None) -> None:
    with get_db_cursor() as cur:
        if erro:
            cur.execute("UPDATE emails_enviados SET status = %s, erro = %s, enviado_em = NOW() WHERE id = %s", (status, erro, email_id))
        else:
            cur.execute("UPDATE emails_enviados SET status = %s, enviado_em = NOW() WHERE id = %s", (status, email_id))

def get_emails_enviados_by_campanha(campaign_id: int) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM emails_enviados WHERE campaign_id = %s ORDER BY criado_em DESC", (campaign_id,))
        return cur.fetchall()
def create_notificacao(tipo: str, titulo: str, mensagem: Optional[str] = None, cnpj: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO notificacoes (tipo, titulo, mensagem, cnpj, user_id) VALUES (%s, %s, %s, %s, %s) RETURNING *", (tipo, titulo, mensagem, cnpj, user_id))
        return cur.fetchone()

def get_notificacoes(user_id: Optional[str] = None, lidas: Optional[bool] = None, limit: int = 100) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        sql = "SELECT * FROM notificacoes WHERE 1=1"
        params = []
        if user_id:
            sql += " AND (user_id = %s OR user_id IS NULL)"
            params.append(user_id)
        if lidas is not None:
            sql += " AND lida = %s"
            params.append(lidas)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        return cur.fetchall()

def mark_notificacao_lida(notificacao_id: int) -> bool:
    with get_db_cursor() as cur:
        cur.execute("UPDATE notificacoes SET lida = TRUE WHERE id = %s", (notificacao_id,))
        return cur.rowcount > 0


# ==================== MONITOR DE EMAILS (FOLLOW-UP) ====================

def get_emails_for_monitor(
    campaign_id=None,
    dias_sla: int = 7,
    limit: int = 200,
    offset: int = 0,
):
    """
    Retorna e-mails enviados com cálculo de status de semáforo para follow-up.

    Status do semáforo:
      - verde:    aberto_em IS NOT NULL (há resposta/interação)
                  OU enviado há <= 2 dias (ainda no início da janela)
      - amarelo:  enviado há 3-5 dias E ainda sem aberto_em (atenção)
      - vermelho: enviado há > 5 dias E ainda sem aberto_em (follow-up urgente)
      - cinza:    status != 'enviado' (pendente, erro, etc.)
    """
    with get_db_cursor() as cur:
        params = []
        where_campaign = ""
        if campaign_id:
            where_campaign = "AND e.campaign_id = %s"
            params.append(campaign_id)

        sql = f"""
            SELECT
                e.id,
                e.campaign_id,
                e.cnpj,
                e.email_destino,
                e.assunto,
                e.status,
                e.erro,
                e.sequencia_passo,
                e.enviado_em,
                e.aberto_em,
                e.criado_em,
                c.nome as campanha_nome,
                COALESCE(
                    GREATEST(EXTRACT(EPOCH FROM (NOW() - e.enviado_em)) / 86400.0, 0),
                    0
                ) as dias_desde_envio,
                CASE
                    WHEN e.enviado_em IS NULL THEN 'cinza'
                    WHEN e.aberto_em IS NOT NULL THEN 'verde'
                    WHEN GREATEST(EXTRACT(EPOCH FROM (NOW() - e.enviado_em)) / 86400.0, 0) <= 2 THEN 'verde'
                    WHEN GREATEST(EXTRACT(EPOCH FROM (NOW() - e.enviado_em)) / 86400.0, 0) <= 5 THEN 'amarelo'
                    ELSE 'vermelho'
                END as semaforo_status,
                emp.razao_social,
                emp.nome_fantasia
            FROM emails_enviados e
            LEFT JOIN campanhas c ON c.id = e.campaign_id
            LEFT JOIN dados_empresas emp ON emp.cnpj_completo = e.cnpj
            WHERE e.enviado_em IS NOT NULL
            {where_campaign}
            ORDER BY e.enviado_em DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows


def get_monitor_stats(dias_sla: int = 7):
    """Retorna estatísticas agregadas para o dashboard de monitoramento."""
    with get_db_cursor() as cur:
        sql = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'enviado') as total_enviados,
                COUNT(*) FILTER (
                    WHERE (aberto_em IS NOT NULL)
                       OR (enviado_em IS NOT NULL AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 <= 2)
                ) as verde,
                COUNT(*) FILTER (
                    WHERE enviado_em IS NOT NULL
                      AND aberto_em IS NULL
                      AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 > 2
                      AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 <= 5
                ) as amarelo,
                COUNT(*) FILTER (
                    WHERE enviado_em IS NOT NULL
                      AND aberto_em IS NULL
                      AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 > 5
                ) as vermelho,
                COUNT(*) FILTER (WHERE status != 'enviado') as cinza
            FROM emails_enviados
        """
        cur.execute(sql)
        row = cur.fetchone()
        return dict(row) if row else {"total_enviados": 0, "verde": 0, "amarelo": 0, "vermelho": 0, "cinza": 0}


def get_emails_vermelhos_para_followup(limite: int = 50):
    """Retorna os e-mails mais críticos (vermelho) para disparo de follow-up."""
    with get_db_cursor() as cur:
        sql = """
            SELECT
                e.*,
                c.nome as campanha_nome,
                GREATEST(EXTRACT(EPOCH FROM (NOW() - e.enviado_em)) / 86400.0, 0) as dias_desde_envio,
                emp.razao_social,
                emp.nome_fantasia
            FROM emails_enviados e
            LEFT JOIN campanhas c ON c.id = e.campaign_id
            LEFT JOIN dados_empresas emp ON emp.cnpj_completo = e.cnpj
            WHERE e.enviado_em IS NOT NULL
              AND e.aberto_em IS NULL
              AND GREATEST(EXTRACT(EPOCH FROM (NOW() - e.enviado_em)) / 86400.0, 0) > 5
            ORDER BY e.enviado_em ASC
            LIMIT %s
        """
        cur.execute(sql, (limite,))
        return cur.fetchall()


def marcar_email_aberto(email_id: int) -> bool:
    """Marca o e-mail como aberto (usado por pixel de tracking)."""
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE emails_enviados SET aberto_em = NOW() WHERE id = %s AND aberto_em IS NULL",
            (email_id,),
        )
        return cur.rowcount > 0



def create_audit_log(action: str, user_id: Optional[str] = None, ip_address: Optional[str] = None, resource_type: Optional[str] = None, resource_id: Optional[str] = None, details: Optional[dict] = None, success: bool = True) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (action, user_id, ip_address, resource_type, resource_id, details, success) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (action, user_id, ip_address, resource_type, resource_id, json.dumps(details or {}), success)
        )
        return cur.fetchone()


def record_login_attempt(username: str, ip_address: Optional[str] = None, success: bool = True) -> None:
    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO login_attempts (username, ip_address, success) VALUES (%s, %s, %s)",
            (username, ip_address, success)
        )


def is_account_locked(username: str, max_attempts: int = 5, lockout_minutes: int = 15) -> bool:
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as cnt FROM login_attempts WHERE username = %s AND success = FALSE AND attempted_at > NOW() - INTERVAL '%s minutes'",
            (username, lockout_minutes)
        )
        row = cur.fetchone()
        return (row and row.get("cnt", 0) >= max_attempts)


def get_audit_logs(user_id: Optional[str] = None, action: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if user_id:
            sql += " AND user_id = %s"
            params.append(user_id)
        if action:
            sql += " AND action = %s"
            params.append(action)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        return cur.fetchall()


# ==================== PASSWORD RESET ====================

def create_password_reset_token(user_id: int, token_hash: str, expires_at) -> Dict[str, Any]:
    """Cria token de recuperacao de senha."""
    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s) RETURNING *",
            (user_id, token_hash, expires_at)
        )
        return cur.fetchone()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Busca usuario pelo e-mail."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM app_users WHERE email = %s", (email,))
        return cur.fetchone()


def get_user_by_username_or_email(username_or_email: str) -> Optional[Dict[str, Any]]:
    """Busca usuario pelo username ou e-mail."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM app_users WHERE username = %s OR email = %s",
            (username_or_email, username_or_email)
        )
        return cur.fetchone()


def get_password_reset_token(token_hash: str) -> Optional[Dict[str, Any]]:
    """Busca token de recuperacao pelo hash."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM password_reset_tokens WHERE token_hash = %s AND used = FALSE AND expires_at > NOW()",
            (token_hash,)
        )
        return cur.fetchone()


def mark_password_reset_token_used(token_id: int) -> bool:
    """Marca token de recuperacao como usado."""
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE password_reset_tokens SET used = TRUE WHERE id = %s",
            (token_id,)
        )
        return cur.rowcount > 0


def update_user_password(user_id: int, password_hash: str) -> bool:
    """Atualiza senha do usuario."""
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE app_users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
            (password_hash, user_id)
        )
        return cur.rowcount > 0
