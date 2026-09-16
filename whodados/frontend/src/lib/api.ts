const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setToken(token: string): void {
  localStorage.setItem("token", token);
}

export function removeToken(): void {
  localStorage.removeItem("token");
}

// Empresa (organizacao) ativa -- enviada no header X-Org-Id em toda chamada, e' o
// que isola CRM/campanhas/templates/monitor por empresa (NRA / SYVP).
export function getActiveOrgId(): number | null {
  if (typeof window === "undefined") return null;
  const v = localStorage.getItem("org_id");
  return v ? Number(v) : null;
}

export function setActiveOrgId(id: number): void {
  localStorage.setItem("org_id", String(id));
}

export function clearActiveOrgId(): void {
  localStorage.removeItem("org_id");
}

/**
 * Rotas que legitimamente nao tem empresa: o login e a propria listagem de
 * empresas (que e' o que DEFINE a empresa ativa). Todo o resto e' dado de
 * uma empresa e nao pode sair daqui sem dizer qual.
 */
const ROTAS_SEM_EMPRESA = ["/api/v1/auth/", "/api/v1/organizacoes", "/api/v1/descadastro"];

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgId = getActiveOrgId();
  if (orgId) headers["X-Org-Id"] = String(orgId);
  else if (token && !ROTAS_SEM_EMPRESA.some(r => path.startsWith(r))) {
    // Sem isto, a requisicao ia sem X-Org-Id e o backend caia na primeira
    // empresa do usuario -- uma tarefa criada "na SYVP" nascia na NRA.
    throw new ApiError(400, "Empresa ativa ainda não carregou. Recarregue a página.");
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Erro desconhecido" }));
    if (res.status === 401 && typeof window !== "undefined") {
      removeToken();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login?expirado=1";
      }
    }
    throw new ApiError(res.status, body.detail || "Erro na API");
  }
  return res.json();
}

// Auth
export async function login(username: string, password: string, rememberMe = false) {
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);
  form.append("remember_me", rememberMe ? "true" : "false");
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Erro de login" }));
    throw new ApiError(res.status, body.detail || "Credenciais invalidas");
  }
  return res.json();
}

export interface MeInfo {
  username: string;
  is_admin: boolean;
  email: string | null;
}

export async function getMe(): Promise<MeInfo> {
  return request("/api/v1/auth/me");
}

// ==================== ORGANIZACOES (MULTI-EMPRESA) ====================

export interface Organizacao {
  id: number;
  nome: string;
  slug: string;
  ativo: boolean;
  papel?: "admin" | "membro" | "visitante";
  /** De onde vem a base de prospecção: "receita" (base pública) ou "carteira" (lista própria). */
  escopo_base?: "receita" | "carteira";
}

/** Empresas que o usuario logado pode operar (para o seletor de empresa ativa). */
export async function listarOrganizacoes(): Promise<Organizacao[]> {
  return request("/api/v1/organizacoes");
}

// Password Reset
export async function forgotPassword(identifier: string) {
  return request("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ username: identifier }),
  });
}

export async function validateResetToken(token: string) {
  return request(`/api/v1/auth/validate-reset-token/${token}`);
}

export async function resetPassword(token: string, novaSenha: string) {
  return request("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, nova_senha: novaSenha }),
  });
}

// Empresas
export type PotencialTier = "alto" | "medio" | "baixo";

export interface EmpresaItem {
  cnpj_completo: string;
  razao_social: string;
  nome_fantasia: string | null;
  municipio: string | null;
  cnae_principal: string | null;
  cnae_descricao?: string | null;
  capital_social: number;
  divida_total: number;
  porte_nome: string | null;
  data_fundacao?: string | null;
  potencial_score: number;
  potencial_tier: PotencialTier;
}

/** Filtros do funil de empresas (aplicados no servidor). */
export interface EmpresaFiltros {
  cidade?: string[];
  cnae?: string[];
  porte?: string[];
  busca?: string;
  divida_min?: number;
  divida_max?: number;
  capital_min?: number;
  capital_max?: number;
  fundacao_de?: string;   // YYYY-MM-DD
  fundacao_ate?: string;  // YYYY-MM-DD
  incluir_inativas?: boolean;
  potencial?: PotencialTier[];
  ordenar_por?: "razao_social" | "potencial";
}

function empresaFiltrosToQuery(f: EmpresaFiltros = {}): URLSearchParams {
  const p = new URLSearchParams();
  (f.cidade ?? []).forEach(v => p.append("cidade", v));
  (f.cnae ?? []).forEach(v => p.append("cnae", v));
  (f.porte ?? []).forEach(v => p.append("porte", v));
  if (f.busca) p.append("busca", f.busca);
  if (f.divida_min != null) p.append("divida_min", String(f.divida_min));
  if (f.divida_max != null) p.append("divida_max", String(f.divida_max));
  if (f.capital_min != null) p.append("capital_min", String(f.capital_min));
  if (f.capital_max != null) p.append("capital_max", String(f.capital_max));
  if (f.fundacao_de) p.append("fundacao_de", f.fundacao_de);
  if (f.fundacao_ate) p.append("fundacao_ate", f.fundacao_ate);
  if (f.incluir_inativas === false) p.append("incluir_inativas", "false");
  (f.potencial ?? []).forEach(v => p.append("potencial", v));
  if (f.ordenar_por) p.append("ordenar_por", f.ordenar_por);
  return p;
}

