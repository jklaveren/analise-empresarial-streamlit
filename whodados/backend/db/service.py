"""DB Service - WhoDados 2.0."""
from __future__ import annotations
import json
import re
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

try:
    from ..crypto_utils import encrypt_secret, decrypt_secret
except ImportError:  # fallback defensivo -- nunca deve ocorrer
    def encrypt_secret(x): return x
    def decrypt_secret(x): return x

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM app_users WHERE username = %s", (username,))
        return cur.fetchone()

def create_user_record(username: str, password_hash: str, email: Optional[str] = None, is_admin: bool = False) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO app_users (username, password_hash, email, is_admin) VALUES (%s, %s, %s, %s) RETURNING *", (username, password_hash, email, is_admin))
        return cur.fetchone()


def salvar_enriquecimento(cnpj: str, itens: List[Dict[str, Any]], coletado_por: str,
                          organizacao_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Grava os itens encontrados pelo agente de enriquecimento. Cada item
    precisa ter fonte_url -- nao gravamos nada sem proveniencia registrada."""
    salvos: List[Dict[str, Any]] = []
    with get_db_cursor() as cur:
        for item in itens:
            if not item.get("fonte_url"):
                continue
            cur.execute(
                """INSERT INTO enriquecimento_contatos
                   (cnpj, tipo_alvo, nome_alvo, campo, valor, fonte_url, fonte_titulo, coletado_por, organizacao_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (
                    cnpj,
                    item.get("tipo_alvo", "empresa"),
                    item.get("nome_alvo"),
                    item.get("campo"),
                    item.get("valor"),
                    item.get("fonte_url"),
                    item.get("fonte_titulo"),
                    coletado_por,
                    organizacao_id,
                ),
            )
            salvos.append(cur.fetchone())
    return salvos

def listar_enriquecimento(cnpj: str, organizacao_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """So retorna itens ainda nao removidos (removido_em IS NULL), e so' os da
    empresa informada -- contato levantado pela NRA nao e' da SYVP. Linhas
    antigas (organizacao_id NULL, de antes desta separacao) seguem visiveis
    pra nao sumir com o que ja' tinha sido pesquisado."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT * FROM enriquecimento_contatos
               WHERE cnpj = %s AND removido_em IS NULL
                 AND (%s::int IS NULL OR organizacao_id = %s OR organizacao_id IS NULL)
               ORDER BY coletado_em DESC""",
            (cnpj, organizacao_id, organizacao_id),
        )
        return cur.fetchall()

def remover_enriquecimento(cnpj: str, organizacao_id: Optional[int] = None) -> int:
    """Direito de exclusao (LGPD): apaga o dado pessoal coletado (valor,
    fonte) mas mantem a linha com removido_em preenchido, como registro de
    auditoria de que a remocao aconteceu -- sem guardar o dado em si."""
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE enriquecimento_contatos
               SET valor = NULL, fonte_url = NULL, fonte_titulo = NULL, removido_em = NOW()
               WHERE cnpj = %s AND removido_em IS NULL
                 AND (%s::int IS NULL OR organizacao_id = %s OR organizacao_id IS NULL)
               RETURNING id""",
            (cnpj, organizacao_id, organizacao_id),
        )
        return len(cur.fetchall())

def get_crm_by_cnpj(cnpj: str, organizacao_id: int) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM crm WHERE cnpj = %s AND organizacao_id = %s", (cnpj, organizacao_id))
        return cur.fetchone()

def get_crm_all(organizacao_id: int) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM crm WHERE organizacao_id = %s ORDER BY data_atualizacao DESC", (organizacao_id,))
        return cur.fetchall()

def create_or_update_crm(cnpj: str, organizacao_id: int, status: Optional[str] = None, notas: Optional[str] = None, criado_por: Optional[str] = None,
                         classificacao: Optional[str] = None, motivo: Optional[str] = None, parceiro: Optional[bool] = None) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO crm (cnpj, organizacao_id, status, notas, criado_por,
                               classificacao, motivo, parceiro, data_atualizacao)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
               ON CONFLICT (organizacao_id, cnpj) DO UPDATE
                   SET status = COALESCE(EXCLUDED.status, crm.status),
                       notas = COALESCE(EXCLUDED.notas, crm.notas),
                       classificacao = COALESCE(EXCLUDED.classificacao, crm.classificacao),
                       motivo = COALESCE(EXCLUDED.motivo, crm.motivo),
                       parceiro = COALESCE(EXCLUDED.parceiro, crm.parceiro, FALSE),
                       data_atualizacao = NOW()
               RETURNING *""",
            (cnpj, organizacao_id, status, notas, criado_por, classificacao, motivo, parceiro),
        )
        return cur.fetchone()


# ---------------------------------------------------------------------------
# CLASSIFICACAO DE PERFIL DA BASE (ideal / possivel / fora do perfil)
# ---------------------------------------------------------------------------
_BLACKLIST_CLASSIFICACAO = r"RECUPERACAO|FALIDA|JUDICIAL|MASSA FALIDA|EM LIQUIDACAO|BAIXADA|INAPTA"


def classificar_empresa(empresa: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica as regras de classificacao em UMA empresa (provinda de dados_empresas).
    Retorna {'classificacao': str, 'motivo': str}."""
    import re as _re
    from datetime import datetime

    razao = (empresa.get("razao_social") or "").upper()
    nome = (empresa.get("nome_fantasia") or "").upper()

    # 1) Eliminatoria: situacao juridica ruim
    situacao = f"{razao} {nome}"
    if _re.search(_BLACKLIST_CLASSIFICACAO, situacao):
        return {"classificacao": "fora_perfil", "motivo": "Situacao juridica desfavoravel (falencia/recuperacao/baixada)"}

    # 2) Eliminatoria: sem contato (sem email E sem telefone)
    email = (empresa.get("email") or "").strip()
    fone = (empresa.get("contato_fone") or "").strip()
    tem_email = bool(email)
    tem_fone = bool(_re.sub(r"\D", "", fone))
    if not tem_email and not tem_fone:
        return {"classificacao": "fora_perfil", "motivo": "Sem dados de contato (e-mail e telefone)"}

    # 3) Eliminatoria: capital social zerado ou sem dados
    capital = 0.0
    try:
        capital = float(empresa.get("capital_social") or 0)
    except (TypeError, ValueError):
        capital = 0.0
    if capital <= 0:
        return {"classificacao": "fora_perfil", "motivo": "Capital social zerado ou sem dados"}

    # 4) Idade (DATA_FUNDACAO vem YYYYMMDD como texto)
    anos = 0.0
    fundacao = (empresa.get("data_fundacao") or "").strip()
    if len(fundacao) >= 8 and fundacao.isdigit():
        try:
            d = datetime(int(fundacao[0:4]), int(fundacao[4:6]), int(fundacao[6:8]))
            anos = (datetime.utcnow() - d).days / 365.25
        except ValueError:
            anos = 0.0

    # 5) PERFIL IDEAL: 3+ anos, capital >= 100k, email E telefone
    if anos >= 3 and capital >= 100000 and tem_email and tem_fone:
        return {"classificacao": "perfil_ideal", "motivo": "Empresa ativa, 3+ anos, capital >= R$100k e contato completo"}

    # 6) PERFIL POSSIVEL: nao atingiu o ideal, mas tem pelo menos um contato
    if tem_email or tem_fone:
        return {"classificacao": "perfil_possivel", "motivo": "Perfil intermediario (faltam criterios do ideal)"}

    return {"classificacao": "fora_perfil", "motivo": "Nao atende ao perfil prospectavel"}


def classificar_base(organizacao_id: int, limite: int = None) -> Dict[str, Any]:
    """Percorre dados_empresas, aplica a classificacao em lote e grava na tabela
    crm (cria registro se ainda nao existir; atualiza classificacao/motivo).
    NAO muda status nem notas existentes. Retorna contadores."""
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "dados_empresas"):
                return {"ok": False, "erro": "Tabela de empresas ainda nao existe", "totais": {}}
            cur.execute(
                """
                SELECT
                    e."CNPJ_COMPLETO" AS cnpj_completo,
                    e."RAZAO_SOCIAL" AS razao_social,
                    e."NOME_FANTASIA" AS nome_fantasia,
                    e."DATA_FUNDACAO" AS data_fundacao,
                    COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) AS capital_social,
                    e."EMAIL" AS email,
                    e."CONTATO_FONE" AS contato_fone
                FROM dados_empresas e
                """
            )
            linhas = cur.fetchall()

        selecionadas = linhas[:limite] if limite and limite > 0 else linhas
        totais = {"perfil_ideal": 0, "perfil_possivel": 0, "fora_perfil": 0}
        for emp in selecionadas:
            r = classificar_empresa(emp)
            if isinstance(r, dict) and r.get("classificacao"):
                totais[r["classificacao"]] = totais.get(r["classificacao"], 0) + 1
                _upsert_classificacao(emp["cnpj_completo"], organizacao_id, r["classificacao"], r.get("motivo", ""))

        return {"ok": True, "processadas": len(selecionadas), "totais": totais}
    except Exception as e:
        log.warning(f"classificar_base falhou: {e}")
        return {"ok": False, "erro": str(e), "totais": {}}


def _upsert_classificacao(cnpj: str, organizacao_id: int, classificacao: str, motivo: str) -> bool:
    """INSERT ... ON CONFLICT mantendo status/notas existentes. Usado em lote."""
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """INSERT INTO crm (cnpj, organizacao_id, classificacao, motivo, data_atualizacao)
                   VALUES (%s, %s, %s, %s, NOW())
                   ON CONFLICT (organizacao_id, cnpj) DO UPDATE
                       SET classificacao = EXCLUDED.classificacao,
                           motivo = EXCLUDED.motivo,
                           data_atualizacao = NOW()""",
                (cnpj, organizacao_id, classificacao, motivo),
            )
        return True
    except Exception as e:
        log.warning(f"_upsert_classificacao falhou para {cnpj}: {e}")
        return False


def listar_crm_classificados(organizacao_id: int, filtro: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista registros do CRM com classificacao, resolvendo dados da empresa base.
    Filtro opcional: perfil_ideal / perfil_possivel / fora_perfil / parceiro / sem_classificacao."""
    permite = {"perfil_ideal", "perfil_possivel", "fora_perfil", "parceiro", "sem_classificacao"}
    try:
        with get_db_cursor() as cur:
            base_sql = f"""
                SELECT c.cnpj, c.classificacao, c.motivo, c.status, c.parceiro,
                       c.data_atualizacao, c.notas,
                       COALESCE(e."RAZAO_SOCIAL", e."NOME_FANTASIA", '') AS razao_social,
                       COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) AS capital_social,
                       COALESCE(e."EMAIL", '') AS email, ({CONTATO_FONE_SQL}) AS contato_fone,
                       COALESCE(m.nome_municipio, '') AS municipio
                FROM crm c
                LEFT JOIN dados_empresas e ON e."CNPJ_COMPLETO" = c.cnpj
                LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                WHERE c.organizacao_id = %s
            """
            params: list = [organizacao_id]
            if filtro == "sem_classificacao":
                base_sql += " AND (c.classificacao IS NULL OR c.classificacao = '')"
            elif filtro in permite:
                base_sql += " AND c.classificacao = %s"
                params.append(filtro)
            base_sql += " ORDER BY c.data_atualizacao DESC NULLS LAST LIMIT 1000"
            cur.execute(base_sql, params)
            return cur.fetchall()
    except Exception as e:
        log.warning(f"listar_crm_classificados falhou: {e}")
        return []


def estatisticas_classificacao(organizacao_id: int) -> Dict[str, Any]:
    """Contadores por classificacao (para a aba Classificacao)."""
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """SELECT classificacao, COUNT(*) AS total FROM crm
                   WHERE organizacao_id = %s AND classificacao IS NOT NULL
                   GROUP BY classificacao""",
                (organizacao_id,),
            )
            linhas = cur.fetchall()
            total_crm = 0
            cur.execute("SELECT COUNT(*) AS total FROM crm WHERE organizacao_id = %s", (organizacao_id,))
            r = cur.fetchone()
            total_crm = int(r["total"]) if r and r.get("total") else 0
        resultado = {"perfil_ideal": 0, "perfil_possivel": 0, "fora_perfil": 0, "parceiro": 0,
                     "sem_classificacao": 0, "total_crm": total_crm}
        for r in linhas:
            chave = r["classificacao"] or "sem_classificacao"
            if chave in resultado:
                resultado[chave] = int(r["total"])
        return resultado
    except Exception as e:
        log.warning(f"estatisticas_classificacao falhou: {e}")
        return {"perfil_ideal": 0, "perfil_possivel": 0, "fora_perfil": 0, "parceiro": 0,
                "sem_classificacao": 0, "total_crm": 0}

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

def create_template(nome: str, assunto: str, corpo_html: str, corpo_texto: Optional[str] = None, criado_por: Optional[str] = None, categoria_cnae: Optional[str] = "todos", organizacao_id: Optional[int] = None) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute(f"INSERT INTO email_templates (nome, assunto, corpo_html, corpo_texto, criado_por, categoria_cnae, organizacao_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {_TEMPLATE_COLS}", (nome, assunto, corpo_html, corpo_texto, criado_por, categoria_cnae or "todos", organizacao_id))
        return _com_imagem_url(cur.fetchone())

