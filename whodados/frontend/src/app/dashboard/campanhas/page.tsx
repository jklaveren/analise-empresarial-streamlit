"use client";

import { useEffect, useState } from "react";
import { listarCampanhas, criarCampanha, executarCampanha, deletarCampanha, listarTemplates, Campanha, Template } from "@/lib/api";

export default function CampanhasPage() {
  const [campanhas, setCampanhas] = useState<Campanha[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<number | null>(null);
  const [form, setForm] = useState({ nome: "", template_id: 0, filtros: { cidade: "", cnae: "", busca: "" } });

  async function load() {
    setLoading(true);
    try {
      const [c, t] = await Promise.all([listarCampanhas(), listarTemplates()]);
      setCampanhas(c || []);
      setTemplates(t || []);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.template_id) { alert("Selecione um template"); return; }
    setSaving(true);
    try {
      const filtros: any = {};
      if (form.filtros.cidade) filtros.cidade = form.filtros.cidade;
      if (form.filtros.cnae) filtros.cnae = form.filtros.cnae;
      if (form.filtros.busca) filtros.busca = form.filtros.busca;
      await criarCampanha({ nome: form.nome, template_id: form.template_id, filtros });
      setShowModal(false);
      setForm({ nome: "", template_id: 0, filtros: { cidade: "", cnae: "", busca: "" } });
      load();
    } catch (e: any) { alert(e.message); } finally { setSaving(false); }
  }

  async function handleRun(id: number) {
    if (!confirm("Iniciar o envio desta campanha agora?")) return;
    setRunning(id);
    try {
      const r = await executarCampanha(id);
      alert("Campanha finalizada! " + r.sucessos + " OK, " + r.erros + " erros");
      load();
    } catch (e: any) { alert(e.message); } finally { setRunning(null); }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir esta campanha?")) return;
    try { await deletarCampanha(id); load(); } catch (e: any) { alert(e.message); }
  }

  const statusColors: Record<string, string> = {
    rascunho: "bg-slate-100 text-slate-700",
    executando: "bg-blue-100 text-blue-700",
    concluida: "bg-green-100 text-green-700",
    erro: "bg-red-100 text-red-700",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div><h1 className="text-2xl font-bold text-slate-800">Campanhas</h1><p className="text-sm text-slate-500 mt-1">Crie e execute campanhas de email</p></div>
        <button onClick={() => setShowModal(true)} disabled={templates.length === 0} className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">+ Nova Campanha</button>
      </div>
      {templates.length === 0 && !loading && <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 text-sm text-amber-800">Aviso: crie um <a href="/dashboard/templates" className="font-bold underline">template</a> antes.</div>}
      {loading && <div className="text-center py-12 text-slate-500">Carregando...</div>}
      {!loading && campanhas.length === 0 && (
        <div className="text-center py-12 text-slate-400 text-sm">Nenhuma campanha criada ainda.</div>
      )}
      {!loading && campanhas.length > 0 && (
        <div className="space-y-3">
          {campanhas.map(c => (
            <div key={c.id} className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1"><h3 className="font-semibold text-slate-800">{c.nome}</h3><span className={"text-xs px-2 py-0.5 rounded-full " + (statusColors[c.status || "rascunho"] || "bg-slate-100")}>{c.status || "rascunho"}</span></div>
                  <p className="text-xs text-slate-500">Template #{c.template_id}{c.created_at && " em " + new Date(c.created_at).toLocaleString("pt-BR")}</p>
                  {c.filtros && Object.keys(c.filtros).length > 0 && <div className="mt-2 flex gap-1 flex-wrap">{Object.entries(c.filtros).map(([k, v]) => v && <span key={k} className="text-xs bg-slate-100 px-2 py-0.5 rounded">{k}: {v}</span>)}</div>}
                </div>
                <div className="flex gap-2 ml-4">
                  <button onClick={() => handleRun(c.id!)} disabled={running === c.id} className="text-xs bg-green-100 hover:bg-green-200 disabled:opacity-50 text-green-700 px-3 py-1.5 rounded font-medium">Executar</button>
                  <button onClick={() => handleDelete(c.id!)} className="text-slate-400 hover:text-red-500 transition-colors p-1" title="Excluir">X</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="p-6 border-b border-slate-200"><h2 className="text-lg font-bold text-slate-800">Nova Campanha</h2></div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Nome</label><input required value={form.nome} onChange={e => setForm({...form, nome: e.target.value})} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Template</label><select required value={form.template_id} onChange={e => setForm({...form, template_id: Number(e.target.value)})} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value={0}>Selecione</option>{templates.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}</select></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Filtros</label><div className="grid grid-cols-3 gap-2"><input value={form.filtros.cidade} onChange={e => setForm({...form, filtros: {...form.filtros, cidade: e.target.value}})} placeholder="Cidade" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" /><input value={form.filtros.cnae} onChange={e => setForm({...form, filtros: {...form.filtros, cnae: e.target.value}})} placeholder="CNAE" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" /><input value={form.filtros.busca} onChange={e => setForm({...form, filtros: {...form.filtros, busca: e.target.value}})} placeholder="Busca" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" /></div></div>
              <div className="flex gap-3 pt-2"><button type="button" onClick={() => setShowModal(false)} className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancelar</button><button type="submit" disabled={saving} className="flex-1 bg-indigo-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50">{saving ? "Criando..." : "Criar"}</button></div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}