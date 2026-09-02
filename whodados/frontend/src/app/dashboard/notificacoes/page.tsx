"use client";

import { useEffect, useState } from "react";
import { listarNotificacoes, marcarNotificacaoLida, Notificacao } from "@/lib/api";
import Link from "next/link";

const TIPO_ICONS: Record<string, string> = {
  campanha: "📧", crm: "👤", enriquecimento: "🔍", sistema: "⚙️", erro: "❌",
};

export default function NotificacoesPage() {
  const [items, setItems] = useState<Notificacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"todas" | "nao_lidas">("nao_lidas");

  async function load() {
    setLoading(true);
    try {
      const data = await listarNotificacoes(filter === "nao_lidas" ? false : undefined);
      setItems(data || []);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [filter]);

  async function handleRead(id: number) {
    try { await marcarNotificacaoLida(id); load(); } catch (e: any) { alert(e.message); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div><h1 className="text-2xl font-bold text-slate-800">Notificações</h1><p className="text-sm text-slate-500 mt-1">Acompanhe eventos do sistema</p></div>
        <div className="flex bg-slate-100 rounded-lg p-1">
          <button onClick={() => setFilter("nao_lidas")} className={`px-3 py-1.5 rounded text-sm font-medium ${filter === "nao_lidas" ? "bg-white shadow-sm" : "text-slate-600"}`}>Não lidas</button>
          <button onClick={() => setFilter("todas")} className={`px-3 py-1.5 rounded text-sm font-medium ${filter === "todas" ? "bg-white shadow-sm" : "text-slate-600"}`}>Todas</button>
        </div>
      </div>

      {loading && <div className="text-center py-12 text-slate-500">Carregando...</div>}
      {!loading && items.length === 0 && <div className="text-center py-16 text-slate-400"><div className="text-5xl mb-4">🔔</div><p className="text-lg font-medium">Nenhuma notificação {filter === "nao_lidas" ? "pendente" : "encontrada"}</p></div>}

      {items.length > 0 && (
        <div className="space-y-2">
          {items.map(n => (
            <div key={n.id} className={`bg-white rounded-xl border p-4 flex items-start gap-3 ${n.lida ? "border-slate-200 opacity-70" : "border-indigo-200 bg-indigo-50/30"}`}>
              <div className="text-2xl">{TIPO_ICONS[n.tipo] || "📌"}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1"><h3 className="font-semibold text-slate-800 text-sm">{n.titulo}</h3>{!n.lida && <span className="w-2 h-2 bg-indigo-500 rounded-full"></span>}</div>
                {n.mensagem && <p className="text-sm text-slate-600 mb-1">{n.mensagem}</p>}
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span>{new Date(n.created_at).toLocaleString("pt-BR")}</span>
                  {n.cnpj && <Link href={`/dashboard/empresa/${encodeURIComponent(n.cnpj)}`} className="text-indigo-600 hover:underline">ver empresa</Link>}
                </div>
              </div>
              {!n.lida && <button onClick={() => handleRead(n.id)} className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded font-medium">Marcar lida</button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