def update_template(template_id: int, nome: Optional[str] = None, assunto: Optional[str] = None, corpo_html: Optional[str] = None, corpo_texto: Optional[str] = None, categoria_cnae: Optional[str] = None, organizacao_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    org_sql = " AND organizacao_id = %s" if organizacao_id is not None else ""
    with get_db_cursor() as cur:
        fields = []
        params = []
        if nome is not None: fields.append("nome = %s"); params.append(nome)
        if assunto is not None: fields.append("assunto = %s"); params.append(assunto)
        if corpo_html is not None: fields.append("corpo_html = %s"); params.append(corpo_html)
        if corpo_texto is not None: fields.append("corpo_texto = %s"); params.append(corpo_texto)
        if categoria_cnae is not None: fields.append("categoria_cnae = %s"); params.append(categoria_cnae)
        if not fields:
            sel_params = [template_id] + ([organizacao_id] if organizacao_id is not None else [])
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE id = %s{org_sql}", sel_params)
            return _com_imagem_url(cur.fetchone())
        fields.append("updated_at = NOW()")
        params.append(template_id)
        if organizacao_id is not None:
            params.append(organizacao_id)
        sql = "UPDATE email_templates SET " + ", ".join(fields) + f" WHERE id = %s{org_sql} RETURNING {_TEMPLATE_COLS}"
        cur.execute(sql, params)
        return _com_imagem_url(cur.fetchone())

def get_template(template_id: int, organizacao_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        if organizacao_id is not None:
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE id = %s AND organizacao_id = %s", (template_id, organizacao_id))
        else:
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE id = %s", (template_id,))
        return _com_imagem_url(cur.fetchone())

def get_all_templates(organizacao_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        if organizacao_id is not None:
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE organizacao_id = %s ORDER BY created_at DESC", (organizacao_id,))
        else:
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates ORDER BY created_at DESC")
        return [_com_imagem_url(r) for r in cur.fetchall()]

def delete_template(template_id: int, organizacao_id: Optional[int] = None) -> bool:
    with get_db_cursor() as cur:
        if organizacao_id is not None:
            cur.execute("DELETE FROM email_templates WHERE id = %s AND organizacao_id = %s", (template_id, organizacao_id))
        else:
            cur.execute("DELETE FROM email_templates WHERE id = %s", (template_id,))
        return cur.rowcount > 0

def get_templates_by_categoria(categoria_cnae: str, organizacao_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retorna templates filtrados por categoria (e por empresa, se informada).
    Se categoria = 'todos', traz todos (da empresa)."""
    org_sql = " AND organizacao_id = %s" if organizacao_id is not None else ""
    with get_db_cursor() as cur:
        if categoria_cnae == "todos":
            params = [organizacao_id] if organizacao_id is not None else []
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE categoria_cnae = 'todos'{org_sql} ORDER BY created_at DESC", params)
        else:
            # Pega templates da categoria especifica + templates 'todos' (fallback)
            params = [categoria_cnae] + ([organizacao_id] if organizacao_id is not None else [])
            cur.execute(f"SELECT {_TEMPLATE_COLS} FROM email_templates WHERE categoria_cnae IN (%s, 'todos'){org_sql} ORDER BY categoria_cnae DESC, created_at DESC", params)
        return [_com_imagem_url(r) for r in cur.fetchall()]

def set_template_imagem(template_id: int, imagem_bytes: bytes, mime: str, organizacao_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Salva/substitui o card (imagem) de um template. Facilmente re-chamavel para trocar a imagem."""
    org_sql = " AND organizacao_id = %s" if organizacao_id is not None else ""
    params = [imagem_bytes, mime, template_id] + ([organizacao_id] if organizacao_id is not None else [])
    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE email_templates SET imagem_data = %s, imagem_mime = %s, tem_imagem = TRUE, updated_at = NOW() WHERE id = %s{org_sql} RETURNING {_TEMPLATE_COLS}",
            params,
        )
        return _com_imagem_url(cur.fetchone())

def get_template_imagem(template_id: int) -> Optional[Dict[str, Any]]:
    """Le os bytes crus da imagem -- usado apenas pelo endpoint publico que serve a imagem."""
    with get_db_cursor() as cur:
        cur.execute("SELECT imagem_data, imagem_mime FROM email_templates WHERE id = %s AND tem_imagem = TRUE", (template_id,))
        return cur.fetchone()

def clear_template_imagem(template_id: int, organizacao_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    org_sql = " AND organizacao_id = %s" if organizacao_id is not None else ""
    params = [template_id] + ([organizacao_id] if organizacao_id is not None else [])
    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE email_templates SET imagem_data = NULL, imagem_mime = NULL, tem_imagem = FALSE, updated_at = NOW() WHERE id = %s{org_sql} RETURNING {_TEMPLATE_COLS}",
            params,
        )
        return _com_imagem_url(cur.fetchone())
def create_campanha(
    nome: str, template_id: Optional[int], filtros: Dict, created_by: Optional[str] = None,
    eh_sequencia: bool = False, agendada_para: Optional[str] = None, organizacao_id: Optional[int] = None,
    canal: str = "email", mensagem: Optional[str] = None, tamanho_lote: Optional[int] = None,
    repetir_ate: Optional[str] = None,
) -> Dict[str, Any]:
    status = "agendada" if agendada_para else "rascunho"
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO campanhas
               (nome, template_id, filtros, status, created_by, eh_sequencia, agendada_para, organizacao_id, canal, mensagem, tamanho_lote, repetir_ate)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (nome, template_id, json.dumps(filtros or {}), status, created_by, eh_sequencia, agendada_para,
             organizacao_id, canal, mensagem, tamanho_lote, repetir_ate),
        )
        row = cur.fetchone()
        if row and row.get("filtros") and isinstance(row["filtros"], str):
            try: row["filtros"] = json.loads(row["filtros"])
            except: pass
        return row

def get_campanha(campanha_id: int, organizacao_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        if organizacao_id is not None:
            cur.execute("SELECT * FROM campanhas WHERE id = %s AND organizacao_id = %s", (campanha_id, organizacao_id))
        else:
            cur.execute("SELECT * FROM campanhas WHERE id = %s", (campanha_id,))
        row = cur.fetchone()
        if row and row.get("filtros") and isinstance(row["filtros"], str):
            try: row["filtros"] = json.loads(row["filtros"])
            except: pass
        return row

def get_all_campanhas(organizacao_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        if organizacao_id is not None:
            cur.execute("SELECT * FROM campanhas WHERE organizacao_id = %s ORDER BY created_at DESC", (organizacao_id,))
        else:
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
    # A empresa (organizacao_id) e' herdada da campanha via subquery, entao o
    # motor de envio (mailer) nao precisa saber a empresa -- fica sempre
    # consistente com a campanha a que o email pertence.
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO emails_enviados
                 (campaign_id, cnpj, email_destino, assunto, sequencia_passo, organizacao_id)
               VALUES (%s, %s, %s, %s, %s, (SELECT organizacao_id FROM campanhas WHERE id = %s))
               RETURNING *""",
            (campaign_id, cnpj, email_destino, assunto, sequencia_passo, campaign_id),
        )
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
def create_notificacao(tipo: str, titulo: str, mensagem: Optional[str] = None, cnpj: Optional[str] = None, user_id: Optional[str] = None, organizacao_id: Optional[int] = None) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO notificacoes (tipo, titulo, mensagem, cnpj, user_id, organizacao_id) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *", (tipo, titulo, mensagem, cnpj, user_id, organizacao_id))
        return cur.fetchone()

def get_notificacoes(user_id: Optional[str] = None, lidas: Optional[bool] = None, limit: int = 100, organizacao_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        # o nome da empresa vem junto: ver "Nova tarefa X" sem saber em qual
        # empresa ela caiu foi exatamente o que escondeu um registro criado
        # na empresa errada.
        sql = ("SELECT n.*, o.nome AS organizacao_nome FROM notificacoes n "
               "LEFT JOIN organizacoes o ON o.id = n.organizacao_id WHERE 1=1")
        params = []
        if organizacao_id is not None:
            sql += " AND n.organizacao_id = %s"
            params.append(organizacao_id)
        if user_id:
            sql += " AND (n.user_id = %s OR n.user_id IS NULL)"
            params.append(user_id)
        if lidas is not None:
            sql += " AND n.lida = %s"
            params.append(lidas)
        sql += " ORDER BY n.created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        return cur.fetchall()

def contar_notificacoes_nao_lidas(user_id: Optional[str] = None, organizacao_id: Optional[int] = None) -> int:
    """So' o numero, pro badge do menu -- puxar a lista inteira a cada
    poucos segundos so' pra contar sairia caro."""
    sql = "SELECT COUNT(*)::int AS n FROM notificacoes WHERE lida = FALSE"
    params: List[Any] = []
    if organizacao_id is not None:
        sql += " AND organizacao_id = %s"
        params.append(organizacao_id)
    if user_id:
        sql += " AND (user_id = %s OR user_id IS NULL)"
        params.append(user_id)
    with get_db_cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row["n"] if row else 0


def mark_notificacao_lida(notificacao_id: int, user_id: Optional[str] = None,
                          organizacao_id: Optional[int] = None) -> bool:
    """Marca como lida. Filtra por usuario e empresa: antes bastava o id pra
    marcar lida a notificacao de outra pessoa (ou de outra empresa)."""
    sql = "UPDATE notificacoes SET lida = TRUE WHERE id = %s"
    params: List[Any] = [notificacao_id]
    if organizacao_id is not None:
        sql += " AND organizacao_id = %s"
        params.append(organizacao_id)
    if user_id:
        sql += " AND (user_id = %s OR user_id IS NULL)"
        params.append(user_id)
    with get_db_cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount > 0


# ==================== MONITOR DE EMAILS (FOLLOW-UP) ====================

def get_emails_for_monitor(
    campaign_id=None,
    dias_sla: int = 7,
    sla_verde_dias: Optional[int] = None,
    sla_amarelo_dias: Optional[int] = None,
    limit: int = 200,
    offset: int = 0,
    organizacao_id: Optional[int] = None,
):
    """
    Retorna e-mails enviados com cálculo de status de semáforo para follow-up.

    Status do semáforo (prazos configuraveis via app_config -- ver
    get_sla_config/set_sla_config -- padrao 2/5 dias se nunca configurado):
      - verde:    aberto_em IS NOT NULL (há resposta/interação)
                  OU dentro do prazo "verde"
      - amarelo:  passou do prazo "verde" mas ainda dentro do "amarelo",
                  sem aberto_em (atenção)
      - vermelho: passou do prazo "amarelo", sem aberto_em (follow-up urgente)
      - cinza:    status != 'enviado' (pendente, erro, etc.)
    """
    if sla_verde_dias is None or sla_amarelo_dias is None:
        sla = get_sla_config()
        sla_verde_dias = sla_verde_dias if sla_verde_dias is not None else sla["sla_verde_dias"]
        sla_amarelo_dias = sla_amarelo_dias if sla_amarelo_dias is not None else sla["sla_amarelo_dias"]

    with get_db_cursor() as cur:
        params: List[Any] = [sla_verde_dias, sla_amarelo_dias]
        where_org = "AND e.organizacao_id = %s" if organizacao_id is not None else ""
        where_campaign = ""
        if campaign_id:
            where_campaign = "AND e.campaign_id = %s"

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
                    WHEN GREATEST(EXTRACT(EPOCH FROM (NOW() - e.enviado_em)) / 86400.0, 0) <= %s THEN 'verde'
                    WHEN GREATEST(EXTRACT(EPOCH FROM (NOW() - e.enviado_em)) / 86400.0, 0) <= %s THEN 'amarelo'
                    ELSE 'vermelho'
                END as semaforo_status,
                emp.razao_social,
                emp.nome_fantasia
            FROM emails_enviados e
            LEFT JOIN campanhas c ON c.id = e.campaign_id
            LEFT JOIN dados_empresas emp ON emp.cnpj_completo = e.cnpj
            WHERE e.enviado_em IS NOT NULL
            {where_org}
            {where_campaign}
            ORDER BY e.enviado_em DESC
            LIMIT %s OFFSET %s
        """
        if organizacao_id is not None:
            params.append(organizacao_id)
        if campaign_id:
            params.append(campaign_id)
        params.extend([limit, offset])
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows


def get_monitor_stats(dias_sla: int = 7, sla_verde_dias: Optional[int] = None, sla_amarelo_dias: Optional[int] = None, organizacao_id: Optional[int] = None):
    """Retorna estatísticas agregadas para o dashboard de monitoramento.
    Prazos configuraveis -- ver get_sla_config/set_sla_config."""
    if sla_verde_dias is None or sla_amarelo_dias is None:
        sla = get_sla_config()
        sla_verde_dias = sla_verde_dias if sla_verde_dias is not None else sla["sla_verde_dias"]
        sla_amarelo_dias = sla_amarelo_dias if sla_amarelo_dias is not None else sla["sla_amarelo_dias"]

    where_org = "WHERE organizacao_id = %(org)s" if organizacao_id is not None else ""
    with get_db_cursor() as cur:
        sql = f"""
            SELECT
                COUNT(*) FILTER (WHERE status = 'enviado') as total_enviados,
                COUNT(*) FILTER (
                    WHERE (aberto_em IS NOT NULL)
                       OR (enviado_em IS NOT NULL AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 <= %(verde)s)
                ) as verde,
                COUNT(*) FILTER (
                    WHERE enviado_em IS NOT NULL
                      AND aberto_em IS NULL
                      AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 > %(verde)s
                      AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 <= %(amarelo)s
                ) as amarelo,
                COUNT(*) FILTER (
                    WHERE enviado_em IS NOT NULL
                      AND aberto_em IS NULL
                      AND EXTRACT(EPOCH FROM (NOW() - enviado_em)) / 86400.0 > %(amarelo)s
                ) as vermelho,
                COUNT(*) FILTER (WHERE status != 'enviado') as cinza
            FROM emails_enviados
            {where_org}
        """
        cur.execute(sql, {"verde": sla_verde_dias, "amarelo": sla_amarelo_dias, "org": organizacao_id})
        row = cur.fetchone()
        return dict(row) if row else {"total_enviados": 0, "verde": 0, "amarelo": 0, "vermelho": 0, "cinza": 0}


def get_emails_vermelhos_para_followup(limite: int = 50, organizacao_id: Optional[int] = None):
    """Retorna os e-mails mais críticos (vermelho) para disparo de follow-up."""
    where_org = "AND e.organizacao_id = %s" if organizacao_id is not None else ""
    params = ([organizacao_id] if organizacao_id is not None else []) + [limite]
    with get_db_cursor() as cur:
        sql = f"""
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
              {where_org}
            ORDER BY e.enviado_em ASC
            LIMIT %s
        """
        cur.execute(sql, params)
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


# ==================== EMPRESAS (DADOS DA RECEITA FEDERAL) ====================
# As tabelas dados_empresas / dados_socios / municipios sao populadas pelo
# pipeline de ETL (whodados/pipeline/pipeline.py + scripts/sync_data_to_db.py,
# rodado pelo GitHub Action .github/workflows/whodados-etl.yml). Enquanto o
# pipeline nao tiver rodado ainda, essas tabelas nao existem -- as funcoes
# abaixo detectam isso e retornam vazio/zero em vez de lancar erro, para o
# resto da aplicacao nunca quebrar por falta desses dados.


# Expressoes SQL que derivam PORTE_NOME e CONTATO_FONE on-the-fly (as duas
# colunas foram removidas da tabela: eram redundantes -- PORTE_NOME e um
# mapeamento fixo do PORTE_EMPRESA, e CONTATO_FONE e so DDD + TELEFONE
# concatenado. Manter derivado economiza ~30MB no Postgres e preserva a
# API que o frontend consome (porte_nome e contato_fone continuam saindo
# nos SELECTs, so mudou como sao produzidos).
PORTE_NOME_SQL = (
    "CASE e.\"PORTE_EMPRESA\" "
    "WHEN '01' THEN 'NAO INFORMADO' "
    "WHEN '02' THEN 'ME' "
    "WHEN '03' THEN 'EPP' "
    "WHEN '05' THEN 'MEDIO E GRANDE' "
    "ELSE 'DEMAIS' END"
)
CONTATO_FONE_SQL = (
    "'(' || COALESCE(e.\"DDD\", '') || ') ' || COALESCE(e.\"TELEFONE\", '')"
)
# Mapeamento inverso pra converter filtros do frontend (que ainda mandam
# 'ME', 'EPP', ...) em codigos PORTE_EMPRESA no WHERE.
PORTE_NOME_TO_CODE = {
    "NAO INFORMADO": "01",
    "ME": "02",
    "EPP": "03",
    "MEDIO E GRANDE": "05",
}

# Score de potencial (0-100), calculado on-the-fly a partir de sinais que ja
# existem em dados_empresas -- sem coluna nova, sem reprocessar o ETL.
# Pesos: porte (35) + capital social (25) + saude financeira/divida (20)
# + maturidade (10) + contactabilidade (10). MEI zera o componente de porte
# porque o cadastro de porte da RF costuma vir "NAO INFORMADO" pra MEI mesmo
# quando o negocio e' relevante -- sem essa checagem MEI empataria com
# "NAO INFORMADO" indevidamente.
POTENCIAL_SCORE_SQL = """(
    (CASE WHEN e."OPCAO_MEI" = 'S' THEN 5 ELSE
        CASE e."PORTE_EMPRESA"
            WHEN '05' THEN 35
            WHEN '03' THEN 25
            WHEN '02' THEN 12
            ELSE 8
        END
    END)
    + (CASE
        WHEN COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) >= 1000000 THEN 25
        WHEN COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) >= 100000 THEN 18
        WHEN COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) >= 10000 THEN 10
        WHEN COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) > 0 THEN 4
        ELSE 0
      END)
    + (CASE
        WHEN COALESCE(NULLIF(e."DIVIDA_TOTAL"::text, '')::numeric, 0) = 0 THEN 20
        WHEN COALESCE(NULLIF(e."DIVIDA_TOTAL"::text, '')::numeric, 0) < 50000 THEN 10
        ELSE 0
      END)
    + (CASE
        WHEN e."DATA_FUNDACAO" IS NULL THEN 4
        WHEN e."DATA_FUNDACAO" <= (NOW() - INTERVAL '5 years')::date THEN 10
        WHEN e."DATA_FUNDACAO" <= (NOW() - INTERVAL '1 year')::date THEN 6
        ELSE 2
      END)
    + (CASE WHEN TRIM(COALESCE(e."EMAIL", '')) <> '' THEN 6 ELSE 0 END)
    + (CASE WHEN TRIM(COALESCE(e."TELEFONE", '')) <> '' THEN 4 ELSE 0 END)
)"""
POTENCIAL_TIER_SQL = f"""(CASE
    WHEN {POTENCIAL_SCORE_SQL} >= 65 THEN 'alto'
    WHEN {POTENCIAL_SCORE_SQL} >= 40 THEN 'medio'
    ELSE 'baixo'
END)"""


# Mesma classificacao de classifier/cnae.py::classificar_cnae, em SQL --
# indexada, pra filtrar por setor sem precisar comparar contra uma lista
# de centenas de codigos CNAE (uma igualdade contra coluna indexada bate
# muito mais rapido que "CNAE_PRINCIPAL = ANY(<231 codigos>)").
CATEGORIA_CNAE_SQL = """(CASE
    WHEN LEFT(e."CNAE_PRINCIPAL", 2) ~ '^\\d+$' AND LEFT(e."CNAE_PRINCIPAL", 2)::int BETWEEN 10 AND 33 THEN 'industria'
    WHEN LEFT(e."CNAE_PRINCIPAL", 2) ~ '^\\d+$' AND LEFT(e."CNAE_PRINCIPAL", 2)::int BETWEEN 35 AND 43 THEN 'industria'
    WHEN LEFT(e."CNAE_PRINCIPAL", 2) ~ '^\\d+$' AND LEFT(e."CNAE_PRINCIPAL", 2)::int BETWEEN 45 AND 47 THEN 'comercio'
    WHEN LEFT(e."CNAE_PRINCIPAL", 2) ~ '^\\d+$' AND LEFT(e."CNAE_PRINCIPAL", 2)::int BETWEEN 58 AND 63 THEN 'tecnologia'
    ELSE 'servicos'
END)"""


def atualizar_potencial_empresas() -> int:
    """Repopula empresas_potencial inteira a partir de dados_empresas.
    Rodar depois de toda carga do ETL (a carga substitui dados_empresas do
    zero -- to_sql replace -- entao qualquer coisa pre-calculada precisa
    ser refeita junto). Uma unica passada em lote, bem mais barato que
    recalcular a formula a cada consulta."""
    with get_db_cursor() as cur:
        cur.execute("TRUNCATE empresas_potencial")
        cur.execute(f"""
            INSERT INTO empresas_potencial (cnpj_completo, potencial_score, potencial_tier, categoria_cnae)
            SELECT e."CNPJ_COMPLETO", ({POTENCIAL_SCORE_SQL}), ({POTENCIAL_TIER_SQL}), ({CATEGORIA_CNAE_SQL})
            FROM dados_empresas e
            WHERE e."CNPJ_COMPLETO" IS NOT NULL
        """)
        return cur.rowcount

# ==================== CONFIGURACOES DA APLICACAO (app_config) ====================

_SLA_PADRAO = {"sla_verde_dias": 2, "sla_amarelo_dias": 5}


def get_app_config() -> Dict[str, str]:
    """Le todos os pares chave-valor de app_config. Retorna vazio (sem
    quebrar) se a tabela ainda nao existir."""
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "app_config"):
                return {}
            cur.execute("SELECT chave, valor FROM app_config")
            return {r["chave"]: r["valor"] for r in cur.fetchall()}
    except Exception as e:
        log.warning(f"get_app_config falhou, retornando vazio: {e}")
        return {}


def set_app_config(chave: str, valor: str) -> None:
    with get_db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_config (chave, valor, atualizado_em)
            VALUES (%s, %s, NOW())
            ON CONFLICT (chave) DO UPDATE
                SET valor = EXCLUDED.valor, atualizado_em = NOW()
            """,
            (chave, valor),
        )


