"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { MultiSelect } from "@/components/MultiSelect";
import { FunilInsights } from "@/components/FunilInsights";
import { listarEmpresas, contarEmpresas, getOpcoesFiltro, EmpresaItem, EmpresaFiltros, AnalyticsFiltros, OpcoesFiltro } from "@/lib/api";

const PAGE_SIZE = 50;

function formatBRL(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function DashboardPage() {
  const [opcoes, setOpcoes] = useState<OpcoesFiltro | null>(null);

  // Filtros do funil (estado bruto)
  const [cidade, setCidade] = useState<string[]>([]);
  const [porte, setPorte] = useState<string[]>([]);
  const [cnae, setCnae] = useState<string[]>([]);
  const [busca, setBusca] = useState("");
  const [dividaMin, setDividaMin] = useState("");
  const [dividaMax, setDividaMax] = useState("");
  const [capitalMin, setCapitalMin] = useState("");
  const [capitalMax, setCapitalMax] = useState("");
  const [fundacaoDe, setFundacaoDe] = useState("");
  const [fundacaoAte, setFundacaoAte] = useState("");
  const [incluirInativas, setIncluirInativas] = useState(true);

  const [empresas, setEmpresas] = useState<EmpresaItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Opcoes dos multiselects (uma vez)
  useEffect(() => { getOpcoesFiltro().then(setOpcoes).catch(() => {}); }, []);

  // Filtros "crus" -> aplicados com atraso (nao dispara a cada tecla nos campos)
  const filtros: EmpresaFiltros = useMemo(() => ({
    cidade, porte, cnae,
    busca: busca || undefined,
    divida_min: dividaMin ? Number(dividaMin) : undefined,
    divida_max: dividaMax ? Number(dividaMax) : undefined,
    capital_min: capitalMin ? Number(capitalMin) : undefined,
    capital_max: capitalMax ? Number(capitalMax) : undefined,
    fundacao_de: fundacaoDe || undefined,
    fundacao_ate: fundacaoAte || undefined,
    incluir_inativas: incluirInativas,
  }), [cidade, porte, cnae, busca, dividaMin, dividaMax, capitalMin, capitalMax, fundacaoDe, fundacaoAte, incluirInativas]);

  const filtrosKey = JSON.stringify(filtros);
  const [applied, setApplied] = useState<EmpresaFiltros>(filtros);
  useEffect(() => {
    const t = setTimeout(() => setApplied(filtros), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtrosKey]);

  const appliedKey = JSON.stringify(applied);

  // Filtros para os insights agregados (analytics nao usa busca/fundacao)
  const analyticsFiltros: AnalyticsFiltros = useMemo(() => ({
    cidade: applied.cidade, cnae: applied.cnae, porte: applied.porte,
    divida_min: applied.divida_min, divida_max: applied.divida_max,
    capital_min: applied.capital_min, capital_max: applied.capital_max,
    incluir_inativas: applied.incluir_inativas,
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [appliedKey]);

  // Volta pra primeira pagina quando o filtro aplicado muda
  useEffect(() => { setPage(0); }, [appliedKey]);

  // Contagem do funil
  useEffect(() => {
    contarEmpresas(applied).then(r => setTotal(r.total)).catch(() => setTotal(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedKey]);

  // Pagina atual
  useEffect(() => {
    let cancel = false;
    setLoading(true); setError("");
    listarEmpresas(applied, PAGE_SIZE, page * PAGE_SIZE)
      .then(d => { if (!cancel) setEmpresas(d); })
      .catch(() => { if (!cancel) setError("Erro ao carregar empresas."); })
      .finally(() => { if (!cancel) setLoading(false); });
    return () => { cancel = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedKey, page]);

  const cidadeOptions = useMemo(() => (opcoes?.cidades ?? []).map(c => ({ value: c, label: c })), [opcoes]);
  const porteOptions = useMemo(() => (opcoes?.portes ?? []).map(p => ({ value: p, label: p })), [opcoes]);
  const cnaeOptions = useMemo(() => (opcoes?.cnaes ?? []).map(c => ({
    value: c.codigo,
    label: `${c.codigo} - ${c.descricao}${c.qtd ? ` (${c.qtd.toLocaleString("pt-BR")})` : ""}`,
  })), [opcoes]);

  const totalPages = total != null ? Math.max(1, Math.ceil(total / PAGE_SIZE)) : null;

  const limparFiltros = () => {
    setCidade([]); setPorte([]); setCnae([]); setBusca("");
    setDividaMin(""); setDividaMax(""); setCapitalMin(""); setCapitalMax("");
    setFundacaoDe(""); setFundacaoAte(""); setIncluirInativas(true);
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Empresas</h1>
          <p className="text-slate-500 mt-1">
            {total != null
              ? <><strong className="text-indigo-700">{total.toLocaleString("pt-BR")}</strong> empresas neste filtro</>
              : "Contando..."}
          </p>
        </div>
        <button onClick={limparFiltros} className="text-sm text-slate-500 hover:text-slate-800 underline">Limpar filtros</button>
      </header>

      {/* Funil de filtros */}
      <div className="rounded-xl bg-white p-4 shadow-sm border border-slate-200 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            type="text"
            placeholder="Buscar por razão social / fantasia..."
            value={busca}
            onChange={e => setBusca(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-indigo-500"
          />
          <MultiSelect options={cidadeOptions} selected={cidade} onChange={setCidade} placeholder="Cidades..." />
          <MultiSelect options={porteOptions} selected={porte} onChange={setPorte} placeholder="Porte..." />
        </div>

        <MultiSelect options={cnaeOptions} selected={cnae} onChange={setCnae} placeholder="Setores (CNAE — código e descrição)..." />

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <label className="text-xs text-slate-500">Passivo (R$)
            <div className="mt-1 flex gap-2">
              <input type="number" placeholder="min" value={dividaMin} onChange={e => setDividaMin(e.target.value)} className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
              <input type="number" placeholder="max" value={dividaMax} onChange={e => setDividaMax(e.target.value)} className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
            </div>
          </label>
          <label className="text-xs text-slate-500">Capital social (R$)
            <div className="mt-1 flex gap-2">
              <input type="number" placeholder="min" value={capitalMin} onChange={e => setCapitalMin(e.target.value)} className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
              <input type="number" placeholder="max" value={capitalMax} onChange={e => setCapitalMax(e.target.value)} className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
            </div>
          </label>
          <label className="text-xs text-slate-500">Fundação (de / até)
            <div className="mt-1 flex gap-2">
              <input type="date" value={fundacaoDe} onChange={e => setFundacaoDe(e.target.value)} className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
              <input type="date" value={fundacaoAte} onChange={e => setFundacaoAte(e.target.value)} className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" />
            </div>
          </label>
          <label className="flex items-end gap-2 text-sm text-slate-600 pb-1">
            <input type="checkbox" checked={!incluirInativas} onChange={e => setIncluirInativas(!e.target.checked)} />
            Ocultar Falência / Rec. Judicial
          </label>
        </div>
      </div>

      {/* Insights agregados sobre a base filtrada inteira */}
      <FunilInsights filtros={analyticsFiltros} />

      {error && <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>}

      {/* Tabela (página) */}
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
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Carregando...</td></tr>
              ) : empresas.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Nenhuma empresa para este filtro.</td></tr>
              ) : empresas.map(e => (
                <tr key={e.cnpj_completo} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs">{e.cnpj_completo}</td>
                  <td className="px-4 py-3 font-medium">{e.razao_social}</td>
                  <td className="px-4 py-3">{e.municipio || "-"}</td>
                  <td className="px-4 py-3 text-xs">{e.cnae_principal || "-"}{e.cnae_descricao ? ` - ${e.cnae_descricao}` : ""}</td>
                  <td className="px-4 py-3 text-right">{formatBRL(e.capital_social)}</td>
                  <td className="px-4 py-3 text-right text-red-600">{formatBRL(e.divida_total)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/dashboard/empresa/${encodeURIComponent(e.cnpj_completo)}`} className="rounded-lg bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600 hover:bg-indigo-100">
                      Ver detalhes
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages != null && total! > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-sm text-slate-600">
            <span>Página {page + 1} de {totalPages.toLocaleString("pt-BR")}</span>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-3 py-1 rounded border border-slate-300 disabled:opacity-40">Anterior</button>
              <button onClick={() => setPage(p => (totalPages && p + 1 < totalPages ? p + 1 : p))} disabled={totalPages != null && page + 1 >= totalPages} className="px-3 py-1 rounded border border-slate-300 disabled:opacity-40">Próxima</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
