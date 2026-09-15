"use client";
import { useEffect, useState } from "react";
import {
  listarCampanhas, criarCampanha, executarCampanha, deletarCampanha,
  listarTemplates, getOpcoesFiltro, listarEmpresas,
} from "@/lib/api";

type FiltrosForm = { cidade: string[]; cnae: string[]; porte: string[]; busca: string; divida_min: string };
const FORM_VAZIO: FiltrosForm = { cidade: [], cnae: [], porte: [], busca: "", divida_min: "" };
const PORTES = ["MICRO", "PEQUENO", "DEMAIS", "SEM INFORMACAO"];

const STATUS_COR: Record<string, string> = {
  rascunho: "bg-slate-100 text-slate-600",
  executando: "bg-blue-100 text-blue-700",
  concluida: "bg-emerald-100 text-emerald-700",
  erro: "bg-red-100 text-red-700",
};

function montarFiltros(f: FiltrosForm): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (f.cidade.length) out.cidade = f.cidade;
  if (f.cnae.length) out.cnae = f.cnae;
  if (f.porte.length) out.porte = f.porte;
  if (f.busca.trim()) out.busca = f.busca.trim();
  if (f.divida_min.trim() && Number(f.divida_min) > 0) out.divida_min = Number(f.divida_min);
  return out;
}