def get_sla_config() -> Dict[str, int]:
    """Prazos (em dias) que definem o semaforo do Monitor de e-mails.
    Le de app_config; usa os padroes (2/5 dias) se nao estiver configurado
    ou se os valores gravados forem invalidos."""
    cfg = get_app_config()
    resultado = dict(_SLA_PADRAO)
    for chave, padrao in _SLA_PADRAO.items():
        valor = cfg.get(chave)
        if valor is not None:
            try:
                resultado[chave] = int(valor)
            except (TypeError, ValueError):
                pass
    return resultado


def set_sla_config(sla_verde_dias: int, sla_amarelo_dias: int) -> None:
    """Grava os prazos do semaforo. Validacao basica: verde tem que ser
    menor que amarelo, os dois positivos -- senao o semaforo fica sem
    sentido (ex: tudo cai direto em vermelho)."""
    if sla_verde_dias < 1 or sla_amarelo_dias < 1:
        raise ValueError("Os prazos precisam ser maiores que zero")
    if sla_verde_dias >= sla_amarelo_dias:
        raise ValueError("O prazo 'verde' precisa ser menor que o prazo 'amarelo'")
    set_app_config("sla_verde_dias", str(sla_verde_dias))
    set_app_config("sla_amarelo_dias", str(sla_amarelo_dias))


# ==================== GESTAO DE USUARIOS ====================

def list_all_users() -> List[Dict[str, Any]]:
    """Lista todos os usuarios do sistema (sem o hash de senha)."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, username, email, is_admin, is_active, created_at "
            "FROM app_users ORDER BY created_at ASC"
        )
        return cur.fetchall()


def update_user_flags(user_id: int, is_admin: Optional[bool] = None, is_active: Optional[bool] = None) -> bool:
    """Atualiza is_admin e/ou is_active de um usuario. So altera os campos
    passados (None = nao muda)."""
    campos = []
    valores: List[Any] = []
    if is_admin is not None:
        campos.append("is_admin = %s")
        valores.append(is_admin)
    if is_active is not None:
        campos.append("is_active = %s")
        valores.append(is_active)
    if not campos:
        return False
    campos.append("updated_at = NOW()")
    valores.append(user_id)
    with get_db_cursor() as cur:
        cur.execute(f"UPDATE app_users SET {', '.join(campos)} WHERE id = %s", valores)
        return cur.rowcount > 0


# ==================== MULTI-EMPRESA (ORGANIZACOES) ====================
# Ver plano/memoria: whodados-multiempresa-nra-syvp. Base de leads e
# compartilhada; o CONTROLE (crm, campanhas, templates, monitor, notificacoes,
# remetente) e isolado por organizacao. O acesso e por usuario.

def listar_organizacoes_do_usuario(username: str) -> List[Dict[str, Any]]:
    """Empresas que o usuario pode operar (para o seletor de empresa ativa),
    com o papel dele em cada uma (admin/membro/visitante)."""
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT o.id, o.nome, o.slug, o.ativo, COALESCE(o.escopo_base, 'receita') AS escopo_base, uo.papel
            FROM organizacoes o
            JOIN usuario_organizacoes uo ON uo.organizacao_id = o.id
            JOIN app_users u ON u.id = uo.user_id
            WHERE u.username = %s AND o.ativo = TRUE
            ORDER BY o.id
            """,
            (username,),
        )
        return cur.fetchall()


def get_papel_usuario_org(username: str, organizacao_id: int) -> Optional[str]:
    """Papel do usuario NESSA organizacao (admin/membro/visitante), ou None
    se ele nao tiver vinculo com ela."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT uo.papel FROM usuario_organizacoes uo
               JOIN app_users u ON u.id = uo.user_id
               WHERE u.username = %s AND uo.organizacao_id = %s""",
            (username, organizacao_id),
        )
        row = cur.fetchone()
        return row["papel"] if row else None


