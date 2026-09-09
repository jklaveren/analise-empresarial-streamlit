"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listarCrmKanban,
  atualizarCrm,
  getEmpresaDetalhe,
  CrmKanban,
  CrmStatus,
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

export default function CrmPage() {
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
      setError("Erro ao carregar o CRM. Tente novamente.");
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
        <p className="text-slate-500">Carregando CRM...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">CRM</h1>
          <p className="text-sm text-slate-500">
            Acompanhe o funil de empresas, do primeiro contato até a conversão.
          </p>
        </div>
      </div>

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
