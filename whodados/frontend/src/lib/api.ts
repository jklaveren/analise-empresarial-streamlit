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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const orgId = getActiveOrgId();
  if (orgId) headers["X-Org-Id"] = String(orgId);
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

export async function getMe() {
  return request("/api/v1/auth/me");
}

// ==================== ORGANIZACOES (MULTI-EMPRESA) ====================

export interface Organizacao {
  id: number;
  nome: string;
  slug: string;
  ativo: boolean;
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
}

export async function listarEmpresas(cidade?: string, cnae?: string, busca?: string, limit = 100, offset = 0): Promise<EmpresaItem[]> {
  const params = new URLSearchParams();
  if (cidade) params.append("cidade", cidade);
  if (cnae) params.append("cnae", cnae);
  if (busca) params.append("busca", busca);
  params.append("limit", String(limit));
  params.append("offset", String(offset));
  return request(`/api/v1/empresas?${params}`);
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

export async function atualizarCrm(cnpj: string, data: { status?: string; notas?: string }) {
  return request(`/api/v1/crm/${encodeURIComponent(cnpj)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ==================== CRM (KANBAN) ====================

export type CrmStatus = "novo" | "em_contato" | "negociando" | "convertido" | "descartado";

export interface CrmKanbanRecord {
  id: number;
  cnpj: string;
  status: CrmStatus;
  notas: string | null;
  criado_por?: string | null;
  data_atualizacao?: string | null;
}

export type CrmKanban = Record<CrmStatus, CrmKanbanRecord[]>;

export async function listarCrmKanban(): Promise<CrmKanban> {
  return request("/api/v1/crm");
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
  created_at?: string;
  updated_at?: string;
  criado_por?: string;
}

export interface Campanha {
  id?: number;
  nome: string;
  template_id: number;
  filtros: Record<string, any>;
  status?: string;
  total_destinatarios?: number;
  enviados?: number;
  erros?: number;
  eh_sequencia?: boolean;
  created_at?: string;
  created_by?: string;
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

export async function deletarTemplate(id: number): Promise<{ ok: boolean }> {
  return request(`/api/v1/templates/${id}`, { method: "DELETE" });
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

export async function executarCampanha(id: number): Promise<{ sucessos: number; erros: number }> {
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

export async function atualizarUsuarioAdmin(userId: number, data: { is_admin?: boolean; is_active?: boolean }): Promise<UsuarioAdmin> {
  return request(`/api/v1/admin/usuarios/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
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