def definir_papel_usuario_org(user_id: int, organizacao_id: int, papel: str) -> bool:
    """Muda o papel de um usuario numa empresa onde ele ja tem acesso.
    Nao cria o vinculo -- so' atualiza um que ja existe (use
    definir_acesso_usuario_orgs pra dar acesso primeiro)."""
    if papel not in ("admin", "membro", "visitante"):
        return False
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE usuario_organizacoes SET papel = %s WHERE user_id = %s AND organizacao_id = %s",
            (papel, user_id, organizacao_id),
        )
        return cur.rowcount > 0


def usuario_tem_acesso_org(username: str, organizacao_id: int) -> bool:
    """True se o usuario esta vinculado aquela empresa."""
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM usuario_organizacoes uo
            JOIN app_users u ON u.id = uo.user_id
            WHERE u.username = %s AND uo.organizacao_id = %s
            """,
            (username, organizacao_id),
        )
        return cur.fetchone() is not None


def criar_organizacao(nome: str, slug: Optional[str] = None) -> Dict[str, Any]:
    """Cria uma empresa (organizacao). Slug e' derivado do nome quando nao
    informado -- e' o identificador estavel, o nome pode mudar depois."""
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome e' obrigatorio")
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")[:60] or "empresa"
    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO organizacoes (nome, slug) VALUES (%s, %s) "
            "ON CONFLICT (slug) DO NOTHING RETURNING id, nome, slug, ativo",
            (nome, slug),
        )
        row = cur.fetchone()
        if row:
            return row
        cur.execute("SELECT id, nome, slug, ativo FROM organizacoes WHERE slug = %s", (slug,))
        return cur.fetchone()


def renomear_organizacao(organizacao_id: int, nome: str) -> bool:
    """Muda so' o nome exibido. O slug continua o mesmo de proposito: e' o
    que amarra os dados (CRM, campanhas) a empresa."""
    nome = (nome or "").strip()
    if not nome:
        return False
    with get_db_cursor() as cur:
        cur.execute("UPDATE organizacoes SET nome = %s WHERE id = %s", (nome, organizacao_id))
        return cur.rowcount > 0


def listar_todas_organizacoes() -> List[Dict[str, Any]]:
    """Todas as empresas (uso administrativo)."""
    with get_db_cursor() as cur:
        cur.execute("SELECT id, nome, slug, ativo FROM organizacoes ORDER BY id")
        return cur.fetchall()


def definir_acesso_usuario_orgs(user_id: int, organizacao_ids: List[int]) -> None:
    """Define exatamente a quais empresas um usuario tem acesso (substitui as
    anteriores). Lista vazia = sem acesso a nenhuma."""
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM usuario_organizacoes WHERE user_id = %s", (user_id,))
        for org_id in organizacao_ids or []:
            cur.execute(
                "INSERT INTO usuario_organizacoes (user_id, organizacao_id) "
                "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, org_id),
            )


def get_orgs_do_user_id(user_id: int) -> List[int]:
    """IDs das empresas de um usuario (por id) -- usado ao listar usuarios."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT organizacao_id FROM usuario_organizacoes WHERE user_id = %s ORDER BY organizacao_id",
            (user_id,),
        )
        return [r["organizacao_id"] for r in cur.fetchall()]


# ---- Config de e-mail (SMTP + assinatura) por empresa ----

def get_org_smtp_config(organizacao_id: int, incluir_password: bool = False) -> Optional[Dict[str, Any]]:
    """Config de e-mail da empresa. Por padrao NAO retorna a senha (write-only);
    o mailer chama com incluir_password=True para poder enviar. Retorna None se
    a empresa nao tiver config."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM org_smtp_config WHERE organizacao_id = %s", (organizacao_id,))
        row = cur.fetchone()
    if not row:
        return None
    dados = dict(row)
    dados["configurado"] = bool(dados.get("smtp_host") and dados.get("smtp_username"))
    dados["tem_logo"] = bool(dados.get("logo_data"))
    dados.pop("logo_data", None)  # bytes crus nunca vao no JSON
    if incluir_password:
        dados["smtp_password"] = decrypt_secret(dados.get("smtp_password"))
    else:
        dados.pop("smtp_password", None)
    return dados


def get_usuario_smtp_config(username: str, organizacao_id: int,
                            incluir_password: bool = False) -> Optional[Dict[str, Any]]:
    """Config de e-mail INDIVIDUAL do usuario nesta empresa. Campo nao
    preenchido volta None de proposito -- quem resolve a mistura com a
    config da empresa e' o mailer."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT c.* FROM usuario_smtp_config c
               JOIN app_users u ON u.id = c.user_id
               WHERE u.username = %s AND c.organizacao_id = %s""",
            (username, organizacao_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    dados = dict(row)
    if incluir_password:
        dados["smtp_password"] = decrypt_secret(dados.get("smtp_password"))
    else:
        dados.pop("smtp_password", None)
    dados["configurado"] = bool(dados.get("email_from") or dados.get("smtp_host"))
    return dados


def set_usuario_smtp_config(username: str, organizacao_id: int, **campos) -> Optional[Dict[str, Any]]:
    """Cria/atualiza o e-mail individual. So altera o que foi passado
    (None = mantem). Senha vazia nao sobrescreve a que ja' existe."""
    permitidos = ("smtp_host", "smtp_port", "smtp_username", "smtp_use_tls",
                  "email_from", "email_from_name", "assinatura_html")
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM app_users WHERE username = %s", (username,))
        user = cur.fetchone()
        if not user:
            return None
        cur.execute(
            """INSERT INTO usuario_smtp_config (user_id, organizacao_id) VALUES (%s, %s)
               ON CONFLICT (user_id, organizacao_id) DO NOTHING""",
            (user["id"], organizacao_id),
        )
        sets, valores = [], []
        for col in permitidos:
            if campos.get(col) is not None:
                sets.append(f"{col} = %s")
                valores.append(campos[col])
        senha = campos.get("smtp_password")
        if senha:
            sets.append("smtp_password = %s")
            valores.append(encrypt_secret(senha))
        if not sets:
            return get_usuario_smtp_config(username, organizacao_id)
        sets.append("updated_at = NOW()")
        valores += [user["id"], organizacao_id]
        cur.execute(
            f"UPDATE usuario_smtp_config SET {', '.join(sets)} WHERE user_id = %s AND organizacao_id = %s",
            valores,
        )
    return get_usuario_smtp_config(username, organizacao_id)


def set_org_smtp_config(organizacao_id: int, smtp_host=None, smtp_port=None, smtp_username=None,
                        smtp_password=None, smtp_use_tls=None, email_from=None,
                        email_from_name=None, assinatura_html=None) -> Dict[str, Any]:
    """Cria/atualiza a config de e-mail da empresa. So altera os campos passados
    (None = mantem). Senha vazia/None nao sobrescreve a existente."""
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO org_smtp_config (organizacao_id) VALUES (%s) ON CONFLICT (organizacao_id) DO NOTHING", (organizacao_id,))
        campos, valores = [], []
        for col, val in [
            ("smtp_host", smtp_host), ("smtp_port", smtp_port), ("smtp_username", smtp_username),
            ("smtp_use_tls", smtp_use_tls), ("email_from", email_from),
            ("email_from_name", email_from_name), ("assinatura_html", assinatura_html),
        ]:
            if val is not None:
                campos.append(f"{col} = %s"); valores.append(val)
        if smtp_password:  # so troca a senha se veio uma nova nao-vazia (cifrada em repouso)
            campos.append("smtp_password = %s"); valores.append(encrypt_secret(smtp_password))
        if campos:
            campos.append("updated_at = NOW()")
            valores.append(organizacao_id)
            cur.execute(f"UPDATE org_smtp_config SET {', '.join(campos)} WHERE organizacao_id = %s", valores)
    return get_org_smtp_config(organizacao_id)


def set_org_logo(organizacao_id: int, logo_bytes: bytes, mime: str) -> None:
    with get_db_cursor() as cur:
        cur.execute("INSERT INTO org_smtp_config (organizacao_id) VALUES (%s) ON CONFLICT (organizacao_id) DO NOTHING", (organizacao_id,))
        cur.execute("UPDATE org_smtp_config SET logo_data = %s, logo_mime = %s, updated_at = NOW() WHERE organizacao_id = %s", (logo_bytes, mime, organizacao_id))


def get_org_logo(organizacao_id: int) -> Optional[Dict[str, Any]]:
    """Bytes crus do logo -- usado pelo endpoint publico que serve o logo no e-mail."""
    with get_db_cursor() as cur:
        cur.execute("SELECT logo_data, logo_mime FROM org_smtp_config WHERE organizacao_id = %s", (organizacao_id,))
        return cur.fetchone()


def delete_user(user_id: int) -> bool:
    """Exclui um usuario. Os vinculos usuario_organizacoes caem por CASCADE."""
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM app_users WHERE id = %s", (user_id,))
        return cur.rowcount > 0


def update_user_email(user_id: int, email: Optional[str]) -> bool:
    """Atualiza o e-mail de um usuario (None/vazio limpa)."""
    with get_db_cursor() as cur:
        cur.execute("UPDATE app_users SET email = %s, updated_at = NOW() WHERE id = %s", (email or None, user_id))
        return cur.rowcount > 0


def _tabela_existe(cur, nome_tabela: str) -> bool:
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s) AS existe",
        (nome_tabela,),
    )
    row = cur.fetchone()
    return bool(row and row.get("existe"))


# Regex (case-insensitive) das situacoes "problematicas" -- mesmo criterio do
# Legado (toggle "Permitir Falencia / Rec. Judicial"). Quando incluir_inativas
# e False, essas empresas sao excluidas.
_BLACKLIST_REGEX = r"RECUPERACAO|FALIDA|JUDICIAL|MASSA FALIDA|EM LIQUIDACAO|BAIXADA|INAPTA"


def _norm_lista(v) -> List[str]:
    """Aceita None, str ou lista -> lista de strings nao-vazias (o endpoint manda
    lista para multiselect; campanhas antigas podem mandar uma string)."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    return [str(x) for x in v if x is not None and str(x) != ""]


def _where_empresas(
    cidade=None, cnae=None, porte=None, busca=None,
    divida_min=None, divida_max=None, capital_min=None, capital_max=None,
    fundacao_de=None, fundacao_ate=None, incluir_inativas: bool = True,
    contato=None, potencial=None, categoria=None,
):
    """Monta o WHERE (e os params) compartilhado pela listagem e pela contagem,
    a partir dos filtros do funil (cidade, CNAE, porte, faixas de passivo/capital,
    data de fundacao, blacklist RJ). Assume os aliases e (dados_empresas) e m
    (municipios) na query."""
    import re as _re
    clauses: List[str] = []
    params: List[Any] = []
    cidades = _norm_lista(cidade)
    if cidades:
        clauses.append("m.nome_municipio = ANY(%s)"); params.append(cidades)
    cnaes = _norm_lista(cnae)
    if cnaes:
        clauses.append('e."CNAE_PRINCIPAL" = ANY(%s)'); params.append(cnaes)
    portes = _norm_lista(porte)
    if portes:
        # Frontend manda nomes ("ME", "EPP", ...) mas a tabela guarda so o
        # codigo ("02", "03", ...). Traduz de volta antes do bind.
        codigos = [PORTE_NOME_TO_CODE[p] for p in portes if p in PORTE_NOME_TO_CODE]
        if codigos:
            clauses.append('e."PORTE_EMPRESA" = ANY(%s)'); params.append(codigos)
    if busca:
        clauses.append('(e."RAZAO_SOCIAL" ILIKE %s OR e."NOME_FANTASIA" ILIKE %s)')
        params.extend([f"%{busca}%", f"%{busca}%"])
    if divida_min is not None:
        clauses.append('COALESCE(NULLIF(e."DIVIDA_TOTAL"::text, \'\')::numeric, 0) >= %s'); params.append(divida_min)
    if divida_max is not None:
        clauses.append('COALESCE(NULLIF(e."DIVIDA_TOTAL"::text, \'\')::numeric, 0) <= %s'); params.append(divida_max)
    if capital_min is not None:
        clauses.append('COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, \'\')::numeric, 0) >= %s'); params.append(capital_min)
    if capital_max is not None:
        clauses.append('COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, \'\')::numeric, 0) <= %s'); params.append(capital_max)
    # DATA_FUNDACAO vem como texto YYYYMMDD -> comparacao lexicografica = cronologica.
    if fundacao_de:
        clauses.append('e."DATA_FUNDACAO" >= %s'); params.append(_re.sub(r"\D", "", str(fundacao_de)))
    if fundacao_ate:
        clauses.append('e."DATA_FUNDACAO" <= %s'); params.append(_re.sub(r"\D", "", str(fundacao_ate)))
    if not incluir_inativas:
        clauses.append('COALESCE(e."RAZAO_SOCIAL", \'\') !~* %s'); params.append(_BLACKLIST_REGEX)
    # Filtro de contato: com_email / so_telefone (sem e-mail, com fone) / sem_contato.
    if contato:
        tem_email = 'TRIM(COALESCE(e."EMAIL", \'\')) <> \'\''
        tem_fone = 'TRIM(COALESCE(e."TELEFONE", \'\')) <> \'\''
        if contato == "com_email":
            clauses.append(tem_email)
        elif contato == "so_telefone":
            clauses.append(f"(NOT ({tem_email}) AND {tem_fone})")
        elif contato == "sem_contato":
            clauses.append(f"(NOT ({tem_email}) AND NOT ({tem_fone}))")
    tiers = _norm_lista(potencial)
    if tiers:
        clauses.append("ep.potencial_tier = ANY(%s)"); params.append(tiers)
    categorias = _norm_lista(categoria)
    if categorias:
        clauses.append("ep.categoria_cnae = ANY(%s)"); params.append(categorias)
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    return where, params


# ==================== CARTEIRA PROPRIA DA EMPRESA ====================
#
# Empresa com escopo_base='carteira' (ex.: JehJuh) prospecta sobre a lista
# dela, nao sobre a base da Receita. As telas sao as mesmas -- Empresas,
# Clientes, Campanhas: o que muda e' de onde as linhas vem. As funcoes abaixo
# devolvem exatamente as mesmas colunas de listar_empresas_db pra tela nao
# precisar saber qual das duas fontes respondeu.

_CARTEIRA_SELECT = """
    c.cnpj_completo,
    COALESCE(c.razao_social, '') AS razao_social,
    COALESCE(c.nome_fantasia, '') AS nome_fantasia,
    COALESCE(c.municipio, '') AS municipio,
    COALESCE(c.cnae_principal, '') AS cnae_principal,
    COALESCE(c.cnae_descricao, '') AS cnae_descricao,
    COALESCE(c.capital_social, 0) AS capital_social,
    COALESCE(c.divida_total, 0) AS divida_total,
    COALESCE(c.porte_nome, '') AS porte_nome,
    NULL::date AS data_fundacao,
    COALESCE(c.email, '') AS email,
    COALESCE(c.contato_fone, '') AS contato_fone,
    COALESCE(c.categoria, 'sem categoria') AS categoria_cnae,
    0 AS potencial_score,
    'medio' AS potencial_tier
