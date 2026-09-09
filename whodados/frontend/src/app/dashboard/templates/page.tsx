"use client";

import { useEffect, useState } from "react";
import { listarTemplates, criarTemplate, deletarTemplate, Template } from "@/lib/api";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ nome: "", assunto: "", corpo_html: "" });
  const [saving, setSaving] = useState(false);

  async function load() {
    try { setTemplates(await listarTemplates()); } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try { await criarTemplate(form); setShowModal(false); setForm({ nome: "", assunto: "", corpo_html: "" }); load(); }
    catch (e: any) { alert(e.message); } finally { setSaving(false); }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir este template?")) return;
    try { await deletarTemplate(id); load(); } catch (e: any) { alert(e.message); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div><h1 className="text-2xl font-bold text-slate-800">Templates de Email</h1><p className="text-sm text-slate-500 mt-1">Gerencie seus modelos de comunicacao</p></div>
        <button onClick={() => setShowModal(true)} className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">+ Novo Template</button>
      </div>
      {loading && <div className="text-center py-12 text-slate-500">Carregando...</div>}
      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-4">{error}</div>}
      {!loading && templates.length === 0 && (
        <div className="text-center py-16 text-slate-400"><div className="text-5xl mb-4">📝</div><p className="text-lg font-medium">Nenhum template cadastrado</p><p className="text-sm mt-1">Clique em "Novo Template" para criar o primeiro.</p></div>
      )}
      {templates.length > 0 && (
        <div className="grid gap-4">
          {templates.map(t => (
            <div key={t.id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1"><h3 className="font-semibold text-slate-800 truncate">{t.nome}</h3><span className="text-xs text-slate-400">#{t.id}</span></div>
                  <p className="text-sm text-indigo-600 font-medium truncate">{t.assunto}</p>
                  {t.created_at && <p className="text-xs text-slate-400 mt-1">Criado em {new Date(t.created_at).toLocaleDateString("pt-BR")}</p>}
                </div>
                <button onClick={() => handleDelete(t.id!)} className="ml-4 text-slate-400 hover:text-red-500 transition-colors p-1" title="Excluir">🗑️</button>
              </div>
              {t.corpo_html && <div className="mt-3 p-3 bg-slate-50 rounded-lg text-sm text-slate-600 max-h-24 overflow-hidden">{t.corpo_html.replace(/<[^>]+>/g, "").slice(0, 200)}...</div>}
            </div>
          ))}
        </div>
      )}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="p-6 border-b border-slate-200"><h2 className="text-lg font-bold text-slate-800">Novo Template</h2></div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Nome</label><input required value={form.nome} onChange={e => setForm({...form, nome: e.target.value})} placeholder="Ex: Primeiro contato" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none" /></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Assunto</label><input required value={form.assunto} onChange={e => setForm({...form, assunto: e.target.value})} placeholder="Ex: Oportunidade de parceria" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none" /></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Corpo (HTML)</label><textarea required rows={8} value={form.corpo_html} onChange={e => setForm({...form, corpo_html: e.target.value})} placeholder="<p>Ola, {nome}!</p>" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none resize-y" /><p className="text-xs text-slate-400 mt-1">Use {"{nome}"}, {"{empresa}"} como variaveis</p></div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancelar</button>
                <button type="submit" disabled={saving} className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium">{saving ? "Salvando..." : "Salvar Template"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