function Chips({ opcoes, selecionados, onChange, placeholder }: { opcoes: string[]; selecionados: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [busca, setBusca] = useState("");
  const sugestoes = (opcoes || [])
    .filter((o) => o && !selecionados.includes(o) && o.toLowerCase().includes(busca.toLowerCase()))
    .slice(0, 30);
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      <div className="flex flex-wrap gap-1.5 mb-2 min-h-[26px]">
        {selecionados.length === 0 && <span className="text-xs text-slate-400 px-1 self-center">{placeholder}</span>}
        {selecionados.map((s) => (
          <span key={s} className="inline-flex items-center gap-1 bg-indigo-100 text-indigo-700 text-xs font-medium px-2 py-0.5 rounded-full">
            {s}
            <button type="button" onClick={() => onChange(selecionados.filter((x) => x !== s))} className="text-indigo-400 hover:text-indigo-700" title="Remover">×</button>
          </span>
        ))}
      </div>
      <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar opção…" className="w-full text-sm rounded-md border border-slate-200 px-2 py-1 bg-white" />
      {busca.trim() !== "" && sugestoes.length > 0 && (
        <div className="max-h-32 overflow-y-auto bg-white rounded-md border border-slate-200 mt-1">
          {sugestoes.map((s) => (
            <button key={s} type="button" onClick={() => { onChange([...selecionados, s]); setBusca(""); }} className="block w-full text-left text-sm px-2 py-1 hover:bg-indigo-50">
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ResumoPublico({ total, carregando, qtdFiltros }: { total: number | null; carregando: boolean; qtdFiltros: number }) {
  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 flex items-start gap-3">
      <div className="text-2xl">🎯</div>
      <div className="flex-1">
        {carregando ? (
          <p className="text-sm text-indigo-700">Calculando público…</p>
        ) : total === null ? (
          <p className="text-sm text-amber-700">Não foi possível calcular o público agora (os filtros continuam salvos).</p>
        ) : (
          <>
            <p className="text-lg font-bold text-indigo-900">{total.toLocaleString("pt-BR")} empresas atendem aos filtros</p>
            <p className="text-xs text-indigo-600 mt-0.5">
              {qtdFiltros === 0
                ? "Nenhum filtro aplicado — a campanha atinge a base inteira."
                : "Prévia calculada com os mesmos filtros do envio. Quem não tem e-mail cai na lista de ligação."}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function resumoFiltros(f: any): string[] {
  const chips: string[] = [];
  const arr = (v: any) => (Array.isArray(v) ? v : v ? [v] : []);
  if (arr(f?.cidade).length) chips.push("Cidade: " + arr(f.cidade).join(", "));
  if (arr(f?.cnae).length) chips.push("CNAE: " + arr(f.cnae).join(", "));
  if (arr(f?.porte).length) chips.push("Porte: " + arr(f.porte).join(", "));
  if (f?.busca) chips.push("Busca: " + f.busca);
  if (f?.divida_min) chips.push("Dívida ≥ R$ " + Number(f.divida_min).toLocaleString("pt-BR"));
  return chips;
}

export default function CampanhasPage() {
  const [campanhas, setCampanhas] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [opcoes, setOpcoes] = useState<{ cidades: string[]; cnaes: string[]; portes: string[] }>({ cidades: [], cnaes: [], portes: [] });
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<number | null>(null);
  const [form, setForm] = useState<{ nome: string; template_id: number; filtros: FiltrosForm }>({ nome: "", template_id: 0, filtros: FORM_VAZIO });
  const [prevTotal, setPrevTotal] = useState<number | null>(null);
  const [prevCarregando, setPrevCarregando] = useState(false);

  async function load() {
    setLoading(true); setErro("");
    try {
      const [c, t] = await Promise.all([listarCampanhas(), listarTemplates()] as any);
      setCampanhas(Array.isArray(c) ? c : []);
      setTemplates(Array.isArray(t) ? t : []);
    } catch (e: any) {
      setErro(e?.message || "Erro ao carregar campanhas.");
    } finally { setLoading(false); }
  }

  async function carregarOpcoes() {
    try {
      const o: any = (await getOpcoesFiltro()) as any;
      setOpcoes({ cidades: o?.cidades || [], cnaes: o?.cnaes || o?.setores || [], portes: o?.portes || [] });
    } catch { /* sem opções — campos continuam utilizáveis */ }
  }

  useEffect(() => { load(); carregarOpcoes(); }, []);

  // Prévia do público: recalcula (com debounce) sempre que os filtros mudam.
  useEffect(() => {
    if (!showModal) return;
    const t = setTimeout(async () => {
      setPrevCarregando(true);
      try {
        const res: any = (await listarEmpresas(montarFiltros(form.filtros) as any, 1 as any)) as any;
        const total = Number(res?.total ?? (res?.empresas || res?.items || []).length);
        setPrevTotal(Number.isFinite(total) ? total : null);
      } catch { setPrevTotal(null); } finally { setPrevCarregando(false); }
    }, 500);
    return () => clearTimeout(t);
  }, [form.filtros, showModal]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.template_id) { setErro("Selecione um template para a campanha."); return; }
    setSaving(true); setErro("");
    try {
      await criarCampanha({ nome: form.nome, template_id: form.template_id, filtros: montarFiltros(form.filtros) } as any);
      setShowModal(false);
      setForm({ nome: "", template_id: 0, filtros: FORM_VAZIO });
      await load();
    } catch (e: any) { setErro(e?.message || "Erro ao criar campanha."); }
    finally { setSaving(false); }
  }

  async function handleRun(c: any) {
    if (!confirm('Disparar a campanha "' + c.nome + '" agora?')) return;
    setRunning(c.id);
    try {
      const r: any = await executarCampanha(c.id);
      alert("Campanha finalizada: " + (r?.sucessos ?? 0) + " enviados com sucesso, " + (r?.erros ?? 0) + " erros.");
      await load();
    } catch (e: any) { alert(e?.message || "Erro ao executar campanha."); }
    finally { setRunning(null); }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir esta campanha?")) return;
    try { await deletarCampanha(id); await load(); }
    catch (e: any) { alert(e?.message || "Erro ao excluir campanha."); }
  }

  function handleDuplicar(c: any) {
    const f = c?.filtros || {};
    const arr = (v: any) => (Array.isArray(v) ? v : v ? [v] : []);
    setForm({
      nome: (c.nome || "Campanha") + " (cópia)",
      template_id: c.template_id || 0,
      filtros: { cidade: arr(f.cidade), cnae: arr(f.cnae), porte: arr(f.porte), busca: f.busca || "", divida_min: f.divida_min != null ? String(f.divida_min) : "" },
    });
    setPrevTotal(null);
    setShowModal(true);
  }
  const qtdFiltros = form.filtros.cidade.length + form.filtros.cnae.length + form.filtros.porte.length + (form.filtros.busca.trim() ? 1 : 0) + (form.filtros.divida_min.trim() ? 1 : 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Campanhas</h1>
          <p className="text-sm text-slate-500 mt-1">Envie e-mails em massa com prévia do público antes de disparar.</p>
        </div>
        <button onClick={() => { setForm({ nome: "", template_id: 0, filtros: FORM_VAZIO }); setPrevTotal(null); setShowModal(true); }} disabled={templates.length === 0}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm">
          + Nova Campanha
        </button>
      </div>

      {templates.length === 0 && !loading && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4 text-sm text-amber-800">
          Você precisa de um template antes de criar campanhas. <a href="/dashboard/templates" className="font-bold underline">Criar template →</a>
        </div>
      )}
      {erro && <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 text-sm text-red-700">{erro}</div>}
      {loading && <div className="text-center py-12 text-slate-500">Carregando…</div>}

      {!loading && campanhas.length === 0 && (
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200">
          <div className="text-5xl mb-3">📣</div>
          <p className="text-slate-600 font-medium">Nenhuma campanha ainda</p>
          <p className="text-sm text-slate-400 mt-1">Crie a primeira campanha e veja quantas empresas ela alcança antes de enviar.</p>
        </div>
      )}

      {!loading && campanhas.length > 0 && (
        <div className="grid grid-cols-1 gap-3">
          {campanhas.map((c) => {
            const chips = resumoFiltros(c.filtros);
            return (
              <div key={c.id} className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h3 className="font-semibold text-slate-800">{c.nome}</h3>
                      <span className={"text-xs px-2 py-0.5 rounded-full font-medium " + (STATUS_COR[c.status || "rascunho"] || STATUS_COR.rascunho)}>{c.status || "rascunho"}</span>
                    </div>
                    <p className="text-xs text-slate-500">Template #{c.template_id}{c.created_at ? " · criada em " + new Date(c.created_at).toLocaleString("pt-BR") : ""}</p>
                    {chips.length > 0 && (
                      <div className="mt-2 flex gap-1 flex-wrap">
                        {chips.map((chip) => (
                          <span key={chip} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{chip}</span>
                        ))}
                      </div>
                    )}
                    {chips.length === 0 && <p className="text-xs text-amber-600 mt-2">⚠ Sem filtros — a campanha vai atingir a base inteira.</p>}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button onClick={() => handleRun(c)} disabled={running === c.id} className="text-xs bg-emerald-100 hover:bg-emerald-200 disabled:opacity-50 text-emerald-700 px-3 py-1.5 rounded-lg font-medium transition-colors">
                      {running === c.id ? "Enviando…" : "▶ Executar"}
                    </button>
                    <button onClick={() => handleDuplicar(c)} className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-lg font-medium transition-colors">Duplicar</button>
                    <button onClick={() => handleDelete(c.id)} className="text-slate-400 hover:text-red-500 transition-colors p-1.5" title="Excluir">✕</button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
            <div className="p-6 border-b border-slate-200"><h2 className="text-lg font-bold text-slate-800">Nova Campanha</h2><p className="text-xs text-slate-500 mt-0.5">Defina o público — a prévia mostra quantas empresas serão atingidas.</p></div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Nome da campanha</label>
                  <input required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: Previdenciário — POA" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Template</label>
                  <select required value={form.template_id} onChange={(e) => setForm({ ...form, template_id: Number(e.target.value) })} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white">
                    <option value={0}>Selecione…</option>
                    {templates.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Cidades ({opcoes.cidades.length} disponíveis)</label>
                <Chips opcoes={opcoes.cidades} selecionados={form.filtros.cidade} onChange={(v) => setForm({ ...form, filtros: { ...form.filtros, cidade: v } })} placeholder="Nenhuma cidade selecionada — todas" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Setores / CNAE</label>
                <Chips opcoes={opcoes.cnaes} selecionados={form.filtros.cnae} onChange={(v) => setForm({ ...form, filtros: { ...form.filtros, cnae: v } })} placeholder="Nenhum setor selecionado — todos" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Porte</label>
                  <div className="flex flex-wrap gap-1.5">
                    {PORTES.map((p) => {
                      const ativo = form.filtros.porte.includes(p);
                      return (
                        <button key={p} type="button" onClick={() => setForm({ ...form, filtros: { ...form.filtros, porte: ativo ? form.filtros.porte.filter((x) => x !== p) : [...form.filtros.porte, p] } })}
                          className={"text-xs px-2.5 py-1 rounded-full border transition-colors " + (ativo ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-600 border-slate-300 hover:border-indigo-400")}>
                          {p}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Busca</label>
                  <input value={form.filtros.busca} onChange={(e) => setForm({ ...form, filtros: { ...form.filtros, busca: e.target.value } })} placeholder="Nome, CNPJ…" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Dívida mínima (R$)</label>
                  <input type="number" min="0" value={form.filtros.divida_min} onChange={(e) => setForm({ ...form, filtros: { ...form.filtros, divida_min: e.target.value } })} placeholder="Ex.: 10000" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                </div>
              </div>

              <ResumoPublico total={prevTotal} carregando={prevCarregando} qtdFiltros={qtdFiltros} />

              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50">Cancelar</button>
                <button type="submit" disabled={saving} className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50">{saving ? "Criando…" : "Criar campanha"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