"""


def org_escopo_base(organizacao_id: Optional[int]) -> str:
    """'receita' (base publica) ou 'carteira' (lista propria da empresa)."""
    if organizacao_id is None:
        return "receita"
    with get_db_cursor() as cur:
        cur.execute("SELECT COALESCE(escopo_base, 'receita') AS e FROM organizacoes WHERE id = %s", (organizacao_id,))
        row = cur.fetchone()
        return row["e"] if row else "receita"


def _where_carteira(organizacao_id: int, cidade=None, busca=None, categoria=None, cnae=None, porte=None):
    clauses = ["c.organizacao_id = %s"]
    params: List[Any] = [organizacao_id]
    cidades = _norm_lista(cidade)
    if cidades:
        clauses.append("c.municipio = ANY(%s)"); params.append(cidades)
    categorias = _norm_lista(categoria)
    if categorias:
        clauses.append("c.categoria = ANY(%s)"); params.append(categorias)
    cnaes = _norm_lista(cnae)
    if cnaes:
        clauses.append("c.cnae_principal = ANY(%s)"); params.append(cnaes)
    portes = _norm_lista(porte)
    if portes:
        clauses.append("c.porte_nome = ANY(%s)"); params.append(portes)
    if busca:
        termo = f"%{busca.strip().upper()}%"
        clauses.append("(UPPER(c.razao_social) LIKE %s OR UPPER(COALESCE(c.nome_fantasia,'')) LIKE %s OR c.cnpj_completo LIKE %s)")
        params += [termo, termo, termo.replace("%", "") + "%"]
    return " AND ".join(clauses), params


def listar_carteira_db(organizacao_id: int, cidade=None, busca=None, categoria=None,
                       cnae=None, porte=None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    where, params = _where_carteira(organizacao_id, cidade, busca, categoria, cnae, porte)
    with get_db_cursor() as cur:
        cur.execute(
            f"SELECT {_CARTEIRA_SELECT} FROM empresas_carteira c WHERE {where} "
            f"ORDER BY c.razao_social LIMIT %s OFFSET %s",
            params + [limit, offset],
        )
        return cur.fetchall()


def contar_carteira_db(organizacao_id: int, cidade=None, busca=None, categoria=None,
                       cnae=None, porte=None) -> int:
    where, params = _where_carteira(organizacao_id, cidade, busca, categoria, cnae, porte)
    with get_db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM empresas_carteira c WHERE {where}", params)
        row = cur.fetchone()
        return int(row["total"]) if row else 0


def get_carteira_by_cnpj(organizacao_id: int, cnpj: str) -> Dict[str, Any]:
    cnpj_limpo = re.sub(r"\D", "", cnpj or "")
    if not cnpj_limpo:
        return {}
    with get_db_cursor() as cur:
        cur.execute(
            f"SELECT {_CARTEIRA_SELECT}, c.cnpj_completo AS cnpj_basico, "
            f"COALESCE(c.observacao, '') AS observacao, COALESCE(c.origem, '') AS origem "
            f"FROM empresas_carteira c WHERE c.organizacao_id = %s AND c.cnpj_completo = %s",
            (organizacao_id, cnpj_limpo),
        )
        return cur.fetchone() or {}


def categorias_da_carteira(organizacao_id: int) -> List[Dict[str, Any]]:
    """Categorias existentes na carteira da empresa, com a contagem -- e' o
    filtro que a tela oferece no lugar do CNAE da Receita."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT COALESCE(categoria, 'sem categoria') AS categoria, COUNT(*)::int AS total
               FROM empresas_carteira WHERE organizacao_id = %s
               GROUP BY 1 ORDER BY 2 DESC""",
            (organizacao_id,),
        )
        return cur.fetchall()


def salvar_na_carteira(organizacao_id: int, empresa: Dict[str, Any], criado_por: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Insere ou atualiza uma empresa da carteira. A chave e' (empresa, CNPJ),
    entao recarregar a mesma planilha atualiza em vez de duplicar."""
    cnpj = re.sub(r"\D", "", str(empresa.get("cnpj_completo") or empresa.get("cnpj") or ""))
    # 14 digitos e nem todos iguais: "00000000000000" passava como valido e
    # entrava na carteira como uma empresa de verdade.
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return None
    campos = {
        "razao_social": empresa.get("razao_social"),
        "nome_fantasia": empresa.get("nome_fantasia"),
        "municipio": (empresa.get("municipio") or "").upper() or None,
        "uf": (empresa.get("uf") or "").upper()[:2] or None,
        "email": empresa.get("email"),
        "contato_fone": empresa.get("contato_fone") or empresa.get("telefone"),
        "cnae_principal": empresa.get("cnae_principal"),
        "cnae_descricao": empresa.get("cnae_descricao"),
        "porte_nome": empresa.get("porte_nome"),
        "capital_social": empresa.get("capital_social"),
        "divida_total": empresa.get("divida_total"),
        "categoria": empresa.get("categoria"),
        "situacao": empresa.get("situacao"),
        "origem": empresa.get("origem") or "importacao",
        "observacao": empresa.get("observacao"),
    }
    cols = ", ".join(campos)
    marks = ", ".join(["%s"] * len(campos))
    # COALESCE no update: coluna que veio vazia na recarga nao apaga o que ja'
    # estava preenchido (e-mail conseguido a mao, por exemplo).
    updates = ", ".join(f"{k} = COALESCE(EXCLUDED.{k}, empresas_carteira.{k})" for k in campos)
    with get_db_cursor() as cur:
        cur.execute(
            f"""INSERT INTO empresas_carteira (organizacao_id, cnpj_completo, criado_por, {cols})
                VALUES (%s, %s, %s, {marks})
                ON CONFLICT (organizacao_id, cnpj_completo) DO UPDATE SET {updates}
                RETURNING id, cnpj_completo, razao_social, categoria""",
            [organizacao_id, cnpj, criado_por] + list(campos.values()),
        )
        return cur.fetchone()


def remover_da_carteira(organizacao_id: int, cnpj: str) -> bool:
    with get_db_cursor() as cur:
        cur.execute(
            "DELETE FROM empresas_carteira WHERE organizacao_id = %s AND cnpj_completo = %s",
            (organizacao_id, re.sub(r"\D", "", cnpj or "")),
        )
        return cur.rowcount > 0


def listar_empresas_db(
    cidade=None, cnae=None, porte=None, busca: Optional[str] = None,
    divida_min=None, divida_max=None, capital_min=None, capital_max=None,
    fundacao_de: Optional[str] = None, fundacao_ate: Optional[str] = None,
    incluir_inativas: bool = True, contato=None, potencial=None, categoria=None,
    ordenar_por: str = "razao_social",
    limit: int = 100, offset: int = 0,
    organizacao_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Lista empresas com o funil de filtros (server-side).

    A fonte depende da empresa: escopo_base='carteira' le' a lista propria
    dela, o padrao le' dados_empresas (Receita Federal). As colunas de saida
    sao as mesmas nos dois casos.
    Retorna [] se a tabela ainda nao existir (ETL nunca rodou) ou em caso de erro."""
    if organizacao_id is not None and org_escopo_base(organizacao_id) == "carteira":
        return listar_carteira_db(organizacao_id, cidade=cidade, busca=busca,
                                  categoria=categoria, cnae=cnae, porte=porte,
                                  limit=limit, offset=offset)
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "dados_empresas"):
                return []
            where, params = _where_empresas(
                cidade, cnae, porte, busca, divida_min, divida_max,
                capital_min, capital_max, fundacao_de, fundacao_ate, incluir_inativas,
                contato, potencial, categoria,
            )
            order_sql = (
                'ep.potencial_score DESC NULLS LAST, e."RAZAO_SOCIAL"'
                if ordenar_por == "potencial"
                else 'e."RAZAO_SOCIAL"'
            )
            sql = f"""
                SELECT
                    e."CNPJ_COMPLETO" AS cnpj_completo,
                    e."RAZAO_SOCIAL" AS razao_social,
                    e."NOME_FANTASIA" AS nome_fantasia,
                    COALESCE(m.nome_municipio, '') AS municipio,
                    e."CNAE_PRINCIPAL" AS cnae_principal,
                    COALESCE(c.descricao_cnae, '') AS cnae_descricao,
                    COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) AS capital_social,
                    COALESCE(NULLIF(e."DIVIDA_TOTAL"::text, '')::numeric, 0) AS divida_total,
                    ({PORTE_NOME_SQL}) AS porte_nome,
                    e."DATA_FUNDACAO" AS data_fundacao,
                    e."EMAIL" AS email,
                    ({CONTATO_FONE_SQL}) AS contato_fone,
                    COALESCE(ep.potencial_score, 0) AS potencial_score,
                    COALESCE(ep.potencial_tier, 'baixo') AS potencial_tier
                FROM dados_empresas e
                LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                LEFT JOIN cnaes c ON c.codigo_cnae = e."CNAE_PRINCIPAL"
                LEFT JOIN empresas_potencial ep ON ep.cnpj_completo = e."CNPJ_COMPLETO"
                WHERE 1=1 {where}
                ORDER BY {order_sql} LIMIT %s OFFSET %s
            """
            cur.execute(sql, params + [limit, offset])
            return cur.fetchall()
    except Exception as e:
        log.warning(f"listar_empresas_db falhou, retornando lista vazia: {e}")
        return []


def contar_empresas_db(
    cidade=None, cnae=None, porte=None, busca: Optional[str] = None,
    divida_min=None, divida_max=None, capital_min=None, capital_max=None,
    fundacao_de: Optional[str] = None, fundacao_ate: Optional[str] = None,
    incluir_inativas: bool = True, potencial=None, categoria=None,
    organizacao_id: Optional[int] = None,
) -> int:
    """Conta quantas empresas batem no filtro atual (para o contador do funil,
    sem trazer as linhas). Retorna 0 se a tabela nao existir ou em caso de erro."""
    if organizacao_id is not None and org_escopo_base(organizacao_id) == "carteira":
        return contar_carteira_db(organizacao_id, cidade=cidade, busca=busca,
                                  categoria=categoria, cnae=cnae, porte=porte)
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "dados_empresas"):
                return 0
            where, params = _where_empresas(
                cidade, cnae, porte, busca, divida_min, divida_max,
                capital_min, capital_max, fundacao_de, fundacao_ate, incluir_inativas,
                potencial=potencial, categoria=categoria,
            )
            sql = f"""
                SELECT COUNT(*) AS total
                FROM dados_empresas e
                LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                LEFT JOIN empresas_potencial ep ON ep.cnpj_completo = e."CNPJ_COMPLETO"
                WHERE 1=1 {where}
            """
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row["total"]) if row and row.get("total") is not None else 0
    except Exception as e:
        log.warning(f"contar_empresas_db falhou, retornando 0: {e}")
        return 0


def get_empresa_by_cnpj_db(cnpj: str, organizacao_id: Optional[int] = None) -> Dict[str, Any]:
    """Busca uma empresa por CNPJ, com municipio e socios resolvidos.
    Empresa de escopo 'carteira' busca na lista propria dela.
    Retorna {} se nao encontrada, tabela ausente, ou erro."""
    cnpj_limpo = re.sub(r"\D", "", cnpj or "")
    if not cnpj_limpo:
        return {}
    if organizacao_id is not None and org_escopo_base(organizacao_id) == "carteira":
        return get_carteira_by_cnpj(organizacao_id, cnpj_limpo)
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "dados_empresas"):
                return {}
            cur.execute(
                f"""
                SELECT
                    e."CNPJ_COMPLETO" AS cnpj_completo,
                    e."CNPJ_BASICO" AS cnpj_basico,
                    e."RAZAO_SOCIAL" AS razao_social,
                    e."NOME_FANTASIA" AS nome_fantasia,
                    COALESCE(m.nome_municipio, '') AS municipio,
                    e."CNAE_PRINCIPAL" AS cnae_principal,
                    COALESCE(c.descricao_cnae, '') AS cnae_descricao,
                    COALESCE(NULLIF(e."CAPITAL_SOCIAL"::text, '')::numeric, 0) AS capital_social,
                    COALESCE(NULLIF(e."DIVIDA_TOTAL"::text, '')::numeric, 0) AS divida_total,
                    ({PORTE_NOME_SQL}) AS porte_nome,
                    e."DATA_FUNDACAO" AS data_fundacao,
                    ({CONTATO_FONE_SQL}) AS contato_fone,
                    COALESCE(ep.potencial_score, 0) AS potencial_score,
                    COALESCE(ep.potencial_tier, 'baixo') AS potencial_tier
                FROM dados_empresas e
                LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                LEFT JOIN cnaes c ON c.codigo_cnae = e."CNAE_PRINCIPAL"
                LEFT JOIN empresas_potencial ep ON ep.cnpj_completo = e."CNPJ_COMPLETO"
                WHERE e."CNPJ_COMPLETO" = %s
                LIMIT 1
                """,
                (cnpj_limpo,),
            )
            row = cur.fetchone()
            if not row:
                return {}
            socios: List[Dict[str, Any]] = []
            if _tabela_existe(cur, "dados_socios"):
                cur.execute(
                    """
                    SELECT
                        "NOME_SOCIO" AS nome_socio,
                        "CPF_CNPJ_SOCIO" AS cpf_cnpj_socio,
                        "QUALIF_SOCIO" AS qualif_socio
                    FROM dados_socios
                    WHERE "CNPJ_BASICO" = %s
                    """,
                    (row.get("cnpj_basico"),),
                )
                socios = cur.fetchall()
            resultado = dict(row)
            resultado["socios"] = socios
            return resultado
    except Exception as e:
        log.warning(f"get_empresa_by_cnpj_db falhou, retornando vazio: {e}")
        return {}


def get_metricas_db() -> Dict[str, Any]:
    """Estatisticas agregadas de dados_empresas. Retorna zeros se a tabela
    ainda nao existir ou em caso de erro."""
    vazio = {
        "total_empresas": 0, "por_cidade": {}, "por_porte": {},
        "capital_total": 0.0, "divida_total": 0.0, "top_cnaes": {},
    }
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "dados_empresas"):
                return vazio
            cur.execute('SELECT COUNT(*) AS total FROM dados_empresas')
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT COALESCE(m.nome_municipio, 'Sem municipio') AS cidade, COUNT(*) AS qtd
                FROM dados_empresas e
                LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                GROUP BY cidade ORDER BY qtd DESC LIMIT 10
            """)
            por_cidade = {r["cidade"]: r["qtd"] for r in cur.fetchall()}

            cur.execute(f'SELECT ({PORTE_NOME_SQL}) AS porte, COUNT(*) AS qtd FROM dados_empresas e GROUP BY porte')
            por_porte = {(r["porte"] or "Nao informado"): r["qtd"] for r in cur.fetchall()}

            cur.execute('SELECT COALESCE(SUM("CAPITAL_SOCIAL"::numeric), 0) AS total FROM dados_empresas')
            capital_total = float(cur.fetchone()["total"])

            cur.execute('SELECT COALESCE(SUM("DIVIDA_TOTAL"::numeric), 0) AS total FROM dados_empresas')
            divida_total = float(cur.fetchone()["total"])

            cur.execute("""
                SELECT "CNAE_PRINCIPAL" AS cnae, COUNT(*) AS qtd
                FROM dados_empresas GROUP BY cnae ORDER BY qtd DESC LIMIT 10
            """)
            top_cnaes = {r["cnae"]: r["qtd"] for r in cur.fetchall()}

            return {
                "total_empresas": total, "por_cidade": por_cidade, "por_porte": por_porte,
                "capital_total": capital_total, "divida_total": divida_total, "top_cnaes": top_cnaes,
            }
    except Exception as e:
        log.warning(f"get_metricas_db falhou, retornando zeros: {e}")
        return vazio

