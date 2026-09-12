"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listarCrmKanban,
  atualizarCrm,
  getEmpresaDetalhe,
  CrmKanban,
  CrmStatus,
  listarEmailsMonitor,
  getMonitorStats,
  getEmailsVermelhos,
  listarCampanhas,
  MonitorEmail,
  MonitorStats,
  Campanha,
} from "@/lib/api";

const COLUNAS: { status: CrmStatus; label: string; cor: string }[] = [
  { status: "novo", label: "Novo", cor: "border-slate-300 bg-slate-50" },
  { status: "em_contato", label: "Em contato", cor: "border-sky-300 bg-sky-50" },
  { status: "negociando", label: "Negociando", cor: "border-amber-300 bg-amber-50" },
  { status: "convertido", label: "Convertido", cor: "border-emerald-300 bg-emerald-50" },
  { status: "descartado", label: "Descartado", cor: "border-rose-300 bg-rose-50" },
];

const KANBAN_VAZIO: CrmKanban = {
  novo: [],
  em_contato: [],
  negociando: [],
  convertido: [],
  descartado: [],
};

const SEMAFORO_CONFIG = {
  verde: {
    label: "No prazo",
    color: "bg-emerald-500",
    textColor: "text-emerald-700",
    bgCard: "bg-emerald-50 border-emerald-200",
    bgBadge: "bg-emerald-100 text-emerald-700",
    icon: "🟢",
    desc: "Enviados há até 2 dias ou já abertos",
  },
  amarelo: {
    label: "Atenção",
    color: "bg-amber-400",
    textColor: "text-amber-700",
    bgCard: "bg-amber-50 border-amber-200",
    bgBadge: "bg-amber-100 text-amber-700",
    icon: "🟡",
    desc: "Enviados há 3-5 dias sem interação",
  },
  vermelho: {
    label: "Urgente",
    color: "bg-red-500",
    textColor: "text-red-700",
    bgCard: "bg-red-50 border-red-200",
    bgBadge: "bg-red-100 text-red-700",
    icon: "🔴",
    desc: "Enviados há mais de 5 dias sem resposta",
  },
  cinza: {
    label: "Pendente",
    color: "bg-slate-400",
    textColor: "text-slate-600",
    bgCard: "bg-slate-50 border-slate-200",
    bgBadge: "bg-slate-100 text-slate-600",
    icon: "⚪",
    desc: "Pendente ou com erro",
  },
};

type SemaforoKey = keyof typeof SEMAFORO_CONFIG;

