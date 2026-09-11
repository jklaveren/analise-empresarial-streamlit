"use client";

import { useEffect, useState } from "react";
import { listarTemplates, criarTemplate, atualizarTemplate, deletarTemplate, enviarTesteTemplate, uploadTemplateImagem, Template } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CATEGORIAS = ["todos", "tecnologia", "comercio", "industria", "servicos"];

type FormState = { nome: string; assunto: string; corpo_html: string; corpo_texto: string; categoria_cnae: string };
const VAZIO: FormState = { nome: "", assunto: "", corpo_html: "", corpo_texto: "", categoria_cnae: "todos" };

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [temImagem, setTemImagem] = useState(false);
  const [logoV, setLogoV] = useState(0);
  const [form, setForm] = useState<FormState>(VAZIO);
  const [saving, setSaving] = useState(false);
  const [fb, setFb] = useState<{ t: "s" | "e"; m: string } | null>(null);

  async function load() {
    try { setTemplates(await listarTemplates()); } catch (e) { setError(e instanceof Error ? e.message : "Erro"); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  function abrirNovo() {
    setEditId(null); setTemImagem(false); setForm(VAZIO); setFb(null); setShowModal(true);
  }
  function abrirEdicao(t: Template) {
    setEditId(t.id ?? null);
    setTemImagem(!!t.tem_imagem);
    setForm({ nome: t.nome, assunto: t.assunto, corpo_html: t.corpo_html, corpo_texto: t.corpo_texto || "", categoria_cnae: t.categoria_cnae || "todos" });
    setFb(null);
    setShowModal(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setFb(null);
    try {
      if (editId) {
        await atualizarTemplate(editId, form);
      } else {
        const t = await criarTemplate(form);
        setEditId(t.id ?? null); // permite enviar imagem logo apos criar
      }
      await load();
      setFb({ t: "s", m: "Template salvo." });
      if (!editId) setShowModal(false);
    } catch (e) {
      setFb({ t: "e", m: e instanceof Error ? e.message : "Erro ao salvar." });
    } finally { setSaving(false); }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir este template?")) return;
    try { await deletarTemplate(id); load(); } catch (e) { alert(e instanceof Error ? e.message : "Erro"); }
  }

  async function handleImagem(file: File | null) {
    if (!file || !editId) return;
    setFb(null);
    try {
      await uploadTemplateImagem(editId, file);
      setTemImagem(true); setLogoV(v => v + 1);
      setFb({ t: "s", m: "Imagem enviada. Use {{imagem}} no corpo para exibi-la." });
      await load();
    } catch (e) {
      setFb({ t: "e", m: e instanceof Error ? e.message : "Erro ao enviar imagem." });
    }
  }

  async function handleTestar(t: Template) {
    const para = window.prompt(`Enviar um teste de "${t.nome}" para qual e-mail?`);
    if (!para) return;
    const cnpj = window.prompt("(Opcional) CNPJ de uma empresa real para testar a personalização com dados reais dela. Deixe em branco para usar dados de exemplo.") || undefined;
    try {
      const r = await enviarTesteTemplate(t.id!, para, cnpj);
      if (r.sucesso) alert(r.simulado ? "Teste OK (SMTP não configurado — envio simulado)." : `Teste enviado para ${para}.`);
      else alert(`Falha: ${r.erro || "erro"}`);
    } catch (e) { alert(e instanceof Error ? e.message : "Erro"); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
        <div><h1 className="text-2xl font-bold text-slate-800">Templates de Email</h1><p className="text-sm text-slate-500 mt-1">Gerencie seus modelos de comunicação</p></div>
        <button onClick={abrirNovo} className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">+ Novo Template</button>
      </div>
      {loading && <div className="text-center py-12 text-slate-500">Carregando...</div>}
      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-4">{error}</div>}
      {!loading && templates.length === 0 && (
        <div className="text-center py-16 text-slate-400"><div className="text-5xl mb-4">📝</div><p className="text-lg font-medium">Nenhum template cadastrado</p><p className="text-sm mt-1">Clique em &quot;Novo Template&quot; para criar o primeiro.</p></div>
      )}
      {templates.length > 0 && (
        <div className="grid gap-4">
          {templates.map(t => (
            <div key={t.id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-semibold text-slate-800 truncate">{t.nome}</h3>
                    <span className="text-xs text-slate-400">#{t.id}</span>
                    {t.categoria_cnae && t.categoria_cnae !== "todos" && <span className="text-[10px] uppercase bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{t.categoria_cnae}</span>}
                    {t.tem_imagem && <span className="text-[10px] bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">🖼️ imagem</span>}
                  </div>
                  <p className="text-sm text-indigo-600 font-medium truncate">{t.assunto}</p>
                  {t.created_at && <p className="text-xs text-slate-400 mt-1">Criado em {new Date(t.created_at).toLocaleDateString("pt-BR")}</p>}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => handleTestar(t)} className="text-xs text-green-600 hover:underline px-1" title="Enviar teste">Testar</button>
                  <button onClick={() => abrirEdicao(t)} className="text-xs text-indigo-600 hover:underline px-1" title="Editar">Editar</button>
                  <button onClick={() => handleDelete(t.id!)} className="text-slate-400 hover:text-red-500 transition-colors p-1" title="Excluir">🗑️</button>
                </div>
              </div>
              {t.corpo_html && <div className="mt-3 p-3 bg-slate-50 rounded-lg text-sm text-slate-600 max-h-24 overflow-hidden">{t.corpo_html.replace(/<[^>]+>/g, "").slice(0, 200)}...</div>}
            </div>
          ))}
        </div>
      )}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-200"><h2 className="text-lg font-bold text-slate-800">{editId ? "Editar Template" : "Novo Template"}</h2></div>
            <form onSubmit={handleSave} className="p-6 space-y-4">
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Nome</label><input required value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })} placeholder="Ex: Primeiro contato" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none" /></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Assunto</label><input required value={form.assunto} onChange={e => setForm({ ...form, assunto: e.target.value })} placeholder="Ex: Oportunidade de parceria" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none" /></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Categoria (CNAE)</label>
                <select value={form.categoria_cnae} onChange={e => setForm({ ...form, categoria_cnae: e.target.value })} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                  {CATEGORIAS.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Corpo (HTML)</label><textarea required rows={8} value={form.corpo_html} onChange={e => setForm({ ...form, corpo_html: e.target.value })} placeholder="<p>Olá, {{empresa}}!</p>" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none resize-y" /><p className="text-xs text-slate-400 mt-1">Variáveis: {"{{empresa}}"}, {"{{cidade}}"}, {"{{cnae_descricao}}"}, {"{{imagem}}"} (imagem do template)</p></div>

              {/* Imagem: só após o template ter id (salvar primeiro) */}
              <div className="rounded-lg border border-slate-200 p-3">
                <label className="block text-sm font-medium text-slate-700 mb-1">Imagem do template</label>
                {editId ? (
                  <div className="flex items-center gap-3">
                    {temImagem && <img src={`${API_BASE}/api/v1/templates/${editId}/imagem?v=${logoV}`} alt="Imagem" className="h-12 border rounded bg-slate-50 p-1" />}
                    <input type="file" accept="image/*" onChange={e => handleImagem(e.target.files?.[0] ?? null)} className="text-sm" />
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">Salve o template primeiro para poder anexar uma imagem.</p>
                )}
              </div>

              {fb && <div className={`p-3 rounded text-sm ${fb.t === "s" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>{fb.m}</div>}
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Fechar</button>
                <button type="submit" disabled={saving} className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium">{saving ? "Salvando..." : "Salvar Template"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