def get_pipeline_metadata() -> Dict[str, Any]:
    """Le a tabela pipeline_metadata (mes RF, trimestre PGFN, ultima
    sincronizacao, contagens) gravada por scripts/sync_data_to_db.py apos
    cada rodada do ETL. Usado pela aba "Sobre" em Configuracoes. Retorna
    dict vazio (sem quebrar) se a tabela nao existir ou o ETL nunca rodou."""
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "pipeline_metadata"):
                return {}
            cur.execute("SELECT chave, valor, atualizado_em FROM pipeline_metadata")
            linhas = cur.fetchall()
            return {
                r["chave"]: {"valor": r["valor"], "atualizado_em": r["atualizado_em"]}
                for r in linhas
            }
    except Exception as e:
        log.warning(f"get_pipeline_metadata falhou, retornando vazio: {e}")
        return {}


def seed_default_templates() -> int:
    """Popula a tabela email_templates com os modelos padrao (backend/mailer/templates.py::TEMPLATES_PADRAO),
    apenas se a tabela ainda estiver vazia. Idempotente -- seguro de chamar em todo startup."""
    try:
        from ..mailer.templates import TEMPLATES_PADRAO
    except ImportError:
        from mailer.templates import TEMPLATES_PADRAO
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM email_templates")
        row = cur.fetchone()
        if row and row.get("cnt", 0) > 0:
            return 0
        criados = 0
        for dados in TEMPLATES_PADRAO.values():
            cur.execute(
                f"INSERT INTO email_templates (nome, assunto, corpo_html, corpo_texto, criado_por, categoria_cnae) VALUES (%s, %s, %s, %s, %s, %s)",
                (dados["nome"], dados["assunto"], dados["corpo_html"], dados["corpo_texto"], "sistema", "todos"),
            )
            criados += 1
        return criados


def buscar_empresas_rapido(termo: str, limite: int = 10) -> List[Dict[str, Any]]:
    """Busca por nome ou CNPJ, so' o que precisa pra montar um autocomplete
    (cnpj + nome + cidade). Limite baixo e sem contagem total de proposito --
    e' pra escolher uma empresa numa lista curta, nao pra navegar a base."""
    termo = (termo or "").strip()
    if len(termo) < 3:
        return []
    so_digitos = re.sub(r"\D", "", termo)
    try:
        with get_db_cursor() as cur:
            if so_digitos and len(so_digitos) >= 6:
                cur.execute(
                    """SELECT e."CNPJ_COMPLETO" AS cnpj_completo, e."RAZAO_SOCIAL" AS razao_social,
                              COALESCE(m.nome_municipio, '') AS municipio
                       FROM dados_empresas e
                       LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                       WHERE e."CNPJ_COMPLETO" LIKE %s LIMIT %s""",
                    (so_digitos + "%", limite),
                )
            else:
                cur.execute(
                    """SELECT e."CNPJ_COMPLETO" AS cnpj_completo, e."RAZAO_SOCIAL" AS razao_social,
                              COALESCE(m.nome_municipio, '') AS municipio
                       FROM dados_empresas e
                       LEFT JOIN municipios m ON m.cod_municipio = e."COD_MUNICIPIO"
                       WHERE e."RAZAO_SOCIAL" LIKE %s LIMIT %s""",
                    (termo.upper() + "%", limite),
                )
            return cur.fetchall()
    except Exception as e:
        log.warning(f"buscar_empresas_rapido falhou: {e}")
        return []


def buscar_socios_principais(cnpjs_basicos: List[str]) -> Dict[str, str]:
    """CNPJ_BASICO -> nome do socio 'responsavel' de cada empresa (pra
    personalizar campanha com o nome de uma pessoa, nao so' da empresa).
    Prioridade por qualificacao (codigos da Receita Federal): Socio-
    Administrador > Titular > Administrador > Presidente > Diretor > Socio
    comum > qualquer outra. Uma empresa pode ter varios socios com a mesma
    qualificacao -- pega um so' (o primeiro por ordem alfabetica, so' pra
    ser deterministico entre chamadas)."""
    if not cnpjs_basicos:
        return {}
    with get_db_cursor() as cur:
        cur.execute(
            """
            WITH ranked AS (
                SELECT "CNPJ_BASICO", "NOME_SOCIO",
                       ROW_NUMBER() OVER (
                           PARTITION BY "CNPJ_BASICO"
                           ORDER BY CASE "QUALIF_SOCIO"
                               WHEN '49' THEN 1
                               WHEN '65' THEN 2
                               WHEN '05' THEN 3
                               WHEN '16' THEN 4
                               WHEN '10' THEN 5
                               WHEN '22' THEN 6
                               ELSE 9
                           END, "NOME_SOCIO"
                       ) AS rn
                FROM dados_socios
                WHERE "CNPJ_BASICO" = ANY(%s) AND COALESCE("NOME_SOCIO", '') <> ''
            )
            SELECT "CNPJ_BASICO", "NOME_SOCIO" FROM ranked WHERE rn = 1
            """,
            (cnpjs_basicos,),
        )
        return {r["CNPJ_BASICO"]: r["NOME_SOCIO"] for r in cur.fetchall()}


# ==================== DESCADASTRO DE E-MAIL (LGPD/opt-out) ====================
# Global (nao por empresa): pedido de "nao me mande mais e-mail" vale pra
# qualquer organizacao que tentar mandar pra esse endereco.

def email_esta_descadastrado(email: str) -> bool:
    if not email:
        return False
    with get_db_cursor() as cur:
        cur.execute("SELECT 1 FROM emails_descadastrados WHERE email = %s", (email.strip().lower(),))
        return cur.fetchone() is not None