/** Uma pagina de empresas para o filtro atual (funil server-side). */
export async function listarEmpresas(filtros: EmpresaFiltros = {}, limit = 100, offset = 0): Promise<EmpresaItem[]> {
  const p = empresaFiltrosToQuery(filtros);
  p.append("limit", String(limit));
  p.append("offset", String(offset));
  return request(`/api/v1/empresas?${p}`);
}

/** Total de empresas que batem no filtro atual (contador do funil). */
export async function contarEmpresas(filtros: EmpresaFiltros = {}): Promise<{ total: number }> {
  return request(`/api/v1/empresas/count?${empresaFiltrosToQuery(filtros)}`);
}

export interface Socio {
  nome_socio: string;
  cpf_cnpj_socio: string | null;
  qualif_socio: string | null;
}

export interface CRMRecord {
  id: number;
  cnpj: string;
  status: string | null;
  notas: string | null;
}

export interface EmpresaDetalhe extends EmpresaItem {
  data_fundacao: string | null;
  contato_fone: string | null;
  socios: Socio[];
  crm: CRMRecord | null;
}

export async function getEmpresaDetalhe(cnpj: string): Promise<EmpresaDetalhe> {
  return request(`/api/v1/empresas/${encodeURIComponent(cnpj)}`);
}

export async function atualizarCrm(cnpj: string, data: { status?: string; notas?: string; classificacao?: string; motivo?: string; parceiro?: boolean }) {
  return request(`/api/v1/crm/${encodeURIComponent(cnpj)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ==================== CRM (KANBAN) ====================

export type CrmStatus = "novo" | "em_contato" | "negociando" | "convertido" | "descartado";
export type CrmClassificacao = "perfil_ideal" | "perfil_possivel" | "fora_perfil" | "parceiro" | "";

export interface CrmKanbanRecord {
  id: number;
  cnpj: string;
  status: CrmStatus;
  notas: string | null;
  criado_por?: string | null;
  data_atualizacao?: string | null;
  classificacao?: string | null;
  motivo?: string | null;
  parceiro?: boolean;
  atividades_pendentes?: number;
}

export type CrmKanban = Record<CrmStatus, CrmKanbanRecord[]>;

export async function listarCrmKanban(): Promise<CrmKanban> {
  return request("/api/v1/crm");
}

// ==================== CRM: ATIVIDADES/TAREFAS ====================

export interface UsuarioOrg {
  id: number;
  username: string;
}

export type StatusAtividade = "pendente" | "em_andamento" | "concluida";

export interface PreviewEmail {
  assunto: string;
  corpo_html: string;
  corpo_texto: string;
  template_usado: string;
  categoria_cnae: string;
  variaveis: Record<string, string>;
  destinatario: string;
  empresa: string;
  cnpj: string;
}

/**
 * E-mail montado exatamente como vai ser enviado (variaveis substituidas,
 * assinatura e rodape de descadastro incluidos). Sem cnpj, o backend usa uma
 * empresa da base como amostra.
 */
export async function previewTemplate(templateId: number, cnpj?: string): Promise<PreviewEmail> {
  return request(`/api/v1/templates/${templateId}/preview`, {
    method: "POST",
    body: JSON.stringify({ cnpj: cnpj || "" }),
  });
}

/** Só o número de não lidas, para o badge do menu. */
export async function contarNotificacoesNaoLidas(): Promise<{ total: number }> {
  return request("/api/v1/notificacoes/nao-lidas");
}

// ==================== GASTOS ====================

export interface Gasto {
  id: number;
  organizacao_id: number;
  descricao: string;
  valor: number;
  data: string;
  categoria: string;
  forma_pagamento: string | null;
  observacao: string | null;
  criado_por: string | null;
  criado_em: string;
  /** Preenchido = excluído (fica fora da lista e do total, mas não some). */
  removido_em: string | null;
  removido_por: string | null;
}

export interface ResumoGastos {
  total: number;
  quantidade: number;
  por_categoria: { categoria: string; total: number; quantidade: number }[];
}

export interface NovoGasto {
  descricao: string;
  valor: number;
  data?: string;
  categoria?: string;
  forma_pagamento?: string;
  observacao?: string;
}

export async function listarGastos(params?: {
  de?: string; ate?: string; categoria?: string; incluir_removidos?: boolean;
}): Promise<Gasto[]> {
  const q = new URLSearchParams();
  if (params?.de) q.set("de", params.de);
  if (params?.ate) q.set("ate", params.ate);
  if (params?.categoria) q.set("categoria", params.categoria);
  if (params?.incluir_removidos) q.set("incluir_removidos", "true");
  const qs = q.toString();
  return request(`/api/v1/gastos${qs ? `?${qs}` : ""}`);
}

export async function resumoGastos(de?: string, ate?: string): Promise<ResumoGastos> {
  const q = new URLSearchParams();
  if (de) q.set("de", de);
  if (ate) q.set("ate", ate);
  const qs = q.toString();
  return request(`/api/v1/gastos/resumo${qs ? `?${qs}` : ""}`);
}

export async function listarCategoriasGasto(): Promise<string[]> {
  return request("/api/v1/gastos/categorias");
}

export async function criarGasto(gasto: NovoGasto): Promise<Gasto> {
  return request("/api/v1/gastos", { method: "POST", body: JSON.stringify(gasto) });
}

/** Exclusão lógica: sai da lista e do total, mas o registro fica. */
export async function removerGasto(id: number) {
  return request(`/api/v1/gastos/${id}`, { method: "DELETE" });
}

export async function restaurarGasto(id: number) {
  return request(`/api/v1/gastos/${id}/restaurar`, { method: "POST" });
}

export interface AnexoAtividade {
  id: number;
  atividade_id: number;
  nome: string;
  mime: string | null;
  tamanho: number | null;
  enviado_por: string | null;
  criado_em: string;
}

/** Passa a tarefa pra outra pessoa (notifica quem recebe). null tira o responsável. */
export async function atribuirAtividade(id: number, responsavelUserId: number | null, titulo?: string) {
  return request(`/api/v1/crm/atividades/${id}/responsavel`, {
    method: "POST",
    body: JSON.stringify({ responsavel_user_id: responsavelUserId, titulo }),
  });
}

export async function listarAnexosAtividade(atividadeId: number): Promise<AnexoAtividade[]> {
  return request(`/api/v1/crm/atividades/${atividadeId}/anexos`);
}

export async function anexarArquivoAtividade(atividadeId: number, file: File): Promise<AnexoAtividade> {
  const form = new FormData();
  form.append("arquivo", file);
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgId = getActiveOrgId();
  if (orgId) headers["X-Org-Id"] = String(orgId);
  const res = await fetch(`${API_URL}/api/v1/crm/atividades/${atividadeId}/anexos`, {
    method: "POST", headers, body: form,
  });
  if (!res.ok) {
    const b = await res.json().catch(() => ({ detail: "Erro" }));
    throw new ApiError(res.status, b.detail || "Erro ao anexar arquivo");
  }
  return res.json();
}

export async function removerAnexoAtividade(anexoId: number) {
  return request(`/api/v1/crm/anexos/${anexoId}`, { method: "DELETE" });
}

/**
 * Baixa o anexo como blob e devolve uma URL local pra abrir ou salvar.
 * Anexo nao e' publico -- so' sai do backend com token, entao nao da' pra
 * apontar um <a href> direto pra API. Quem chamar precisa dar
 * URL.revokeObjectURL depois pra nao segurar o arquivo em memoria.
 */
export async function baixarAnexoAtividade(anexoId: number): Promise<{ url: string; tipo: string }> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgId = getActiveOrgId();
  if (orgId) headers["X-Org-Id"] = String(orgId);
  const res = await fetch(`${API_URL}/api/v1/crm/anexos/${anexoId}`, { headers });
  if (!res.ok) throw new ApiError(res.status, "Não consegui abrir o anexo");
  const blob = await res.blob();
  return { url: URL.createObjectURL(blob), tipo: blob.type };
}

export interface HistoricoAtividade {
  id: number;
  atividade_id: number;
  /** comentario = escrito pelo usuario; status/prazo = registrado automaticamente. */
  tipo: "comentario" | "status" | "prazo" | "anexo" | "anexo_removido" | "responsavel";
  texto: string | null;
  de: string | null;
  para: string | null;
  autor: string | null;
  criado_em: string;
}

export async function listarHistoricoAtividade(id: number): Promise<HistoricoAtividade[]> {
  return request(`/api/v1/crm/atividades/${id}/historico`);
}

export async function comentarAtividade(id: number, texto: string): Promise<HistoricoAtividade> {
  return request(`/api/v1/crm/atividades/${id}/comentario`, {
    method: "POST",
    body: JSON.stringify({ texto }),
  });
}

/** prazo vazio remove o prazo. A troca fica registrada no historico. */
export async function alterarPrazoAtividade(id: number, prazo: string) {
  return request(`/api/v1/crm/atividades/${id}/prazo`, {
    method: "POST",
    body: JSON.stringify({ prazo }),
  });
}

export type SemaforoAtividade = "verde" | "amarelo" | "vermelho" | "cinza";

export interface AtividadeCrm {
  id: number;
  cnpj: string | null;
  titulo: string;
  tipo: string;
  descricao: string | null;
  responsavel_user_id: number | null;
  responsavel_username?: string | null;
  razao_social?: string;
  prazo: string | null;
  status: StatusAtividade;
  criado_por: string | null;
  criado_em: string;
  concluido_em: string | null;
  /** Cor de acompanhamento (calculada no banco, igual ao monitor de e-mails). */
  semaforo: SemaforoAtividade;
  dias_aberta: number | null;
  /** Negativo = atrasada. null quando a atividade nao tem prazo. */
  dias_para_prazo: number | null;
  /** Quantos eventos de acompanhamento (comentarios + mudancas). */
  n_historico?: number;
  n_anexos?: number;
}

/** Todas as atividades da organizacao (board agregado, tipo Trello). */
export function listarTodasAtividades(): Promise<AtividadeCrm[]> {
  return request("/api/v1/crm/atividades");
}

export function moverAtividadeCrm(id: number, status: StatusAtividade): Promise<{ ok: boolean }> {
  return request(`/api/v1/crm/atividades/${id}/mover`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export function listarUsuariosOrg(): Promise<UsuarioOrg[]> {
  return request("/api/v1/crm/usuarios");
}

export function listarAtividadesCrm(cnpj: string): Promise<AtividadeCrm[]> {
  return request(`/api/v1/crm/${encodeURIComponent(cnpj)}/atividades`);
}

export function criarAtividadeCrm(cnpj: string, data: {
  titulo: string; tipo?: string; descricao?: string; responsavel_user_id?: number; prazo?: string;
}): Promise<AtividadeCrm> {
  return request(`/api/v1/crm/${encodeURIComponent(cnpj)}/atividades`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface EmpresaBusca {
  cnpj_completo: string;
  razao_social: string;
  municipio: string;
}

/** Busca rapida por nome/CNPJ, pra vincular atividade a uma empresa. */
export function buscarEmpresaRapido(q: string): Promise<EmpresaBusca[]> {
  return request(`/api/v1/crm/buscar-empresa?q=${encodeURIComponent(q)}`);
}

/** Cria atividade direto do board. Empresa (cnpj) e' opcional. */
export function criarAtividadeAvulsa(data: {
  titulo: string; tipo?: string; descricao?: string;
  responsavel_user_id?: number; prazo?: string; cnpj?: string;
}): Promise<AtividadeCrm> {
  return request("/api/v1/crm/atividades", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function concluirAtividadeCrm(id: number): Promise<{ ok: boolean }> {
  return request(`/api/v1/crm/atividades/${id}/concluir`, { method: "POST" });
}

export function deletarAtividadeCrm(id: number): Promise<{ ok: boolean }> {
  return request(`/api/v1/crm/atividades/${id}`, { method: "DELETE" });
}

// ==================== CLASSIFICACAO DE PERFIL ====================

export interface CrmClassificado {
  cnpj: string;
  classificacao: string | null;
  motivo: string | null;
  status: string | null;
  parceiro: boolean;
  data_atualizacao: string | null;
  notas: string | null;
  razao_social: string;
  capital_social: number;
  email: string;
  contato_fone: string;
  municipio: string;
}

export interface ClassificacaoEstatisticas {
  perfil_ideal: number;
  perfil_possivel: number;
  fora_perfil: number;
  parceiro: number;
  sem_classificacao: number;
  total_crm: number;
}

/** Roda a regra de perfil na base inteira (lote). Retorna contadores. */
export async function classificarBase(limite?: number): Promise<{ ok: boolean; processadas: number; totais: Record<string, number>; erro?: string }> {
  const q = limite ? `?limite=${limite}` : "";
  return request(`/api/v1/crm/classificar${q}`, { method: "POST" });
}

export async function listarCrmClassificados(filtro?: CrmClassificacao | "sem_classificacao"): Promise<CrmClassificado[]> {
  const q = filtro ? `?filtro=${filtro}` : "";
  return request(`/api/v1/crm/classificacao${q}`);
}

export async function getCrmClassificacaoEstatisticas(): Promise<ClassificacaoEstatisticas> {
  return request("/api/v1/crm/classificacao/estatisticas");
}

export async function getMetricas() {
  return request("/api/v1/dashboard/metricas");
}

// ==================== MONITOR DE EMAILS (FOLLOW-UP COM SEMAFORO) ====================

export interface MonitorEmail {
  id: number;
  campaign_id: number | null;
  cnpj: string;
  email_destino: string;
  assunto: string | null;
  status: string;
  erro: string | null;
  sequencia_passo: number;
  enviado_em: string | null;
  aberto_em: string | null;
  criado_em: string;
  campanha_nome: string | null;
  dias_desde_envio: number;
  semaforo_status: "verde" | "amarelo" | "vermelho" | "cinza";
  razao_social: string | null;
  nome_fantasia: string | null;
}

export interface MonitorStats {
  total_enviados: number;
  verde: number;
  amarelo: number;
  vermelho: number;
  cinza: number;
  total: number;
}

export async function listarEmailsMonitor(
  campaignId?: number,
  semaforo?: string,
  diasSla = 7,
  limit = 200,
  offset = 0,
): Promise<MonitorEmail[]> {
  const params = new URLSearchParams();
  if (campaignId) params.append("campaign_id", String(campaignId));
  if (semaforo) params.append("semaforo", semaforo);
  params.append("dias_sla", String(diasSla));
  params.append("limit", String(limit));
  params.append("offset", String(offset));
  return request(`/api/v1/emails-enviados/monitor?${params}`);
}

export async function getMonitorStats(diasSla = 7): Promise<MonitorStats> {
  return request(`/api/v1/emails-enviados/monitor/stats?dias_sla=${diasSla}`);
}

export async function getEmailsVermelhos(limite = 50): Promise<MonitorEmail[]> {
  return request(`/api/v1/emails-enviados/monitor/vermelhos?limite=${limite}`);
}

// ==================== CAMPANHAS / TEMPLATES ====================

export interface Template {
  id?: number;
  nome: string;
  assunto: string;
  corpo_html: string;
  corpo_texto?: string | null;
  categoria_cnae?: string;
  imagem_url?: string | null;
  tem_imagem?: boolean;
  created_at?: string;
  updated_at?: string;
  criado_por?: string;
}

export interface Campanha {
  id?: number;
  nome: string;
  template_id: number | null;
  filtros: Record<string, any>;
  status?: string;
  total_destinatarios?: number;
  enviados?: number;
  erros?: number;
  eh_sequencia?: boolean;
  created_at?: string;
  created_by?: string;
  canal?: "email" | "whatsapp";
  mensagem?: string | null;
  tamanho_lote?: number | null;
  repetir_ate?: string | null;
  ultimo_lote_em?: string | null;
  ja_contatados?: number;
}

export async function listarTemplates(): Promise<Template[]> {
  return request("/api/v1/templates");
}

export async function criarTemplate(data: Template): Promise<Template> {
  return request("/api/v1/templates", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function atualizarTemplate(id: number, data: Partial<Template>): Promise<Template> {
  return request(`/api/v1/templates/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deletarTemplate(id: number): Promise<{ ok: boolean }> {
  return request(`/api/v1/templates/${id}`, { method: "DELETE" });
}

/** Envia um e-mail de teste deste template para 1 endereco. Se `cnpj` for
 *  informado, a personalizacao usa os dados REAIS daquela empresa. */
export async function enviarTesteTemplate(id: number, para: string, cnpj?: string): Promise<{ sucesso: boolean; simulado?: boolean; erro?: string }> {
  return request(`/api/v1/templates/${id}/test-send`, {
    method: "POST",
    body: JSON.stringify({ para, cnpj }),
  });
}

/** Envia/atualiza a imagem (card) de um template. Referenciada no corpo via {{imagem}}. */
export async function uploadTemplateImagem(id: number, file: File): Promise<Template> {
  const form = new FormData();
  form.append("arquivo", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgId = getActiveOrgId();
  if (orgId) headers["X-Org-Id"] = String(orgId);
  const res = await fetch(`${API_URL}/api/v1/templates/${id}/imagem`, { method: "POST", headers, body: form });
  if (!res.ok) {
    const b = await res.json().catch(() => ({ detail: "Erro" }));
    throw new ApiError(res.status, b.detail || "Erro ao enviar imagem");
  }
  return res.json();
}

export async function listarCampanhas(): Promise<Campanha[]> {
  return request("/api/v1/campanhas");
}

export async function criarCampanha(data: Partial<Campanha>): Promise<Campanha> {
  return request("/api/v1/campanhas", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function executarCampanha(id: number): Promise<{ sucessos: number; erros: number; restantes?: number; status?: string }> {
  return request(`/api/v1/campanhas/${id}/executar`, { method: "POST" });
}

export async function deletarCampanha(id: number): Promise<{ ok: boolean }> {
  return request(`/api/v1/campanhas/${id}`, { method: "DELETE" });
}

// ==================== NOTIFICACOES ====================

export interface Notificacao {
  id: number;
  tipo: string;
  titulo: string;
  mensagem: string | null;
  cnpj: string | null;
  user_id: string | null;
  lida: boolean;
  created_at: string;
  organizacao_id: number | null;
  /** Empresa onde a notificação nasceu — sem isso não dá pra ver que caiu no lugar errado. */
  organizacao_nome: string | null;
}

export async function listarNotificacoes(lidas?: boolean): Promise<Notificacao[]> {
  const params = new URLSearchParams();
  if (lidas !== undefined) params.append("lidas", String(lidas));
  const qs = params.toString();
  return request(`/api/v1/notificacoes${qs ? "?" + qs : ""}`);
}

export async function marcarNotificacaoLida(id: number): Promise<{ ok: boolean }> {
  return request(`/api/v1/notificacoes/${id}/ler`, { method: "POST" });
}

// Sobre / status do sistema (aba "Sobre" em Configuracoes)
export interface SistemaStatus {
  mes_referencia_rf: string | null;
  trimestre_pgfn: string | null;
  gerado_em: string | null;
  ultima_sincronizacao: string | null;
  total_matrizes: string | null;
  total_empresas_sincronizadas: string | null;
  total_socios_sincronizados: string | null;
  pipeline_ja_rodou: boolean;
}

export async function getSistemaStatus(): Promise<SistemaStatus> {
  return request<SistemaStatus>("/api/v1/admin/sistema/status");
}

// ==================== CONFIGURACOES: SLA (REGRAS DO MONITOR) ====================

export interface SlaConfig {
  sla_verde_dias: number;
  sla_amarelo_dias: number;
}

export async function getSlaConfig(): Promise<SlaConfig> {
  return request("/api/v1/admin/sla");
}

export async function updateSlaConfig(data: SlaConfig): Promise<SlaConfig> {
  return request("/api/v1/admin/sla", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ==================== CONFIGURACOES: PERFIL/CONTA ====================

export async function trocarMinhaSenha(senhaAtual: string, novaSenha: string): Promise<{ sucesso: boolean; message: string }> {
  return request("/api/v1/auth/me/senha", {
    method: "PUT",
    body: JSON.stringify({ senha_atual: senhaAtual, nova_senha: novaSenha }),
  });
}

// ==================== CONFIGURACOES: USUARIOS ====================

export interface UsuarioAdmin {
  id: number;
  username: string;
  email: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
  organizacao_ids: number[];
}

export async function listarUsuarios(): Promise<UsuarioAdmin[]> {
  return request("/api/v1/admin/usuarios");
}

export async function criarUsuarioAdmin(data: { username: string; password: string; email?: string; is_admin?: boolean; organizacao_ids?: number[] }): Promise<{ username: string }> {
  return request("/api/v1/admin/usuarios", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function definirEmpresasUsuario(userId: number, organizacaoIds: number[]): Promise<{ sucesso: boolean; organizacao_ids: number[] }> {
  return request(`/api/v1/admin/usuarios/${userId}/organizacoes`, {
    method: "PUT",
    body: JSON.stringify({ organizacao_ids: organizacaoIds }),
  });
}

// ==================== ADMIN: EMPRESAS (config de e-mail por empresa) ====================

export interface OrgEmailConfig {
  organizacao_id?: number;
  smtp_host?: string | null;
  smtp_port?: number | null;
  smtp_username?: string | null;
  smtp_use_tls?: boolean;
  email_from?: string | null;
  email_from_name?: string | null;
  assinatura_html?: string | null;
  configurado: boolean;
  tem_logo: boolean;
}

export async function listarOrganizacoesAdmin(): Promise<Organizacao[]> {
  return request("/api/v1/admin/organizacoes");
}

export async function getOrgEmailConfig(orgId: number): Promise<OrgEmailConfig> {
  return request(`/api/v1/admin/organizacoes/${orgId}/smtp`);
}

export async function setOrgEmailConfig(orgId: number, data: Partial<OrgEmailConfig> & { smtp_password?: string }): Promise<OrgEmailConfig> {
  return request(`/api/v1/admin/organizacoes/${orgId}/smtp`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function uploadOrgLogo(orgId: number, file: File): Promise<{ sucesso: boolean; tem_logo: boolean }> {
  const form = new FormData();
  form.append("arquivo", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgActive = getActiveOrgId();
  if (orgActive) headers["X-Org-Id"] = String(orgActive);
  const res = await fetch(`${API_URL}/api/v1/admin/organizacoes/${orgId}/logo`, {
    method: "POST", headers, body: form,
  });
  if (!res.ok) {
    const b = await res.json().catch(() => ({ detail: "Erro" }));
    throw new ApiError(res.status, b.detail || "Erro ao enviar logo");
  }
  return res.json();
}

export async function atualizarUsuarioAdmin(userId: number, data: { is_admin?: boolean; is_active?: boolean; email?: string | null }): Promise<UsuarioAdmin> {
  return request(`/api/v1/admin/usuarios/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function excluirUsuarioAdmin(userId: number): Promise<{ sucesso: boolean; message: string }> {
  return request(`/api/v1/admin/usuarios/${userId}`, { method: "DELETE" });
}

export async function redefinirSenhaUsuarioAdmin(userId: number, novaSenha: string): Promise<{ sucesso: boolean; message: string }> {
  return request(`/api/v1/admin/usuarios/${userId}/redefinir-senha`, {
    method: "POST",
    body: JSON.stringify({ nova_senha: novaSenha }),
  });
}

// ==================== ANALYTICS (telas de analise) ====================

/** Filtros compartilhados por todos os endpoints de analytics. */
export interface AnalyticsFiltros {
  cidade?: string[];
  cnae?: string[];
  porte?: string[];
  divida_min?: number;
  divida_max?: number;
  capital_min?: number;
  capital_max?: number;
  incluir_inativas?: boolean;
}

function filtrosToQuery(f: AnalyticsFiltros = {}): URLSearchParams {
  const p = new URLSearchParams();
  (f.cidade ?? []).forEach(v => p.append("cidade", v));
  (f.cnae ?? []).forEach(v => p.append("cnae", v));
  (f.porte ?? []).forEach(v => p.append("porte", v));
  if (f.divida_min != null) p.append("divida_min", String(f.divida_min));
  if (f.divida_max != null) p.append("divida_max", String(f.divida_max));
  if (f.capital_min != null) p.append("capital_min", String(f.capital_min));
  if (f.capital_max != null) p.append("capital_max", String(f.capital_max));
  if (f.incluir_inativas) p.append("incluir_inativas", "true");
  return p;
}

export interface AnalyticsResumo {
  total_empresas: number;
  divida_total: number;
  capital_total: number;
  divida_media: number;
  capital_medio: number;
  qtd_cidades: number;
  qtd_setores: number;
  qtd_com_divida: number;
  qtd_inativas: number;
  /** false quando o banco ainda nao tem coluna de passivo (ETL legado). */
  tem_dados_divida?: boolean;
}

export interface CidadeAgg {
  cidade: string;
  qtd: number;
  capital_total: number;
  divida_total: number;
}

export interface SetorAgg {
  cnae: string;
  descricao: string;
  qtd: number;
  capital_total: number;
  divida_total: number;
  divida_media: number;
}

export interface PorteAgg {
  porte: string;
  qtd: number;
}

export interface TopEmpresa {
  cnpj_completo: string;
  razao_social: string;
  municipio: string;
  cnae_principal: string;
  cnae_descricao: string;
  porte_nome: string | null;
  capital_social: number;
  divida_total: number;
  /** true quando o banco ainda nao tem passivo (ranking degradou p/ capital). */
  sem_divida?: boolean;
  ordenado_por?: "divida" | "capital";
}

export interface SocioAgg {
  nome_socio: string;
  qtd_empresas: number;
  divida_total: number;
  capital_total: number;
}

export interface SocioEmpresa {
  cnpj_completo: string;
  razao_social: string;
  municipio: string;
  cnae_principal: string;
  cnae_descricao: string;
  capital_social: number;
  divida_total: number;
}

export interface OpcoesFiltro {
  cidades: string[];
  portes: string[];
  cnaes: { codigo: string; descricao: string; qtd: number }[];
}

export function getAnalyticsResumo(f?: AnalyticsFiltros): Promise<AnalyticsResumo> {
  return request(`/api/v1/analytics/resumo?${filtrosToQuery(f)}`);
}

export function getAnalyticsPorCidade(f?: AnalyticsFiltros, limite = 20): Promise<CidadeAgg[]> {
  const p = filtrosToQuery(f); p.append("limite", String(limite));
  return request(`/api/v1/analytics/por-cidade?${p}`);
}

export function getAnalyticsPorSetor(f?: AnalyticsFiltros, limite = 20): Promise<SetorAgg[]> {
  const p = filtrosToQuery(f); p.append("limite", String(limite));
  return request(`/api/v1/analytics/por-setor?${p}`);
}

export function getAnalyticsPorPorte(f?: AnalyticsFiltros): Promise<PorteAgg[]> {
  return request(`/api/v1/analytics/por-porte?${filtrosToQuery(f)}`);
}

export function getAnalyticsTopEmpresas(
  ordenarPor: "divida" | "capital" = "divida", limite = 10, f?: AnalyticsFiltros,
): Promise<TopEmpresa[]> {
  const p = filtrosToQuery(f);
  p.append("ordenar_por", ordenarPor);
  p.append("limite", String(limite));
  return request(`/api/v1/analytics/top-empresas?${p}`);
}

export function getSociosRanking(f?: AnalyticsFiltros, limite = 50): Promise<SocioAgg[]> {
  const p = filtrosToQuery(f); p.append("limite", String(limite));
  return request(`/api/v1/analytics/socios/ranking?${p}`);
}

export function getSocioDetalhe(nome: string): Promise<SocioEmpresa[]> {
  return request(`/api/v1/analytics/socios/detalhe?nome=${encodeURIComponent(nome)}`);
}

export function getOpcoesFiltro(): Promise<OpcoesFiltro> {
  return request("/api/v1/analytics/opcoes-filtro");
}

// ==================== INTEGRACOES (WhatsApp / Twilio) ====================

export interface IntegracaoConfig {
  id: number;
  key: string;
  value: string | null;
  descricao: string | null;
  ativo: boolean;
}

/** Lista as integrações salvas no banco (Brevo/Twilio). */
export async function listarIntegracoes(): Promise<IntegracaoConfig[]> {
  return request("/api/v1/integracoes");
}

/** Salva/atualiza o valor de uma integração. */
export async function salvarIntegracao(key: string, value: string, descricao?: string): Promise<IntegracaoConfig> {
  return request("/api/v1/integracoes", {
    method: "POST",
    body: JSON.stringify({ key, value, descricao }),
  });
}

/** Envia uma mensagem de WhatsApp para um número. */
export async function enviarWhatsApp(
  telefone: string,
  mensagem: string,
  cnpj?: string
): Promise<{ status: string; sid: string; to: string }> {
  return request("/api/v1/integracoes/whatsapp/enviar", {
    method: "POST",
    body: JSON.stringify({ telefone, mensagem, cnpj }),
  });
}

export interface ConversaWhatsApp {
  telefone: string;
  cnpj: string | null;
  razao_social: string;
  ultima_mensagem: string;
  ultima_direcao: "entrada" | "saida";
  ultima_em: string;
  nao_lidas: number;
}

export interface MensagemWhatsApp {
  id: number;
  cnpj: string | null;
  telefone: string;
  direcao: "entrada" | "saida";
  corpo: string;
  status: string;
  criado_em: string;
  lida: boolean;
}

/** Caixa de entrada: uma linha por conversa (numero), mais recente primeiro. */
export async function listarConversasWhatsApp(): Promise<ConversaWhatsApp[]> {
  return request("/api/v1/integracoes/whatsapp/conversas");
}

/** Historico completo de uma conversa (mais antiga -> mais recente). */
export async function listarMensagensWhatsApp(telefone: string): Promise<MensagemWhatsApp[]> {
  return request(`/api/v1/integracoes/whatsapp/conversas/${encodeURIComponent(telefone)}`);
}

// ==================== CONSULTA EM LINGUAGEM NATURAL ====================

export interface FiltroInterpretado {
  cidade: string | null;
  cnae: string | null;
  busca: string | null;
  ordenar_por: "capital_social" | "divida_total" | "nenhum";
  ordem: "asc" | "desc";
  limite: number;
}

export interface EmpresaConsultaNatural {
  cnpj_completo: string;
  razao_social: string;
  nome_fantasia?: string;
  municipio?: string;
  cnae_principal?: string;
  capital_social?: number;
  divida_total?: number;
  porte_nome?: string;
}

export interface ConsultaNaturalResposta {
  pergunta_original: string;
  filtro_interpretado: FiltroInterpretado;
  total_encontrado: number;
  empresas: EmpresaConsultaNatural[];
  resumo_em_texto: string;
}

/** Pergunta em portugues livre -> filtro estruturado (via Claude) -> resultado.
 * O modelo nunca toca o banco: so preenche um filtro validado por Pydantic,
 * que roda pelo mesmo caminho do /empresas normal. */
export async function consultaNatural(pergunta: string): Promise<ConsultaNaturalResposta> {
  return request("/api/v1/empresas/consulta-natural", {
    method: "POST",
    body: JSON.stringify({ pergunta }),
  });
}

// ==================== ENRIQUECIMENTO DE CONTATO (IA, so admin) ====================

export interface ItemEnriquecimento {
  id: number;
  cnpj: string;
  tipo_alvo: string;
  nome_alvo: string | null;
  campo: string;
  valor: string | null;
  fonte_url: string | null;
  fonte_titulo: string | null;
  coletado_por: string;
  coletado_em: string;
  removido_em: string | null;
}

/** Dispara o agente (Claude + busca na web) pra achar contato publico da
 * empresa/socios. Restrito a admin no backend (require_admin) -- dispara
 * custo de LLM por uso, entao nunca chame automaticamente. */
export async function enriquecerEmpresa(cnpj: string): Promise<{ cnpj: string; itens_encontrados: number; itens: ItemEnriquecimento[] }> {
  return request(`/api/v1/empresas/${encodeURIComponent(cnpj)}/enriquecer`, { method: "POST" });
}

export async function listarEnriquecimento(cnpj: string): Promise<ItemEnriquecimento[]> {
  return request(`/api/v1/empresas/${encodeURIComponent(cnpj)}/enriquecimento`);
}

/** Direito de exclusao (LGPD): apaga o valor/fonte coletados, mantendo so o
 * registro de auditoria de que a remocao aconteceu. */
export async function removerEnriquecimento(cnpj: string): Promise<{ cnpj: string; itens_removidos: number }> {
  return request(`/api/v1/empresas/${encodeURIComponent(cnpj)}/enriquecimento`, { method: "DELETE" });
}
