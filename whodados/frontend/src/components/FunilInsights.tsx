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

  // O banco atual pode nao ter coluna de passivo (ETL legado sem
  // DIVIDA_TOTAL). Nesse caso os agregados de divida voltam 0 -- e mostrar
  // "R$ 0" nos KPIs/graficos seria mentir. Escondemos divida e mostramos o
  // que existe de verdade: contagem, capital, cidades, setores, portes.
  const temDivida = resumo?.tem_dados_divida === true;

  const kpis = resumo ? (
    temDivida ? [
      { label: "Empresas", valor: resumo.total_empresas.toLocaleString("pt-BR") },
      { label: "Dívida total", valor: brl(resumo.divida_total) },
      { label: "Capital total", valor: brl(resumo.capital_total) },
      { label: "Dívida média", valor: brl(resumo.divida_media) },
      { label: "Cidades", valor: resumo.qtd_cidades.toLocaleString("pt-BR") },
      { label: "Setores", valor: resumo.qtd_setores.toLocaleString("pt-BR") },
    ] : [
      { label: "Empresas", valor: resumo.total_empresas.toLocaleString("pt-BR") },
      { label: "Capital total", valor: brl(resumo.capital_total) },
      { label: "Capital médio", valor: brl(resumo.capital_medio) },
      { label: "Cidades", valor: resumo.qtd_cidades.toLocaleString("pt-BR") },
      { label: "Setores", valor: resumo.qtd_setores.toLocaleString("pt-BR") },
      { label: "Falência/Recup.", valor: resumo.qtd_inativas.toLocaleString("pt-BR") },
    ]
  ) : [];

  // Barras ordenadas por volume: qtd quando nao ha passivo, divida quando ha.
  const cidadeData = [...cidades]
    .sort((a, b) => temDivida ? b.divida_total - a.divida_total : b.qtd - a.qtd)
    .map(c => ({
      name: c.cidade,
      valor: temDivida ? c.divida_total : c.qtd,
      qtd: c.qtd,
      capital: c.capital_total,
    }));
  const setorData = [...setores]
    .sort((a, b) => temDivida ? b.divida_total - a.divida_total : b.qtd - a.qtd)
    .map(s => ({
      name: (s.descricao || s.cnae).slice(0, 28),
      valor: temDivida ? s.divida_total : s.qtd,
      qtd: s.qtd,
      capital: s.capital_total,
    }));
  // Portes nomeados primeiro; "NAO INFORMADO" vai pro fim e em cinza --
  // senao ele domina o grafico (quase 100% da base) e esconde as fatias pequenas.
  const porteData = [...portes]
    .sort((a, b) => {
      const naoInfo = (p: PorteAgg) => !p.porte || !p.porte.trim() || p.porte.trim().toUpperCase().startsWith("NAO");
      return Number(naoInfo(a)) - Number(naoInfo(b)) || b.qtd - a.qtd;
    })
    .map(p => ({ name: p.porte && p.porte.trim() ? p.porte : "Não informado", value: p.qtd }));
  const porteTotal = porteData.reduce((s, p) => s + p.value, 0);
  const COR_NAO_INFORMADO = "#cbd5e1";
  const pct = (v: number) => (porteTotal ? ((v / porteTotal) * 100).toFixed(1) : "0");

    return (
    <div className="space-y-8">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {(loading && !resumo ? Array.from({ length: 6 }) : kpis).map((k, i) => (
          <div 
            key={i} 
            className="rounded-2xl bg-white/80 backdrop-blur-sm border border-slate-200/50 p-5 shadow-lg hover:shadow-xl transition-all duration-300 group"
          >
            <div className="text-xs text-slate-500 group-hover:text-slate-700 transition-colors">
              {(k as { label?: string })?.label ?? "…"}
            </div>
            <div className="text-xl font-bold text-slate-800 mt-2 group-hover:text-indigo-600 transition-colors">
              {(k as { valor?: string })?.valor ?? "—"}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Dívida por cidade */}
        <div className="rounded-2xl bg-white/80 border border-slate-200/50 p-6 shadow-lg hover:shadow-xl transition-shadow duration-300">
          <h3 className="font-semibold text-slate-800 text-lg mb-1">Dívida por cidade</h3>
          <p className="text-xs text-slate-400 mb-5">Total de passivo por município (base filtrada inteira)</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cidadeData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => brl(Number(v))} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
                <Tooltip formatter={(v: number, n) => n === "divida" ? brl(Number(v)) : v} />
                <Bar dataKey="divida" name="Dívida" fill="url(#cityGradient)" radius={[0, 4, 4, 0]} />
                <defs>
                  <linearGradient id="cityGradient" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#ef4444" />
                    <stop offset="100%" stopColor="#f97316" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Dívida por setor */}
        <div className="rounded-2xl bg-white/80 border border-slate-200/50 p-6 shadow-lg hover:shadow-xl transition-colors duration-300">
          <h3 className="font-semibold text-slate-800 text-lg mb-1">Dívida por setor (CNAE)</h3>
          <p className="text-xs text-slate-400 mb-5">Top setores por passivo</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={setorData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => brl(Number(v))} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={140} />
                <Tooltip formatter={(v: number, n) => n === "divida" ? brl(Number(v)) : v} />
                <Bar dataKey="divida" name="Dívida" fill="url(#sectorGradient)" radius={[0, 4, 4, 0]} />
                <defs>
                  <linearGradient id="sectorGradient" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#8b5cf6" />
                    <stop offset="100%" stopColor="#ec4899" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Distribuição por porte */}
        <div className="rounded-2xl bg-white/80 border border-slate-200/50 p-6 shadow-lg hover:shadow-xl transition-colors duration-300 lg:col-span-2">
          <h3 className="font-semibold text-slate-800 text-lg mb-1">Distribuição por porte</h3>
          <p className="text-xs text-slate-400 mb-2">Empresas por porte — percentual sobre a base filtrada</p>
          <div className="relative h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={porteData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={2}
                  dataKey="value"
                  stroke="none"
                >
                  {porteData.map((p, i) => (
                    <Cell
                      key={i}
                      fill={p.name === "Não informado" ? COR_NAO_INFORMADO : COLORS[i % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number, name) => [
                    `${Number(v).toLocaleString("pt-BR")} empresas (${pct(Number(v))}%)`,
                    String(name),
                  ]}
                />
                <Legend
                  payload={porteData.map((p, i) => ({
                    value: `${p.name} · ${p.value.toLocaleString("pt-BR")} (${pct(p.value)}%)`,
                    type: "square" as const,
                    color: p.name === "Não informado" ? COR_NAO_INFORMADO : COLORS[i % COLORS.length],
                    id: String(i),
                  }))}
                  wrapperStyle={{ fontSize: 11 }}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* Total no centro do donut (levemente acima, compensando a legenda) */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pb-10 pointer-events-none">
              <span className="text-2xl font-bold text-slate-800">{porteTotal.toLocaleString("pt-BR")}</span>
              <span className="text-xs text-slate-400">empresas</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