def descadastrar_email(email: str, cnpj: Optional[str] = None, motivo: Optional[str] = None) -> bool:
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO emails_descadastrados (email, cnpj, motivo)
               VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING""",
            (email.strip().lower(), cnpj, motivo),
        )
        return True


# ==================== CRM: ATIVIDADES/TAREFAS ====================

def listar_usuarios_da_org(organizacao_id: int) -> List[Dict[str, Any]]:
    """Usuarios que podem ser responsaveis por uma atividade (membros da
    mesma organizacao ativa -- ex.: os socios da SVYP)."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT u.id, u.username, u.email
               FROM app_users u
               JOIN usuario_organizacoes uo ON uo.user_id = u.id
               WHERE uo.organizacao_id = %s AND u.is_active = TRUE
               ORDER BY u.username""",
            (organizacao_id,),
        )
        return cur.fetchall()


def criar_atividade_crm(
    cnpj: str, organizacao_id: int, titulo: str, criado_por: Optional[str] = None,
    tipo: str = "tarefa", descricao: Optional[str] = None,
    responsavel_user_id: Optional[int] = None, prazo: Optional[str] = None,
) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO crm_atividades
               (organizacao_id, cnpj, titulo, tipo, descricao, responsavel_user_id, prazo, criado_por)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (organizacao_id, cnpj, titulo, tipo, descricao, responsavel_user_id, prazo, criado_por),
        )
        return cur.fetchone()


# Semaforo das atividades -- mesma ideia do monitor de e-mails (verde/amarelo/
# vermelho), mas medindo o prazo da tarefa em vez do tempo sem resposta:
#   cinza    = concluida
#   vermelho = venceu (ou, sem prazo, esta' aberta ha' mais de 14 dias)
#   amarelo  = vence hoje ou amanha (ou aberta ha' mais de 7 dias sem prazo)
#   verde    = no prazo
ATIVIDADE_SEMAFORO_SQL = """
    CASE
        WHEN a.status = 'concluida' THEN 'cinza'
        WHEN a.prazo IS NOT NULL AND a.prazo < CURRENT_DATE THEN 'vermelho'
        WHEN a.prazo IS NOT NULL AND a.prazo <= CURRENT_DATE + 1 THEN 'amarelo'
        WHEN a.prazo IS NOT NULL THEN 'verde'
        WHEN a.criado_em < NOW() - INTERVAL '14 days' THEN 'vermelho'
        WHEN a.criado_em < NOW() - INTERVAL '7 days' THEN 'amarelo'
        ELSE 'verde'
    END AS semaforo"""

# Tempo decorrido: dias em aberto e dias ate'/desde o prazo (negativo = atrasada)
ATIVIDADE_TEMPO_SQL = """
    FLOOR(EXTRACT(EPOCH FROM (COALESCE(a.concluido_em, NOW()) - a.criado_em)) / 86400.0)::int AS dias_aberta,
    CASE WHEN a.prazo IS NULL THEN NULL ELSE (a.prazo - CURRENT_DATE) END AS dias_para_prazo"""


def listar_todas_atividades(organizacao_id: int) -> List[Dict[str, Any]]:
    """Todas as atividades da organizacao, com nome da empresa resolvido --
    base do board tipo Trello (visao agregada, nao so' por empresa)."""
    with get_db_cursor() as cur:
        cur.execute(
            f"""SELECT a.*, u.username AS responsavel_username,
                      COALESCE(e."RAZAO_SOCIAL", e."NOME_FANTASIA", a.cnpj) AS razao_social,
                      {ATIVIDADE_SEMAFORO_SQL}, {ATIVIDADE_TEMPO_SQL},
                      (SELECT COUNT(*) FROM crm_atividade_historico h WHERE h.atividade_id = a.id)::int AS n_historico,
                      (SELECT COUNT(*) FROM crm_atividade_anexos x WHERE x.atividade_id = a.id)::int AS n_anexos
               FROM crm_atividades a
               LEFT JOIN app_users u ON u.id = a.responsavel_user_id
               LEFT JOIN dados_empresas e ON e."CNPJ_COMPLETO" = a.cnpj
               WHERE a.organizacao_id = %s
               ORDER BY a.prazo ASC NULLS LAST, a.criado_em ASC""",
            (organizacao_id,),
        )
        return cur.fetchall()


# Colunas do anexo SEM o conteudo -- listar anexo nunca deve arrastar os
# bytes do arquivo junto (uma tarefa com 5 PDFs viraria uma resposta de MBs).
_ANEXO_COLS = "id, atividade_id, nome, mime, tamanho, enviado_por, criado_em"


# ==================== GASTOS (despesas por empresa) ====================

_GASTO_COLS = ("id, organizacao_id, descricao, valor, data, categoria, forma_pagamento, "
               "observacao, criado_por, criado_em, removido_em, removido_por")


def criar_gasto(
    organizacao_id: int, descricao: str, valor: float, data: Optional[str] = None,
    categoria: str = "outros", forma_pagamento: Optional[str] = None,
    observacao: Optional[str] = None, criado_por: Optional[str] = None,
) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute(
            f"""INSERT INTO gastos (organizacao_id, descricao, valor, data, categoria,
                                    forma_pagamento, observacao, criado_por)
                VALUES (%s,%s,%s,COALESCE(%s::date, CURRENT_DATE),%s,%s,%s,%s)
                RETURNING {_GASTO_COLS}""",
            (organizacao_id, descricao, valor, data or None, categoria,
             forma_pagamento, observacao, criado_por),
        )
        return cur.fetchone()


def listar_gastos(
    organizacao_id: int, de: Optional[str] = None, ate: Optional[str] = None,
    categoria: Optional[str] = None, incluir_removidos: bool = False,
) -> List[Dict[str, Any]]:
    where = ["organizacao_id = %s"]
    params: List[Any] = [organizacao_id]
    if not incluir_removidos:
        where.append("removido_em IS NULL")
    if de:
        where.append("data >= %s::date"); params.append(de)
    if ate:
        where.append("data <= %s::date"); params.append(ate)
    if categoria:
        where.append("categoria = %s"); params.append(categoria)
    with get_db_cursor() as cur:
        cur.execute(
            f"SELECT {_GASTO_COLS} FROM gastos WHERE {' AND '.join(where)} "
            "ORDER BY data DESC, id DESC",
            params,
        )
        return cur.fetchall()


def resumo_gastos(organizacao_id: int, de: Optional[str] = None, ate: Optional[str] = None) -> Dict[str, Any]:
    """Total do periodo e quebra por categoria -- o que a tela mostra em cima."""
    where = ["organizacao_id = %s", "removido_em IS NULL"]
    params: List[Any] = [organizacao_id]
    if de:
        where.append("data >= %s::date"); params.append(de)
    if ate:
        where.append("data <= %s::date"); params.append(ate)
    cond = " AND ".join(where)
    with get_db_cursor() as cur:
        cur.execute(f"SELECT COALESCE(SUM(valor),0) AS total, COUNT(*)::int AS n FROM gastos WHERE {cond}", params)
        topo = cur.fetchone()
        cur.execute(
            f"SELECT categoria, COALESCE(SUM(valor),0) AS total, COUNT(*)::int AS n "
            f"FROM gastos WHERE {cond} GROUP BY categoria ORDER BY total DESC",
            params,
        )
        return {
            "total": float(topo["total"] or 0),
            "quantidade": topo["n"],
            "por_categoria": [
                {"categoria": r["categoria"], "total": float(r["total"]), "quantidade": r["n"]}
                for r in cur.fetchall()
            ],
        }


def remover_gasto(gasto_id: int, organizacao_id: int, removido_por: Optional[str] = None) -> bool:
    """Exclusao logica: o registro continua no banco, so' sai da lista e do
    total. Gasto lancado errado se corrige restaurando ou lancando de novo --
    nao sumindo com o rastro."""
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE gastos SET removido_em = NOW(), removido_por = %s "
            "WHERE id = %s AND organizacao_id = %s AND removido_em IS NULL",
            (removido_por, gasto_id, organizacao_id),
        )
        return cur.rowcount > 0


def restaurar_gasto(gasto_id: int, organizacao_id: int) -> bool:
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE gastos SET removido_em = NULL, removido_por = NULL "
            "WHERE id = %s AND organizacao_id = %s",
            (gasto_id, organizacao_id),
        )
        return cur.rowcount > 0


def atualizar_gasto(gasto_id: int, organizacao_id: int, campos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    permitidos = ("descricao", "valor", "data", "categoria", "forma_pagamento", "observacao")
    sets, params = [], []
    for campo in permitidos:
        if campo in campos:
            sets.append(f"{campo} = %s")
            params.append(campos[campo])
    if not sets:
        return None
    params += [gasto_id, organizacao_id]
    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE gastos SET {', '.join(sets)} WHERE id = %s AND organizacao_id = %s "
            f"RETURNING {_GASTO_COLS}",
            params,
        )
        return cur.fetchone()


def salvar_anexo_atividade(
    atividade_id: int, organizacao_id: int, nome: str, mime: Optional[str],
    conteudo: bytes, enviado_por: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Anexa um arquivo a uma atividade. Devolve None se a atividade nao for
    da organizacao -- a checagem e' aqui e nao no endpoint pra nao existir
    caminho que grave anexo em tarefa de outra empresa."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM crm_atividades WHERE id = %s AND organizacao_id = %s",
            (atividade_id, organizacao_id),
        )
        if not cur.fetchone():
            return None
        cur.execute(
            f"""INSERT INTO crm_atividade_anexos (atividade_id, nome, mime, tamanho, conteudo, enviado_por)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING {_ANEXO_COLS}""",
            (atividade_id, nome, mime, len(conteudo), conteudo, enviado_por),
        )
        return cur.fetchone()


def listar_anexos_atividade(atividade_id: int, organizacao_id: int) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            f"""SELECT {', '.join('a.' + c for c in _ANEXO_COLS.split(', '))}
                FROM crm_atividade_anexos a
                JOIN crm_atividades t ON t.id = a.atividade_id
                WHERE a.atividade_id = %s AND t.organizacao_id = %s
                ORDER BY a.criado_em ASC""",
            (atividade_id, organizacao_id),
        )
        return cur.fetchall()


def get_anexo_atividade(anexo_id: int, organizacao_id: int) -> Optional[Dict[str, Any]]:
    """Bytes do anexo, ja' filtrado pela organizacao -- e' o que serve o
    download/visualizacao."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT a.nome, a.mime, a.conteudo
               FROM crm_atividade_anexos a
               JOIN crm_atividades t ON t.id = a.atividade_id
               WHERE a.id = %s AND t.organizacao_id = %s""",
            (anexo_id, organizacao_id),
        )
        return cur.fetchone()


def deletar_anexo_atividade(anexo_id: int, organizacao_id: int) -> Optional[Dict[str, Any]]:
    """Remove o anexo e devolve {atividade_id, nome} pra registrar no historico."""
    with get_db_cursor() as cur:
        cur.execute(
            """DELETE FROM crm_atividade_anexos a
               USING crm_atividades t
               WHERE a.id = %s AND t.id = a.atividade_id AND t.organizacao_id = %s
               RETURNING a.atividade_id, a.nome""",
            (anexo_id, organizacao_id),
        )
        return cur.fetchone()


def contar_anexos_por_atividade(organizacao_id: int) -> Dict[int, int]:
    """atividade_id -> quantidade de anexos, pra badge no card sem uma
    consulta por card."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT a.atividade_id, COUNT(*)::int AS n
               FROM crm_atividade_anexos a
               JOIN crm_atividades t ON t.id = a.atividade_id
               WHERE t.organizacao_id = %s
               GROUP BY a.atividade_id""",
            (organizacao_id,),
        )
        return {r["atividade_id"]: r["n"] for r in cur.fetchall()}


def atribuir_atividade(atividade_id: int, organizacao_id: int, responsavel_user_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """Troca o responsavel. Devolve {de, para} com os usernames pra registrar
    no historico -- quem passou a tarefa pra quem fica no acompanhamento.
    None quando a atividade nao e' da organizacao."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT u.username AS anterior FROM crm_atividades a
               LEFT JOIN app_users u ON u.id = a.responsavel_user_id
               WHERE a.id = %s AND a.organizacao_id = %s""",
            (atividade_id, organizacao_id),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cur.execute(
            "UPDATE crm_atividades SET responsavel_user_id = %s WHERE id = %s AND organizacao_id = %s",
            (responsavel_user_id, atividade_id, organizacao_id),
        )
        novo = None
        if responsavel_user_id:
            cur.execute("SELECT username, email FROM app_users WHERE id = %s", (responsavel_user_id,))
            novo = cur.fetchone()
        return {
            "de": row["anterior"],
            "para": novo["username"] if novo else None,
            "email": novo["email"] if novo else None,
        }


def registrar_historico_atividade(
    atividade_id: int, tipo: str, autor: str,
    texto: Optional[str] = None, de: Optional[str] = None, para: Optional[str] = None,
) -> Dict[str, Any]:
    """Uma linha do acompanhamento. tipo: 'comentario' | 'status' | 'prazo'."""
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO crm_atividade_historico (atividade_id, tipo, texto, de, para, autor)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
            (atividade_id, tipo, texto, de, para, autor),
        )
        return cur.fetchone()


def listar_historico_atividade(atividade_id: int, organizacao_id: int) -> List[Dict[str, Any]]:
    """Historico em ordem cronologica. Passa pela organizacao de proposito --
    ninguem le' o acompanhamento de uma tarefa de outra empresa."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT h.* FROM crm_atividade_historico h
               JOIN crm_atividades a ON a.id = h.atividade_id
               WHERE h.atividade_id = %s AND a.organizacao_id = %s
               ORDER BY h.criado_em ASC""",
            (atividade_id, organizacao_id),
        )
        return cur.fetchall()


def atualizar_prazo_atividade(atividade_id: int, organizacao_id: int, prazo: Optional[str]) -> Optional[str]:
    """Troca o prazo e devolve o prazo ANTERIOR (pra registrar no historico).
    Devolve None quando a atividade nao e' da organizacao."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT prazo FROM crm_atividades WHERE id = %s AND organizacao_id = %s",
            (atividade_id, organizacao_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        anterior = row["prazo"].isoformat() if row["prazo"] else ""
        cur.execute(
            "UPDATE crm_atividades SET prazo = %s WHERE id = %s AND organizacao_id = %s",
            (prazo or None, atividade_id, organizacao_id),
        )
        return anterior


def get_status_atividade(atividade_id: int, organizacao_id: int) -> Optional[str]:
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT status FROM crm_atividades WHERE id = %s AND organizacao_id = %s",
            (atividade_id, organizacao_id),
        )
        row = cur.fetchone()
        return row["status"] if row else None


def mover_atividade_crm(atividade_id: int, organizacao_id: int, status: str) -> bool:
    if status not in ("pendente", "em_andamento", "concluida"):
        return False
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE crm_atividades SET status = %s,
                   concluido_em = CASE WHEN %s = 'concluida' THEN NOW() ELSE NULL END
               WHERE id = %s AND organizacao_id = %s""",
            (status, status, atividade_id, organizacao_id),
        )
        return cur.rowcount > 0


def listar_atividades_crm(cnpj: str, organizacao_id: int) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            f"""SELECT a.*, u.username AS responsavel_username,
                      {ATIVIDADE_SEMAFORO_SQL}, {ATIVIDADE_TEMPO_SQL},
                      (SELECT COUNT(*) FROM crm_atividade_historico h WHERE h.atividade_id = a.id)::int AS n_historico,
                      (SELECT COUNT(*) FROM crm_atividade_anexos x WHERE x.atividade_id = a.id)::int AS n_anexos
               FROM crm_atividades a
               LEFT JOIN app_users u ON u.id = a.responsavel_user_id
               WHERE a.cnpj = %s AND a.organizacao_id = %s
               ORDER BY (a.status = 'concluida'), a.prazo NULLS LAST, a.criado_em DESC""",
            (cnpj, organizacao_id),
        )
        return cur.fetchall()


def contar_atividades_pendentes(organizacao_id: int) -> Dict[str, int]:
    """CNPJ -> quantidade de atividades pendentes, pra badge nos cards do
    Kanban sem precisar de uma consulta por card."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT cnpj, COUNT(*) AS n FROM crm_atividades
               WHERE organizacao_id = %s AND status = 'pendente'
               GROUP BY cnpj""",
            (organizacao_id,),
        )
        return {r["cnpj"]: r["n"] for r in cur.fetchall()}


