const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

function setToken(token: string): void {
  localStorage.setItem("token", token);
}

function removeToken(): void {
  localStorage.removeItem("token");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Erro desconhecido" }));
    throw new ApiError(res.status, body.detail || "Erro na API");
  }
  return res.json();
}

// Auth
export async function login(username: string, password: string) {
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);
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
-NoNewline
