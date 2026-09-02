"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MultiSelect } from "@/components/MultiSelect";
import { AnalyticsCharts } from "@/components/AnalyticsCharts";
import { listarEmpresas, EmpresaItem } from "@/lib/api";

export default function DashboardPage() {
  const [empresas, setEmpresas] = useState<EmpresaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtroCidade, setFiltroCidade] = useState<string[]>([]);
  const [filtroCnae, setFiltroCnae] = useState<string[]>([]);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    const carregar = async () => {
      try {
        const data = await listarEmpresas();
        setEmpresas(data);
      } catch (err) {
        setError("Erro ao carregar empresas. Tente novamente.");
      } finally {
        setLoading(false);
      }
    };
    carregar();
  }, []);

  if (loading) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Carregando empresas...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
    );
  }

  const cidades = Array.from(
    new Set(empresas.map(e => e.municipio).filter((m): m is string => !!m))
  );
  const cnaes = Array.from(
    new Set(empresas.map(e => e.cnae_principal).filter((c): c is string => !!c))
  );

  const filtradas = empresas.filter(e => {
    if (filtroCidade.length && e.municipio && !filtroCidade.includes(e.municipio)) return false;
    if (filtroCnae.length && e.cnae_principal && !filtroCnae.includes(e.cnae_principal)) return false;
    if (busca && !e.razao_social.toLowerCase().includes(busca.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-slate-500 mt-1">
          {filtradas.length} de {empresas.length} empresas
        </p>
      </header>

      {/* Filtros */}
      <div className="rounded-xl bg-white p-4 shadow-sm border border-slate-200">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="text"
            placeholder="Buscar por razão social..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-indigo-500"
          />
          <MultiSelect
            options={cidades.map(c => ({ value: c, label: c }))}
            selected={filtroCidade}
            onChange={setFiltroCidade}
            placeholder="Cidades..."
          />
          <MultiSelect
            options={cnaes.map(c => ({ value: c, label: c }))}
            selected={filtroCnae}
            onChange={setFiltroCnae}
            placeholder="CNAEs..."
          />
        </div>
      </div>

      {/* Graficos */}
      <AnalyticsCharts empresas={filtradas} />

      {/* Tabela */}
      <div className="rounded-xl bg-white shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-700">
              <tr>
                <th className="px-4 py-3 text-left">CNPJ</th>
                <th className="px-4 py-3 text-left">Razão Social</th>
                <th className="px-4 py-3 text-left">Município</th>
                <th className="px-4 py-3 text-left">CNAE</th>
                <th className="px-4 py-3 text-right">Capital</th>
                <th className="px-4 py-3 text-right">Dívida</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtradas.slice(0, 50).map(e => (
                <tr key={e.cnpj_completo} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs">{e.cnpj_completo}</td>
                  <td className="px-4 py-3 font-medium">{e.razao_social}</td>
                  <td className="px-4 py-3">{e.municipio || "-"}</td>
                  <td className="px-4 py-3 text-xs">{e.cnae_principal || "-"}</td>
                  <td className="px-4 py-3 text-right">
                    {e.capital_social.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                  </td>
                  <td className="px-4 py-3 text-right text-red-600">
                    {e.divida_total.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/dashboard/empresa/${encodeURIComponent(e.cnpj_completo)}`}
                      className="rounded-lg bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600 hover:bg-indigo-100"
                    >
                      Ver detalhes
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtradas.length > 50 && (
          <div className="px-4 py-3 text-center text-sm text-slate-500 border-t border-slate-100">
            Mostrando 50 de {filtradas.length} — use os filtros para refinar
          </div>
        )}
      </div>
    </div>
  );
}
