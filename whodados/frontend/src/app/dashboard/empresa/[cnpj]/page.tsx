"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ApiError, EmpresaDetalhe, atualizarCrm, getEmpresaDetalhe } from "@/lib/api";

export default function EmpresaDetalhePage() {
  const params = useParams<{ cnpj: string }>();
  const cnpj = params?.cnpj ? decodeURIComponent(params.cnpj) : "";
  const [empresa, setEmpresa] = useState<EmpresaDetalhe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [crmStatus, setCrmStatus] = useState("");
  const [crmNotas, setCrmNotas] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!cnpj) return;
    getEmpresaDetalhe(cnpj)
      .then(data => {
        setEmpresa(data);
        setCrmStatus(data.crm?.status || "");
        setCrmNotas(data.crm?.notas || "");
      })
      .catch(err => {
        if (err instanceof ApiError) setError(err.message);
        else setError("Erro ao carregar empresa");
      })
      .finally(() => setLoading(false));
  }, [cnpj]);

  const handleSalvarCrm = async () => {
    if (!empresa) return;
    setSalvando(true);
    try {
      await atualizarCrm(empresa.cnpj_completo, { status: crmStatus, notas: crmNotas });
      alert("CRM atualizado!");
    } catch (err) {
      alert("Erro: " + (err instanceof ApiError ? err.message : "desconhecido"));
    } finally {
      setSalvando(false);
    }
  };

  if (loading) return <div className="text-center py-12 text-slate-500">Carregando...</div>;
  if (error) return <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>;
  if (!empresa) return null;

  const fmt = (v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard" className="text-sm text-indigo-600 hover:underline">← Voltar</Link>
        <h1 className="text-2xl font-bold text-slate-800 mt-2">{empresa.razao_social}</h1>
        <p className="text-slate-500 font-mono text-sm">{empresa.cnpj_completo}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Dados */}
        <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200">
          <h2 className="font-semibold text-slate-800 mb-4">Dados da Empresa</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-500">Nome Fantasia:</dt><dd>{empresa.nome_fantasia || "-"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Porte:</dt><dd>{empresa.porte_nome || "-"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Fundação:</dt><dd>{empresa.data_fundacao || "-"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">CNAE:</dt><dd className="text-xs">{empresa.cnae_principal || "-"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Capital:</dt><dd>{fmt(empresa.capital_social)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Dívida Total:</dt><dd className="text-red-600 font-semibold">{fmt(empresa.divida_total)}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Telefone:</dt><dd>{empresa.contato_fone || "-"}</dd></div>
          </dl>
        </div>

        {/* CRM */}
        <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200">
          <h2 className="font-semibold text-slate-800 mb-4">CRM</h2>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Status</label>
              <select value={crmStatus} onChange={e => setCrmStatus(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2">
                <option value="">— Selecionar —</option>
                <option value="novo">Novo</option>
                <option value="em_contato">Em Contato</option>
                <option value="negociando">Negociando</option>
                <option value="convertido">Convertido</option>
                <option value="descartado">Descartado</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Notas</label>
              <textarea value={crmNotas} onChange={e => setCrmNotas(e.target.value)} rows={6} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
            </div>
            <button onClick={handleSalvarCrm} disabled={salvando} className="w-full rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
              {salvando ? "Salvando..." : "Salvar CRM"}
            </button>
          </div>
        </div>
      </div>

      {/* Sócios */}
      {empresa.socios && empresa.socios.length > 0 && (
        <div className="rounded-xl bg-white p-6 shadow-sm border border-slate-200">
          <h2 className="font-semibold text-slate-800 mb-4">Sócios</h2>
          <table className="w-full text-sm">
            <thead className="text-slate-700 border-b border-slate-200">
              <tr><th className="text-left pb-2">Nome</th><th className="text-left pb-2">CPF/CNPJ</th><th className="text-left pb-2">Qualificação</th></tr>
            </thead>
            <tbody>
              {empresa.socios.map((s, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="py-2 font-medium">{s.nome_socio}</td>
                  <td className="py-2 font-mono text-xs">{s.cpf_cnpj_socio || "-"}</td>
                  <td className="py-2">{s.qualif_socio || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
