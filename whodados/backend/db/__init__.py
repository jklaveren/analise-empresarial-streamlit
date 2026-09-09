"""DB Module."""
from .service import (
    create_user_record, get_user_by_username, get_user_by_email, get_user_by_username_or_email,
    create_audit_log, record_login_attempt, is_account_locked, get_audit_logs,
    create_or_update_crm, get_crm_by_cnpj, get_crm_all,
    create_template, get_template, get_all_templates, update_template, delete_template, get_templates_by_categoria,
    set_template_imagem, get_template_imagem, clear_template_imagem,
    salvar_enriquecimento, listar_enriquecimento, remover_enriquecimento,
    create_campanha, get_campanha, get_all_campanhas, update_campanha_status,
    create_email_enviado, update_email_enviado, get_emails_enviados_by_campanha,
    create_notificacao, get_notificacoes, mark_notificacao_lida,
    # Password reset
    create_password_reset_token, get_password_reset_token, mark_password_reset_token_used, update_user_password,
    # Monitor de emails (follow-up com semaforo)
    get_emails_for_monitor, get_monitor_stats, get_emails_vermelhos_para_followup, marcar_email_aberto,
    # Empresas (dados da Receita Federal, via pipeline de ETL)
    listar_empresas_db, get_empresa_by_cnpj_db, get_metricas_db,
)
__all__ = [
    "create_user_record", "get_user_by_username", "get_user_by_email", "get_user_by_username_or_email",
    "create_or_update_crm", "get_crm_by_cnpj", "get_crm_all",
    "create_template", "get_template", "get_all_templates", "update_template", "delete_template", "get_templates_by_categoria",
    "set_template_imagem", "get_template_imagem", "clear_template_imagem",
    "salvar_enriquecimento", "listar_enriquecimento", "remover_enriquecimento",
    "create_campanha", "get_campanha", "get_all_campanhas", "update_campanha_status",
    "create_email_enviado", "update_email_enviado", "get_emails_enviados_by_campanha",
    "create_notificacao", "get_notificacoes", "mark_notificacao_lida",
    # Password reset
    "create_password_reset_token", "get_password_reset_token", "mark_password_reset_token_used", "update_user_password",
    # Monitor de emails (follow-up com semaforo)
    "get_emails_for_monitor", "get_monitor_stats", "get_emails_vermelhos_para_followup", "marcar_email_aberto",
    # Empresas (dados da Receita Federal, via pipeline de ETL)
    "listar_empresas_db", "get_empresa_by_cnpj_db", "get_metricas_db",
]
