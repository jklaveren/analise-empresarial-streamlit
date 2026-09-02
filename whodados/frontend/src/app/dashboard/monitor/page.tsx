"use client";

import { useEffect, useState } from "react";
import {
  listarEmailsMonitor,
  getMonitorStats,
  getEmailsVermelhos,
  listarCampanhas,
  MonitorEmail,
  MonitorStats,
  Campanha,
} from "@/lib/api";
import Link from "next/link";

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

export default function MonitorPage() {
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
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Monitor de E-mails</h1>
          <p className="text-sm text-slate-500 mt-1">
            Acompanhe o status dos e-mails enviados com semáforo de follow-up (SLA 7 dias)
          </p>
        </div>
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