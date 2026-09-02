"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, ResponsiveContainer, Legend,
} from "recharts";
import { EmpresaItem } from "@/lib/api";

const COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f97316", "#10b981", "#3b82f6"];

interface AnalyticsChartsProps {
  empresas: EmpresaItem[];
}

export function AnalyticsCharts({ empresas }: AnalyticsChartsProps) {
  const porCidade = useMemo(() => {
    const map: Record<string, number> = {};
    empresas.forEach(e => {
      const city = e.municipio || "Desconhecido";
      map[city] = (map[city] || 0) + 1;
    });
    return Object.entries(map)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 15);
  }, [empresas]);

  const porPorte = useMemo(() => {
    const map: Record<string, number> = {};
    empresas.forEach(e => {
      const p = e.porte_nome || "DEMAIS";
      map[p] = (map[p] || 0) + 1;
    });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [empresas]);

  const comDivida = useMemo(() => {
    const com = empresas.filter(e => e.divida_total > 0).length;
    const sem = empresas.length - com;
    return [
      { name: "Com Dívida", value: com },
      { name: "Sem Dívida", value: sem },
    ];
  }, [empresas]);

  if (empresas.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Por Cidade */}
      <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200">
        <h3 className="font-semibold text-slate-800 mb-4">Empresas por Cidade</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={porCidade} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={100} />
              <Tooltip />
              <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Por Porte */}
      <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200">
        <h3 className="font-semibold text-slate-800 mb-4">Por Porte</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={porPorte}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={90}
                paddingAngle={2}
                dataKey="value"
              >
                {porPorte.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Com Divida */}
      <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200 md:col-span-2">
        <h3 className="font-semibold text-slate-800 mb-4">Dívida Ativa</h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={comDivida}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
              >
                <Cell fill="#ef4444" />
                <Cell fill="#10b981" />
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
