"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, ResponsiveContainer, Legend,
} from "recharts";
import {
  getAnalyticsResumo, getAnalyticsPorCidade, getAnalyticsPorSetor, getAnalyticsPorPorte,
  AnalyticsFiltros, AnalyticsResumo, CidadeAgg, SetorAgg, PorteAgg,
} from "@/lib/api";

const COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f97316", "#10b981", "#3b82f6"];

function brl(v: number): string {
  if (Math.abs(v) >= 1e9) return `R$ ${(v / 1e9).toFixed(1)} bi`;
  if (Math.abs(v) >= 1e6) return `R$ ${(v / 1e6).toFixed(1)} mi`;
  if (Math.abs(v) >= 1e3) return `R$ ${(v / 1e3).toFixed(0)} mil`;
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/**
 * Insights AGREGADOS sobre a base filtrada inteira (não sobre a página exibida).
 * Cada valor é calculado no servidor (endpoints de analytics) com os mesmos
 * filtros do funil -- ex.: dívida por cidade mostra PoA/Caxias/Canoas com os
 * totais reais de toda a seleção.
 */
export function FunilInsights({ filtros }: { filtros: AnalyticsFiltros }) {
  const [resumo, setResumo] = useState<AnalyticsResumo | null>(null);
  const [cidades, setCidades] = useState<CidadeAgg[]>([]);
  const [setores, setSetores] = useState<SetorAgg[]>([]);
  const [portes, setPortes] = useState<PorteAgg[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    Promise.all([
      getAnalyticsResumo(filtros),
      getAnalyticsPorCidade(filtros, 12),
      getAnalyticsPorSetor(filtros, 10),
      getAnalyticsPorPorte(filtros),
    ])
      .then(([r, c, s, p]) => { if (!cancel) { setResumo(r); setCidades(c); setSetores(s); setPortes(p); } })
      .catch(() => {})
      .finally(() => { if (!cancel) setLoading(false); });
    return () => { cancel = true; };
  }, [filtros]);

  const kpis = resumo ? [
    { label: "Empresas", valor: resumo.total_empresas.toLocaleString("pt-BR") },
    { label: "Dívida total", valor: brl(resumo.divida_total) },
    { label: "Capital total", valor: brl(resumo.capital_total) },
    { label: "Dívida média", valor: brl(resumo.divida_media) },
    { label: "Cidades", valor: resumo.qtd_cidades.toLocaleString("pt-BR") },
    { label: "Setores", valor: resumo.qtd_setores.toLocaleString("pt-BR") },
  ] : [];

  const cidadeData = cidades.map(c => ({ name: c.cidade, divida: c.divida_total, qtd: c.qtd }));
  const setorData = setores.map(s => ({ name: (s.descricao || s.cnae).slice(0, 28), divida: s.divida_total, qtd: s.qtd }));
  const porteData = portes.map(p => ({ name: p.porte || "—", value: p.qtd }));

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {(loading && !resumo ? Array.from({ length: 6 }) : kpis).map((k, i) => (
          <div key={i} className="rounded-xl bg-white border border-slate-200 p-4">
            <div className="text-xs text-slate-500">{(k as { label?: string })?.label ?? "…"}</div>
            <div className="text-lg font-bold text-slate-800 mt-1">{(k as { valor?: string })?.valor ?? "—"}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Dívida por cidade */}
        <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-1">Dívida por cidade</h3>
          <p className="text-xs text-slate-400 mb-4">Total de passivo por município (base filtrada inteira)</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cidadeData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => brl(Number(v))} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
                <Tooltip formatter={(v: number, n) => n === "divida" ? brl(Number(v)) : v} />
                <Bar dataKey="divida" name="Dívida" fill="#ef4444" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Dívida por setor */}
        <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-1">Dívida por setor (CNAE)</h3>
          <p className="text-xs text-slate-400 mb-4">Top setores por passivo</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={setorData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => brl(Number(v))} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={140} />
                <Tooltip formatter={(v: number, n) => n === "divida" ? brl(Number(v)) : v} />
                <Bar dataKey="divida" name="Dívida" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Distribuição por porte */}
        <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200 lg:col-span-2">
          <h3 className="font-semibold text-slate-800 mb-4">Distribuição por porte</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={porteData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={2} dataKey="value">
                  {porteData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: number) => v.toLocaleString("pt-BR")} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
