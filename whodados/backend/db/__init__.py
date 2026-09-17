"""DB Module."""
from .service import (
    create_user_record, get_user_by_username, get_user_by_email, get_user_by_username_or_email,
    create_audit_log, record_login_attempt, is_account_locked, get_audit_logs,
    create_or_update_crm, get_crm_by_cnpj, get_crm_all,
    classificar_base, estatisticas_classificacao, listar_crm_classificados, classificar_empresa,
    create_template, get_template, get_all_templates, update_template, delete_template, get_templates_by_categoria,
    set_template_imagem, get_template_imagem, clear_template_imagem,
    salvar_enriquecimento, listar_enriquecimento, remover_enriquecimento,
    create_campanha, get_campanha, get_all_campanhas, update_campanha_status,
    create_email_enviado, update_email_enviado, get_emails_enviados_by_campanha,
    create_notificacao, get_notificacoes, mark_notificacao_lida, contar_notificacoes_nao_lidas,
    # Password reset
    create_password_reset_token, get_password_reset_token, mark_password_reset_token_used, update_user_password,
    # Monitor de emails (follow-up com semaforo)
    get_emails_for_monitor, get_monitor_stats, get_emails_vermelhos_para_followup, marcar_email_aberto,
    # Empresas (dados da Receita Federal, via pipeline de ETL)
    listar_empresas_db, contar_empresas_db, get_empresa_by_cnpj_db, get_metricas_db,
    atualizar_potencial_empresas,
    org_escopo_base, listar_carteira_db, contar_carteira_db, get_carteira_by_cnpj,
    categorias_da_carteira, salvar_na_carteira, remover_da_carteira,
    seed_default_templates, get_pipeline_metadata,
    get_app_config, set_app_config, get_sla_config, set_sla_config,
    list_all_users, update_user_flags, delete_user, update_user_email,
    # Multi-empresa (organizacoes)
    listar_organizacoes_do_usuario, usuario_tem_acesso_org, listar_todas_organizacoes,
    definir_acesso_usuario_orgs, get_orgs_do_user_id, criar_organizacao, renomear_organizacao,
    get_papel_usuario_org, definir_papel_usuario_org,
    get_org_smtp_config, set_org_smtp_config,
    get_usuario_smtp_config, set_usuario_smtp_config, set_org_logo, get_org_logo,
    # WhatsApp (Twilio)
    registrar_mensagem_whatsapp, listar_conversas_whatsapp, listar_mensagens_whatsapp,
    buscar_empresa_por_telefone,
    # Campanhas em lote
    cnpjs_ja_contatados_campanha, registrar_envio_campanha, contar_envios_campanha,
    listar_campanhas_pendentes,
    # CRM: atividades/tarefas
    listar_usuarios_da_org, criar_atividade_crm, listar_atividades_crm,
    contar_atividades_pendentes, concluir_atividade_crm, deletar_atividade_crm,
    listar_todas_atividades, mover_atividade_crm,
    criar_gasto, listar_gastos, resumo_gastos, remover_gasto, restaurar_gasto, atualizar_gasto,
    salvar_anexo_atividade, listar_anexos_atividade, get_anexo_atividade,
    deletar_anexo_atividade, contar_anexos_por_atividade,
    atribuir_atividade,
    registrar_historico_atividade, listar_historico_atividade,
    atualizar_prazo_atividade, get_status_atividade,
    # Descadastro de e-mail (LGPD/opt-out)
    email_esta_descadastrado, descadastrar_email,
    buscar_socios_principais, buscar_empresas_rapido,
)
from .analytics import (
    analytics_resumo, analytics_por_cidade, analytics_por_setor, analytics_por_porte,
    analytics_top_empresas, analytics_socios_ranking, analytics_socio_detalhe,
    analytics_opcoes_filtro,
)
__all__ = [
    "create_user_record", "get_user_by_username", "get_user_by_email", "get_user_by_username_or_email",
    "create_or_update_crm", "get_crm_by_cnpj", "get_crm_all",
    "classificar_base", "estatisticas_classificacao", "listar_crm_classificados", "classificar_empresa",
    "create_template", "get_template", "get_all_templates", "update_template", "delete_template", "get_templates_by_categoria",
    "set_template_imagem", "get_template_imagem", "clear_template_imagem",
    "salvar_enriquecimento", "listar_enriquecimento", "remover_enriquecimento",
    "create_campanha", "get_campanha", "get_all_campanhas", "update_campanha_status",
    "create_email_enviado", "update_email_enviado", "get_emails_enviados_by_campanha",
    "create_notificacao", "get_notificacoes", "mark_notificacao_lida", "contar_notificacoes_nao_lidas",
    # Password reset
    "create_password_reset_token", "get_password_reset_token", "mark_password_reset_token_used", "update_user_password",
    # Monitor de emails (follow-up com semaforo)
    "get_emails_for_monitor", "get_monitor_stats", "get_emails_vermelhos_para_followup", "marcar_email_aberto",
    # Empresas (dados da Receita Federal, via pipeline de ETL)
    "listar_empresas_db", "contar_empresas_db", "get_empresa_by_cnpj_db", "get_metricas_db",
    "atualizar_potencial_empresas",
    "org_escopo_base", "listar_carteira_db", "contar_carteira_db", "get_carteira_by_cnpj",
    "categorias_da_carteira", "salvar_na_carteira", "remover_da_carteira",
    "seed_default_templates", "get_pipeline_metadata",
    "get_app_config", "set_app_config", "get_sla_config", "set_sla_config",
    "list_all_users", "update_user_flags", "delete_user", "update_user_email",
    # Multi-empresa (organizacoes)
    "listar_organizacoes_do_usuario", "usuario_tem_acesso_org", "listar_todas_organizacoes",
    "definir_acesso_usuario_orgs", "get_orgs_do_user_id", "criar_organizacao", "renomear_organizacao",
    "get_papel_usuario_org", "definir_papel_usuario_org",
    "get_org_smtp_config", "set_org_smtp_config",
    "get_usuario_smtp_config", "set_usuario_smtp_config", "set_org_logo", "get_org_logo",
    # WhatsApp (Twilio)
    "registrar_mensagem_whatsapp", "listar_conversas_whatsapp", "listar_mensagens_whatsapp",
    "buscar_empresa_por_telefone",
    # CRM: atividades/tarefas
    "listar_usuarios_da_org", "criar_atividade_crm", "listar_atividades_crm",
    "contar_atividades_pendentes", "concluir_atividade_crm", "deletar_atividade_crm",
    "listar_todas_atividades", "mover_atividade_crm",
    "criar_gasto", "listar_gastos", "resumo_gastos", "remover_gasto", "restaurar_gasto", "atualizar_gasto",
    "salvar_anexo_atividade", "listar_anexos_atividade", "get_anexo_atividade",
    "deletar_anexo_atividade", "contar_anexos_por_atividade",
    "atribuir_atividade",
    "registrar_historico_atividade", "listar_historico_atividade",
    "atualizar_prazo_atividade", "get_status_atividade",
    "email_esta_descadastrado", "descadastrar_email", "buscar_socios_principais", "buscar_empresas_rapido",
    # Analytics (agregacoes sobre dados_empresas / dados_socios)
    "analytics_resumo", "analytics_por_cidade", "analytics_por_setor", "analytics_por_porte",
    "analytics_top_empresas", "analytics_socios_ranking", "analytics_socio_detalhe",
    "analytics_opcoes_filtro",
]
