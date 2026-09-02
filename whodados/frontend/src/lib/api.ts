/**
 * Cliente HTTP para a API FastAPI.
 * Todas as rotas (exceto /health e /auth/login) exigem Bearer token.
 */

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

const TOKEN_KEY = "whodados_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let message = `Erro ${res.status}`;
    try {
      const data = await res.json();
      message = data.detail || data.message || message;
    } catch {}
    throw new ApiError(message, res.status);
  }

  if (res.status === 204) return null as T;
  return res.json();
}

// -------- Tipos --------
export interface EmpresaItem {
  cnpj_completo: string;
  razao_social: string;
  nome_fantasia?: string;
  municipio?: string;
  cnae_principal?: string;
  capital_social: number;
  divida_total: number;
  porte_nome?: string;
  data_fundacao?: string;
}

export interface CrmData {
  status?: string;
  notas?: string;
  data_atualizacao?: string;
}

export interface SocioItem {
  nome_socio: string;
  cpf_cnpj_socio?: string;
  qualif_socio?: string;
}

export interface EmpresaDetalhe extends EmpresaItem {
  logradouro?: string;
  numero?: string;
  bairro?: string;
  cep?: string;
  email?: string;
  contato_fone?: string;
  socios?: SocioItem[];
  crm?: CrmData;
}

// -------- Auth --------
export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);
  return request<LoginResponse>("/auth/login", { method: "POST", body });
}

// -------- Empresas --------
export async function listarEmpresas(params?: { cidade?: string; cnae?: string; busca?: string }): Promise<EmpresaItem[]> {
  const query = new URLSearchParams();
  if (params?.cidade) query.set("cidade", params.cidade);
  if (params?.cnae) query.set("cnae", params.cnae);
  if (params?.busca) query.set("busca", params.busca);
  const qs = query.toString();
  return request<EmpresaItem[]>(`/empresas${qs ? `?${qs}` : ""}`);
}

export async function getEmpresaDetalhe(cnpj: string): Promise<EmpresaDetalhe> {
  return request<EmpresaDetalhe>(`/empresas/${encodeURIComponent(cnpj)}`);
}

// -------- CRM --------
export async function atualizarCrm(cnpj: string, data: { status?: string; notas?: string }): Promise<CrmData> {
  return request<CrmData>(`/crm/${encodeURIComponent(cnpj)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function getCrm(cnpj: string): Promise<CrmData> {
  return request<CrmData>(`/crm/${encodeURIComponent(cnpj)}`);
}