def concluir_atividade_crm(atividade_id: int, organizacao_id: int) -> bool:
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE crm_atividades SET status = 'concluida', concluido_em = NOW()
               WHERE id = %s AND organizacao_id = %s""",
            (atividade_id, organizacao_id),
        )
        return cur.rowcount > 0


def deletar_atividade_crm(atividade_id: int, organizacao_id: int) -> bool:
    with get_db_cursor() as cur:
        cur.execute(
            "DELETE FROM crm_atividades WHERE id = %s AND organizacao_id = %s",
            (atividade_id, organizacao_id),
        )
        return cur.rowcount > 0


# ==================== CAMPANHAS EM LOTE (envio diario ate um limite) ====================

# ==================== LISTA DE ENVIO DA CAMPANHA ====================
#
# A campanha pode ter destinatarios montados a mao em vez de sair de um
# filtro sobre a base. E' o caminho pra quem quer escolher pra quem vai
# (planilha do cliente, selecao na tela, um e-mail digitado na hora).

def adicionar_destinatarios(campanha_id: int, itens: List[Dict[str, Any]]) -> Dict[str, int]:
    """Adiciona e-mails na lista da campanha. Repetido nao duplica (a chave e'
    campanha + e-mail), entao da' pra ir somando de varias origens."""
    adicionados, invalidos, repetidos = 0, 0, 0
    with get_db_cursor() as cur:
        for item in itens:
            email = (item.get("email") or "").strip().lower()
            if "@" not in email or "." not in email.split("@")[-1]:
                invalidos += 1
                continue
            cnpj = re.sub(r"\D", "", str(item.get("cnpj") or "")) or None
            cur.execute(
                """INSERT INTO campanha_destinatarios
                   (campanha_id, email, cnpj, razao_social, municipio, nome_socio, origem)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (campanha_id, email) DO NOTHING
                   RETURNING id""",
                (campanha_id, email, cnpj, item.get("razao_social"), item.get("municipio"),
                 item.get("nome_socio"), item.get("origem") or "manual"),
            )
            if cur.fetchone():
                adicionados += 1
            else:
                repetidos += 1
    return {"adicionados": adicionados, "invalidos": invalidos, "repetidos": repetidos}


def listar_destinatarios(campanha_id: int, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT * FROM campanha_destinatarios WHERE campanha_id = %s
               ORDER BY razao_social NULLS LAST, email LIMIT %s OFFSET %s""",
            (campanha_id, limit, offset),
        )
        return cur.fetchall()


def contar_destinatarios(campanha_id: int) -> int:
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM campanha_destinatarios WHERE campanha_id = %s", (campanha_id,))
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def remover_destinatario(campanha_id: int, destinatario_id: int) -> bool:
    with get_db_cursor() as cur:
        cur.execute(
            "DELETE FROM campanha_destinatarios WHERE id = %s AND campanha_id = %s",
            (destinatario_id, campanha_id),
        )
        return cur.rowcount > 0


def limpar_destinatarios(campanha_id: int) -> int:
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM campanha_destinatarios WHERE campanha_id = %s", (campanha_id,))
        return cur.rowcount


def cnpjs_ja_contatados_campanha(campanha_id: int) -> set:
    """CNPJs que essa campanha ja contatou (em qualquer lote anterior).
    Usado pra calcular quem ainda falta no proximo lote."""
    with get_db_cursor() as cur:
        cur.execute("SELECT cnpj FROM campanha_envios WHERE campanha_id = %s", (campanha_id,))
        return {r["cnpj"] for r in cur.fetchall()}


def registrar_envio_campanha(campanha_id: int, cnpj: str, canal: str, status: str = "enviado") -> None:
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO campanha_envios (campanha_id, cnpj, canal, status)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (campanha_id, cnpj) DO UPDATE SET status = EXCLUDED.status""",
            (campanha_id, cnpj, canal, status),
        )


def contar_envios_campanha(campanha_id: int) -> int:
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM campanha_envios WHERE campanha_id = %s", (campanha_id,))
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def listar_campanhas_pendentes() -> List[Dict[str, Any]]:
    """Campanhas em lote que ainda tem lote pra mandar hoje: status
    'agendada' (primeiro lote) ou 'em_andamento' (proximos lotes), com
    repetir_ate ainda no futuro (ou sem data-limite) e que ainda nao
    rodaram hoje. Usada pelo cron diario (GitHub Actions)."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT * FROM campanhas
               WHERE status IN ('agendada', 'em_andamento')
                 AND tamanho_lote IS NOT NULL
                 AND (repetir_ate IS NULL OR repetir_ate >= CURRENT_DATE)
                 AND (ultimo_lote_em IS NULL OR ultimo_lote_em::date < CURRENT_DATE)
               ORDER BY id"""
        )
        rows = cur.fetchall()
        for r in rows:
            if r and r.get("filtros") and isinstance(r["filtros"], str):
                try: r["filtros"] = json.loads(r["filtros"])
                except: pass
        return rows


# ==================== WHATSAPP (Twilio) ====================

def _so_digitos(v: Optional[str]) -> str:
    return re.sub(r"\D", "", v or "")


def buscar_empresa_por_telefone(telefone: str) -> Optional[str]:
    """Tenta achar o CNPJ de uma empresa cujo telefone cadastrado bate com o
    numero recebido no WhatsApp. Compara so os ultimos 8 digitos (numero sem
    DDI/DDD) pra tolerar diferenca de formatacao entre o que a RF cadastrou e
    o que o Twilio manda. Retorna None se nao achar (mensagem fica sem CNPJ
    associado, mas continua visivel na caixa de entrada por telefone)."""
    digitos = _so_digitos(telefone)
    if len(digitos) < 8:
        return None
    ultimos8 = digitos[-8:]
    try:
        with get_db_cursor() as cur:
            # ORDER BY determinístico: sem isso, quando o sufixo bate em mais
            # de uma empresa (esperado -- 8 digitos colidem em ~1-2% dos casos
            # numa base de 1.6M+ empresas), o Postgres pode devolver uma linha
            # diferente a cada chamada e a mesma conversa mudaria de "dona".
            cur.execute(
                """SELECT "CNPJ_COMPLETO" AS cnpj FROM dados_empresas
                   WHERE right(regexp_replace(COALESCE("TELEFONE", ''), '\\D', '', 'g'), 8) = %s
                      OR right(regexp_replace(COALESCE("TELEFONE_2", ''), '\\D', '', 'g'), 8) = %s
                   ORDER BY "CNPJ_COMPLETO" LIMIT 1""",
                (ultimos8, ultimos8),
            )
            row = cur.fetchone()
            return row["cnpj"] if row else None
    except Exception as e:
        log.warning(f"buscar_empresa_por_telefone falhou: {e}")
        return None


def _cnpj_da_conversa(telefone: str) -> Optional[str]:
    """CNPJ ja associado a essa conversa (se alguma mensagem anterior achou
    um match). Evita re-rodar o match fuzzy por telefone a cada mensagem --
    o que, alem de mais lento, podia (antes desta funcao existir) associar
    cada mensagem da MESMA conversa a uma empresa diferente."""
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """SELECT cnpj FROM whatsapp_mensagens
                   WHERE telefone = %s AND cnpj IS NOT NULL
                   ORDER BY criado_em ASC LIMIT 1""",
                (telefone,),
            )
            row = cur.fetchone()
            return row["cnpj"] if row else None
    except Exception:
        return None


def registrar_mensagem_whatsapp(
    telefone: str, direcao: str, corpo: str, cnpj: Optional[str] = None,
    status: str = "recebida", twilio_sid: Optional[str] = None,
    organizacao_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Grava uma mensagem (enviada ou recebida) no historico de WhatsApp.
    Se cnpj nao vier informado, reusa o da conversa (se ja resolvido antes)
    ou tenta resolver pelo telefone agora."""
    if not cnpj:
        cnpj = _cnpj_da_conversa(telefone) or buscar_empresa_por_telefone(telefone)
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO whatsapp_mensagens
               (organizacao_id, cnpj, telefone, direcao, corpo, status, twilio_sid)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id, criado_em""",
            (organizacao_id, cnpj, telefone, direcao, corpo, status, twilio_sid),
        )
        row = cur.fetchone()
        return {"id": row["id"], "criado_em": row["criado_em"], "cnpj": cnpj}


def listar_conversas_whatsapp(organizacao_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Uma linha por numero de telefone, com a ultima mensagem da conversa e
    quantas mensagens recebidas ainda nao foram lidas. Ordenado pela mais
    recente primeiro."""
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "whatsapp_mensagens"):
                return []
            cur.execute(
                """
                SELECT DISTINCT ON (w.telefone)
                    w.telefone, w.cnpj,
                    COALESCE(e."RAZAO_SOCIAL", '') AS razao_social,
                    w.corpo AS ultima_mensagem, w.direcao AS ultima_direcao,
                    w.criado_em AS ultima_em
                FROM whatsapp_mensagens w
                LEFT JOIN dados_empresas e ON e."CNPJ_COMPLETO" = w.cnpj
                WHERE (%s::int IS NULL OR w.organizacao_id = %s)
                ORDER BY w.telefone, w.criado_em DESC
                """,
                (organizacao_id, organizacao_id),
            )
            conversas = cur.fetchall()
            cur.execute(
                """SELECT telefone, COUNT(*) AS nao_lidas FROM whatsapp_mensagens
                   WHERE direcao = 'entrada' AND lida = FALSE
                     AND (%s::int IS NULL OR organizacao_id = %s)
                   GROUP BY telefone""",
                (organizacao_id, organizacao_id),
            )
            nao_lidas = {r["telefone"]: r["nao_lidas"] for r in cur.fetchall()}
            for c in conversas:
                c["nao_lidas"] = nao_lidas.get(c["telefone"], 0)
            conversas.sort(key=lambda c: c["ultima_em"], reverse=True)
            return conversas
    except Exception as e:
        log.warning(f"listar_conversas_whatsapp falhou, retornando lista vazia: {e}")
        return []


def listar_mensagens_whatsapp(
    telefone: str, marcar_como_lida: bool = True, organizacao_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Historico completo (mais antiga -> mais recente) de uma conversa. Marca
    as mensagens recebidas dessa conversa como lidas ao abrir (comportamento
    padrao de caixa de entrada).

    A conversa e' DA EMPRESA: cada uma tem o proprio numero de WhatsApp, e a
    mensagem recebida e' endereçada pela empresa dona do numero de destino
    (ver org_do_numero). Quem esta' na NRA nao ve a caixa de entrada da SYVP.
    organizacao_id=None so' aparece em rotina interna que varre tudo."""
    try:
        with get_db_cursor() as cur:
            if not _tabela_existe(cur, "whatsapp_mensagens"):
                return []
            cur.execute(
                """SELECT id, cnpj, telefone, direcao, corpo, status, criado_em, lida
                   FROM whatsapp_mensagens
                   WHERE telefone = %s AND (%s::int IS NULL OR organizacao_id = %s)
                   ORDER BY criado_em ASC""",
                (telefone, organizacao_id, organizacao_id),
            )
            mensagens = cur.fetchall()
            if marcar_como_lida:
                cur.execute(
                    """UPDATE whatsapp_mensagens SET lida = TRUE
                       WHERE telefone = %s AND direcao = 'entrada' AND lida = FALSE
                         AND (%s::int IS NULL OR organizacao_id = %s)""",
                    (telefone, organizacao_id, organizacao_id),
                )
            return mensagens
    except Exception as e:
        log.warning(f"listar_mensagens_whatsapp falhou, retornando lista vazia: {e}")
        return []


# ==================== LOTES DE LEADS ====================

def create_lote_db(organizacao_id: int, nome: str, filtros: Dict, total_encontrado: int, criado_por: Optional[str]) -> Dict[str, Any]:
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO lotes_leads (organizacao_id, nome, filtros, total_encontrado, criado_por)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (organizacao_id, nome, json.dumps(filtros or {}), total_encontrado, criado_por)
        )
        row = cur.fetchone()
        if row and row.get("filtros") and isinstance(row["filtros"], str):
            try: row["filtros"] = json.loads(row["filtros"])
            except: pass
        return row

def get_lote_db(lote_id: int, organizacao_id: int) -> Optional[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM lotes_leads WHERE id = %s AND organizacao_id = %s", (lote_id, organizacao_id))
        row = cur.fetchone()
        if row and row.get("filtros") and isinstance(row["filtros"], str):
            try: row["filtros"] = json.loads(row["filtros"])
            except: pass
        return row

def listar_lotes_db(organizacao_id: int) -> List[Dict[str, Any]]:
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM lotes_leads WHERE organizacao_id = %s ORDER BY created_at DESC", (organizacao_id,))
        rows = cur.fetchall()
        for r in rows:
            if r and r.get("filtros") and isinstance(r["filtros"], str):
                try: r["filtros"] = json.loads(r["filtros"])
                except: pass
        return rows

def delete_lote_db(lote_id: int, organizacao_id: int) -> bool:
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM lotes_leads WHERE id = %s AND organizacao_id = %s", (lote_id, organizacao_id))
        return cur.rowcount > 0