function FunilTab() {
  const [kanban, setKanban] = useState<CrmKanban>(KANBAN_VAZIO);
  const [nomes, setNomes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [movendo, setMovendo] = useState<string | null>(null);

  const carregar = async () => {
    try {
      const data = await listarCrmKanban();
      setKanban(data);

      const cnpjs = Array.from(
        new Set(Object.values(data).flat().map((r) => r.cnpj))
      );
      const faltantes = cnpjs.filter((c) => !(c in nomes));
      if (faltantes.length > 0) {
        const resultados = await Promise.all(
          faltantes.map(async (cnpj) => {
            try {
              const detalhe = await getEmpresaDetalhe(cnpj);
              return [cnpj, detalhe.razao_social] as const;
            } catch {
              return [cnpj, cnpj] as const;
            }
          })
        );
        setNomes((prev) => {
          const novo = { ...prev };
          for (const [cnpj, nome] of resultados) novo[cnpj] = nome;
          return novo;
        });
      }
    } catch (err) {
      setError("Erro ao carregar os clientes. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const moverPara = async (cnpj: string, novoStatus: CrmStatus) => {
    setMovendo(cnpj);
    try {
      await atualizarCrm(cnpj, { status: novoStatus });
      await carregar();
    } catch {
      setError("Não foi possível mover esse registro. Tente novamente.");
    } finally {
      setMovendo(null);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Carregando clientes...</p>
      </div>
    );
  }

  return (
    <div>
      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {COLUNAS.map((coluna) => {
          const registros = kanban[coluna.status] || [];
          return (
            <div key={coluna.status} className={`rounded-xl border ${coluna.cor} p-3 flex flex-col gap-2 min-h-[200px]`}>
              <div className="flex items-center justify-between px-1">
                <h2 className="text-sm font-semibold text-slate-700">{coluna.label}</h2>
                <span className="text-xs font-medium text-slate-500 bg-white rounded-full px-2 py-0.5">
                  {registros.length}
                </span>
              </div>

              {registros.length === 0 && (
                <p className="text-xs text-slate-400 px-1 py-4 text-center">Nenhuma empresa aqui</p>
              )}

              {registros.map((r) => (
                <div key={r.cnpj} className="bg-white rounded-lg border border-slate-200 p-3 shadow-sm">
                  <Link
                    href={`/dashboard/empresa/${encodeURIComponent(r.cnpj)}`}
                    className="text-sm font-medium text-slate-800 hover:text-indigo-600 line-clamp-2"
                  >
                    {nomes[r.cnpj] || r.cnpj}
                  </Link>
                  {r.notas && (
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">{r.notas}</p>
                  )}
                  <select
                    className="mt-2 w-full text-xs border border-slate-200 rounded-md px-2 py-1 text-slate-600 disabled:opacity-50"
                    value={r.status}
                    disabled={movendo === r.cnpj}
                    onChange={(e) => moverPara(r.cnpj, e.target.value as CrmStatus)}
                  >
                    {COLUNAS.map((c) => (
                      <option key={c.status} value={c.status}>
                        Mover para: {c.label}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MonitorTab() {
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [emails, setEmails] = useState<MonitorEmail[]>([]);
  const [vermelhos, setVermelhos] = useState<MonitorEmail[]>([]);
  const [campanhas, setCampanhas] = useState<Campanha[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroSemaforo, setFiltroSemaforo] = useState<SemaforoKey | "todos">("todos");
  const [filtroCampanha, setFiltroCampanha] = useState<number | "">("");
  const [search, setSearch] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [s, e, v, c] = await Promise.all([
        getMonitorStats(),
        listarEmailsMonitor(),
        getEmailsVermelhos(20),
        listarCampanhas(),
      ]);
      setStats(s);
      setEmails(e);
      setVermelhos(v);
      setCampanhas(c || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = emails.filter((email) => {
    if (filtroSemaforo !== "todos" && email.semaforo_status !== filtroSemaforo) return false;
    if (filtroCampanha !== "" && email.campaign_id !== filtroCampanha) return false;
    if (search) {
      const q = search.toLowerCase();
      const nome = (email.razao_social || email.nome_fantasia || "").toLowerCase();
      const dest = email.email_destino.toLowerCase();
      const cnpj = email.cnpj.toLowerCase();
      if (!nome.includes(q) && !dest.includes(q) && !cnpj.includes(q)) return false;
    }
    return true;
  });

  function formatDias(n: number): string {
    if (n < 1) return Math.round(n * 24) + "h";
    return Math.round(n) + "d";
  }

  function formatDate(d: string | null): string {
    if (!d) return "-";
    try {
      return new Date(d).toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "-";
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400 text-lg">Carregando monitor de e-mails...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-end mb-4">
        <button
          onClick={load}
          className="text-sm bg-white border border-slate-300 hover:bg-slate-50 text-slate-600 px-4 py-2 rounded-lg transition-colors"
        >
          🔄 Atualizar
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {(Object.keys(SEMAFORO_CONFIG) as SemaforoKey[]).map((key) => {
          const cfg = SEMAFORO_CONFIG[key];
          const count = stats ? stats[key] : 0;
          const isActive = filtroSemaforo === key;
          return (
            <button
              key={key}
              onClick={() => setFiltroSemaforo(isActive ? "todos" : key)}
              className={
                isActive
                  ? cfg.bgCard + " rounded-xl border p-4 text-left transition-all border-2 shadow-sm"
                  : "bg-white border-slate-200 rounded-xl border p-4 text-left transition-all hover:border-slate-300"
              }
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl">{cfg.icon}</span>
                <span className={"text-xs font-medium " + cfg.textColor}>{cfg.label}</span>
              </div>
              <div className={"text-2xl font-bold " + cfg.textColor}>{count}</div>
              <div className="text-xs text-slate-500 mt-1">{cfg.desc}</div>
            </button>
          );
        })}
      </div>

      {vermelhos.length > 0 && (
        <div className={"rounded-xl border p-4 mb-6 " + SEMAFORO_CONFIG.vermelho.bgCard}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xl">🚨</span>
            <h2 className="font-semibold text-red-700">
              {vermelhos.length} e-mail{vermelhos.length > 1 ? "s" : ""} aguardando follow-up
            </h2>
            <span className="text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded-full ml-1">
              &gt;5 dias
            </span>
          </div>
          <div className="space-y-2">
            {vermelhos.slice(0, 5).map((v) => (
              <div key={v.id} className="flex items-center justify-between bg-white/60 rounded-lg px-3 py-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-slate-800 truncate">
                    {v.razao_social || v.nome_fantasia || v.cnpj}
                  </div>
                  <div className="text-xs text-slate-500">{v.email_destino}</div>
                </div>
                <div className="flex items-center gap-3 ml-4 shrink-0">
                  <span className="text-xs text-slate-500">
                    {formatDias(v.dias_desde_envio)} sem resposta
                  </span>
                  <Link
                    href={`/dashboard/empresa/${encodeURIComponent(v.cnpj)}`}
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    Ver empresa
                  </Link>
                </div>
              </div>
            ))}
          </div>
          {vermelhos.length > 5 && (
            <p className="text-xs text-red-600 mt-2 text-center">
              +{vermelhos.length - 5} outros e-mails aguardando follow-up
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-4 items-center">
        <input
          type="text"
          placeholder="Buscar empresa, e-mail ou CNPJ..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-48 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <select
          value={filtroCampanha}
          onChange={(e) => setFiltroCampanha(e.target.value ? Number(e.target.value) : "")}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Todas campanhas</option>
          {campanhas.map((c) => (
            <option key={c.id} value={c.id}>{c.nome}</option>
          ))}
        </select>
        <select
          value={filtroSemaforo}
          onChange={(e) => setFiltroSemaforo(e.target.value as SemaforoKey | "todos")}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="todos">Todos os status</option>
          {(Object.keys(SEMAFORO_CONFIG) as SemaforoKey[]).map((key) => (
            <option key={key} value={key}>
              {SEMAFORO_CONFIG[key].icon} {SEMAFORO_CONFIG[key].label}
            </option>
          ))}
        </select>
        <span className="text-sm text-slate-500">
          {filtered.length} resultado{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <div className="text-5xl mb-4">📭</div>
          <p className="text-lg font-medium">Nenhum e-mail encontrado</p>
          <p className="text-sm mt-1">
            Execute uma campanha primeiro ou ajuste os filtros.
          </p>
          <a href="/dashboard/campanhas" className="inline-block mt-4 text-sm text-indigo-600 hover:underline">
            Ir para Campanhas →
          </a>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-3 font-medium text-slate-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Empresa</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">E-mail</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Enviado em</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Dias</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Campanha</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((email) => {
                const cfg = SEMAFORO_CONFIG[email.semaforo_status as SemaforoKey];
                const nome = email.razao_social || email.nome_fantasia;
                return (
                  <tr key={email.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3">
                      <span className={"inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-1 rounded-full " + cfg.bgBadge}>
                        <span>{cfg.icon}</span>
                        <span>{cfg.label}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800 truncate max-w-[180px]">
                        {nome || <span className="text-slate-400">—</span>}
                      </div>
                      {nome && <div className="text-xs text-slate-400">{email.cnpj}</div>}
                    </td>
                    <td className="px-4 py-3 text-slate-600 truncate max-w-[200px]">
                      {email.email_destino}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">
                      {formatDate(email.enviado_em)}
                    </td>
                    <td className="px-4 py-3">
                      <span className={"font-semibold " + cfg.textColor}>
                        {formatDias(email.dias_desde_envio)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 truncate max-w-[120px]">
                      {email.campanha_nome || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {email.cnpj && (
                        <Link
                          href={"/dashboard/empresa/" + encodeURIComponent(email.cnpj)}
                          className="text-xs text-indigo-600 hover:underline whitespace-nowrap"
                        >
                          Ver empresa →
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
        <span>🟢 <strong>Verde:</strong> até 2 dias ou aberto</span>
        <span>🟡 <strong>Amarelo:</strong> 3-5 dias sem interação</span>
        <span>🔴 <strong>Vermelho:</strong> mais de 5 dias — follow-up urgente</span>
        <span>⚪ <strong>Pendente:</strong> status pendente/erro</span>
      </div>
    </div>
  );
}

export default function CrmPage() {
  const [aba, setAba] = useState<"funil" | "monitor">("funil");

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Clientes</h1>
        <p className="text-sm text-slate-500">
          Acompanhe a carteira de empresas e o follow-up dos envios, tudo em um só lugar.
        </p>
      </div>

      <div className="mb-6 flex gap-1 border-b border-slate-200">
        <button
          onClick={() => setAba("funil")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            aba === "funil" ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          🗂️ Clientes
        </button>
        <button
          onClick={() => setAba("monitor")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            aba === "monitor" ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          🚦 Follow-up de E-mails
        </button>
      </div>

      {aba === "funil" ? <FunilTab /> : <MonitorTab />}
    </div>
  );
}
