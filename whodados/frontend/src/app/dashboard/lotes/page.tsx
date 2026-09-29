"use client";

import Link from "next/link";

import { useEffect, useMemo, useState } from "react";
import { listarLotes, criarLote, getLote, deletarLote, criarCampanhaDoLote, listarTemplates, getOpcoesFiltro, contarEmpresas, definirTemplateBloco, descreverFiltros, recalcularLote, type OpcoesFiltro, type CanalLote } from "@/lib/api";
import { MultiSelect } from "@/components/MultiSelect";

// Nomes que o backend entende (codigos RF 01/03/05); rotulo so pra tela.
const PORTES_OPCOES = [
  { value: "ME", label: "Micro" },
  { value: "EPP", label: "Pequeno porte" },
  { value: "DEMAIS", label: "Demais" },
];

export default function LotesPage() {
  const [lotes, setLotes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  // Form para criar lote (focado em CNAE, Capital, Fundação, etc.)
  const [nomeLote, setNomeLote] = useState("");
  const [cidadeFiltro, setCidadeFiltro] = useState<string[]>([]);
  const [cnaeFiltro, setCnaeFiltro] = useState<string[]>([]);
  const [opcoes, setOpcoes] = useState<OpcoesFiltro | null>(null);
  const [capitalMin, setCapitalMin] = useState("");
  const [fundacaoDe, setFundacaoDe] = useState("");
  const [porteFiltro, setPorteFiltro] = useState<string[]>([]);
  const [dividaMin, setDividaMin] = useState("");
  const [criando, setCriando] = useState(false);
  const [previa, setPrevia] = useState<number | null>(null);
  const [prevendo, setPrevendo] = useState(false);

  // Lote selecionado para detalhe / modal de campanha
  const [loteDetalhe, setLoteDetalhe] = useState<any | null>(null);
  const [recalculando, setRecalculando] = useState<number | null>(null);
  const [modalCampanhaLote, setModalCampanhaLote] = useState<any | null>(null);
  const [templates, setTemplates] = useState<any[]>([]);
  const [canalCampanha, setCanalCampanha] = useState("email");
  const [templateIdCampanha, setTemplateIdCampanha] = useState<number | "" >("");
  const [mensagemCampanha, setMensagemCampanha] = useState("");
  const [nomeCampanha, setNomeCampanha] = useState("");
  const [tamanhoLoteEnvio, setTamanhoLoteEnvio] = useState("100");
  const [enviandoCampanha, setEnviandoCampanha] = useState(false);

  async function carregar() {
    setLoading(true);
    setErro(null);
    try {
      const data = await listarLotes();
      setLotes(data);
      const tpls = await listarTemplates().catch(() => []);
      setTemplates(tpls);
    } catch (e: any) {
      setErro(e?.message || "Erro ao carregar lotes.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    carregar();
    getOpcoesFiltro().then(setOpcoes).catch(() => setOpcoes(null));
  }, []);

  // Mesmas opcoes do dashboard: so da pra escolher o que existe na base
  // (texto livre gerava lote vazio: "Porto Alegre" x "PORTO ALEGRE", CNAE
  // de 5 digitos x codigo de 7 no banco).
  const cidadeOptions = useMemo(() => (opcoes?.cidades ?? []).map(c => ({ value: c, label: c })), [opcoes]);
  const cnaeOptions = useMemo(() => (opcoes?.cnaes ?? []).map(c => ({
    value: c.codigo,
    label: `${c.codigo} - ${c.descricao}${c.qtd ? ` (${c.qtd.toLocaleString("pt-BR")})` : ""}`,
  })), [opcoes]);

  // Filtros do form no formato que a API espera (mesmo objeto usado na
  // previa e na criacao -- se divergirem, o total salvo nao bate com o lote).
  const filtrosAtuais = useMemo(() => {
    const f: any = {};
    if (cidadeFiltro.length > 0) f.cidade = cidadeFiltro;
    if (cnaeFiltro.length > 0) f.cnae = cnaeFiltro;
    if (capitalMin) f.capital_min = parseFloat(capitalMin);
    if (fundacaoDe.trim()) f.fundacao_de = fundacaoDe.trim();
    if (porteFiltro.length > 0) f.porte = porteFiltro;
    if (dividaMin) f.divida_min = parseFloat(dividaMin);
    return f;
  }, [cidadeFiltro, cnaeFiltro, capitalMin, fundacaoDe, porteFiltro, dividaMin]);

  // Conta antes de salvar: da pra ajustar o filtro sem criar lote vazio.
  // Espera 600ms parado pra nao contar a cada tecla.
  useEffect(() => {
    let vivo = true;
    setPrevia(null);
    if (Object.keys(filtrosAtuais).length === 0) return;
    setPrevendo(true);
    const t = setTimeout(() => {
      contarEmpresas(filtrosAtuais)
        .then(r => { if (vivo) setPrevia(r.total); })
        .catch(() => { if (vivo) setPrevia(null); })
        .finally(() => { if (vivo) setPrevendo(false); });
    }, 600);
    return () => { vivo = false; clearTimeout(t); setPrevendo(false); };
  }, [filtrosAtuais]);

  async function handleCriarLote(e: React.FormEvent) {
    e.preventDefault();
    if (!nomeLote.trim()) {
      setErro("Nome do lote é obrigatório.");
      return;
    }
    setCriando(true);
    setErro(null);
    setSucesso(null);
    try {
      await criarLote({ nome: nomeLote.trim(), filtros: filtrosAtuais });
      setSucesso("Lote criado com sucesso!");
      setNomeLote("");
      setCidadeFiltro([]);
      setCnaeFiltro([]);
      setCapitalMin("");
      setFundacaoDe("");
      setPorteFiltro([]);
      setDividaMin("");
      carregar();
    } catch (e: any) {
      setErro(e?.message || "Erro ao criar lote.");
    } finally {
      setCriando(false);
    }
  }

  async function salvarTemplateBloco(canal: CanalLote, bloco: number, valor: string) {
    if (!loteDetalhe) return;
    const id = valor ? Number(valor) : null;
    try {
      await definirTemplateBloco(loteDetalhe.id, canal, bloco, id);
      setLoteDetalhe({
        ...loteDetalhe,
        composicao: {
          ...loteDetalhe.composicao,
          blocos: loteDetalhe.composicao.blocos.map((b: any) =>
            b.canal === canal && b.bloco === bloco ? { ...b, template_id: id } : b),
        },
      });
    } catch {
      setErro("Não consegui salvar o modelo deste bloco.");
    }
  }

  async function handleRecalcular(id: number) {
    setRecalculando(id);
    setErro(null);
    try {
      const r = await recalcularLote(id);
      setSucesso(`Composição refeita: ${r.total.toLocaleString("pt-BR")} empresas.`);
      if (loteDetalhe?.id === id) await verDetalhes(id);
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao recalcular.");
    } finally {
      setRecalculando(null);
    }
  }

  async function handleExcluir(id: number) {
    if (!confirm("Tem certeza que deseja excluir este lote?")) return;
    try {
      await deletarLote(id);
      if (loteDetalhe?.id === id) setLoteDetalhe(null);
      carregar();
    } catch (e: any) {
      alert(e?.message || "Erro ao excluir lote.");
    }
  }

  async function verDetalhes(id: number) {
    try {
      const d = await getLote(id);
      setLoteDetalhe(d);
    } catch (e: any) {
      alert(e?.message || "Erro ao carregar detalhes do lote.");
    }
  }

  async function handleCriarCampanha(e: React.FormEvent) {
    e.preventDefault();
    if (!modalCampanhaLote) return;
    setEnviandoCampanha(true);
    setErro(null);
    try {
      await criarCampanhaDoLote(modalCampanhaLote.id, {
        nome_campanha: nomeCampanha || undefined,
        template_id: templateIdCampanha ? Number(templateIdCampanha) : undefined,
        canal: canalCampanha,
        mensagem: canalCampanha === "whatsapp" ? mensagemCampanha : undefined,
        // 300 = teto diario do Brevo free; o backend corta no que couber.
        tamanho_lote: parseInt(tamanhoLoteEnvio) || 300,
      });
      alert("Campanha criada com sucesso a partir do lote!");
      setModalCampanhaLote(null);
      setNomeCampanha("");
      setMensagemCampanha("");
    } catch (e: any) {
      alert(e?.message || "Erro ao criar campanha.");
    } finally {
      setEnviandoCampanha(false);
    }
  }

  function togglePorte(p: string) {
    setPorteFiltro(prev =>
      prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">📦 Lotes de Leads e Perfil</h1>
          <p className="text-sm text-slate-500">Listas de empresas salvas a partir de um filtro, prontas para virar campanha.</p>
        </div>
      </div>

      {erro && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700">{erro}</div>
      )}
      {sucesso && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-sm text-emerald-700">{sucesso}</div>
      )}

      {/* Formulário de Criação de Lote */}
      <div className="rounded-2xl border border-dashed border-indigo-300 bg-indigo-50/50 p-6 text-center">
        <p className="font-medium text-slate-800">Os lotes são criados na tela de Empresas</p>
        <p className="mx-auto mt-1 max-w-xl text-sm text-slate-600">
          Lá você filtra por busca, cidade, setor, porte, passivo, capital e data de
          fundação — e o lote nasce exatamente com o que a tela mostra. O formulário
          que existia aqui aceitava menos campos e gerava lotes diferentes do filtro.
        </p>
        <Link
          href="/dashboard"
          className="mt-4 inline-block rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          Ir para Empresas e criar um lote
        </Link>
      </div>

      {/* Lista de Lotes */}
      <div className="rounded-2xl bg-white border border-slate-200 overflow-hidden shadow-sm">
        <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">📋 Lotes Salvos ({lotes.length})</h2>
          <button onClick={carregar} className="text-xs text-indigo-600 hover:underline">Atualizar</button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-slate-500">Carregando lotes...</div>
        ) : lotes.length === 0 ? (
          <div className="p-12 text-center text-slate-400">Nenhum lote ainda. Crie o primeiro na tela de Empresas, a partir de um filtro.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {lotes.map(lote => (
              <div key={lote.id} className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50/60 transition-colors">
                <div>
                  <h3 className="font-semibold text-slate-800 text-base">{lote.nome}</h3>
                  <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-slate-500">
                    <span className="font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                      {lote.total_encontrado?.toLocaleString("pt-BR")} empresas encontradas
                    </span>
                    <span>Criado em: {new Date(lote.created_at).toLocaleDateString("pt-BR")}</span>
                    {lote.filtros?.cnae && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">CNAE: {lote.filtros.cnae.join(", ")}</span>
                    )}
                    {lote.filtros?.capital_min && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">Capital ≥ R$ {Number(lote.filtros.capital_min).toLocaleString("pt-BR")}</span>
                    )}
                    {lote.filtros?.cidade && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">Cidade: {lote.filtros.cidade.join(", ")}</span>
                    )}
                    {lote.filtros?.potencial && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">Potencial: {lote.filtros.potencial.join(", ")}</span>
                    )}
                    {lote.filtros?.porte && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">Porte: {lote.filtros.porte.join(", ")}</span>
                    )}
                    {lote.filtros?.fundacao_de && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">Fundada após: {lote.filtros.fundacao_de}</span>
                    )}
                    {lote.filtros?.divida_min != null && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">Dívida ≥ R$ {Number(lote.filtros.divida_min).toLocaleString("pt-BR")}</span>
                    )}
                    {lote.filtros?.busca && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">Busca: {lote.filtros.busca}</span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">O lote salva os filtros + o total calculado na hora. A campanha herda exatamente esses filtros.</p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => verDetalhes(lote.id)}
                    className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    👁️ Ver Amostra
                  </button>
                  <button
                    onClick={() => setModalCampanhaLote(lote)}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                  >
                    Criar campanha
                  </button>
                  <button
                    onClick={() => verDetalhes(lote.id)}
                    className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Ver composição
                  </button>
                  <button
                    onClick={() => handleRecalcular(lote.id)}
                    disabled={recalculando === lote.id}
                    className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                    title="Refaz a lista a partir do filtro salvo"
                  >
                    {recalculando === lote.id ? "Recalculando..." : "Recalcular"}
                  </button>
                  <button
                    onClick={() => handleExcluir(lote.id)}
                    className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100"
                  >
                    Excluir
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal de Detalhes / Amostra */}
      {loteDetalhe && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-xl overflow-hidden">
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="font-bold text-slate-800 text-lg">{loteDetalhe.nome}</h3>
                <p className="text-xs text-slate-500">Total de empresas: {loteDetalhe.total_encontrado?.toLocaleString("pt-BR")}</p>
              </div>
              <button onClick={() => setLoteDetalhe(null)} className="text-slate-400 hover:text-slate-700 text-xl font-bold">✕</button>
            </div>
            <div className="p-5 flex-1 overflow-y-auto space-y-3">
              <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
                <p className="text-xs font-semibold text-slate-600 mb-1.5">Este lote é composto por</p>
                <div className="flex flex-wrap gap-1.5">
                  {descreverFiltros(loteDetalhe.filtros).map((t: string, i: number) => (
                    <span key={i} className="rounded-full bg-white border border-slate-300 px-2.5 py-1 text-xs text-slate-700">{t}</span>
                  ))}
                  {descreverFiltros(loteDetalhe.filtros).length === 0 && (
                    <span className="text-xs text-slate-400">Sem filtro — base inteira.</span>
                  )}
                </div>
              </div>

              {loteDetalhe.composicao?.canais ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    {(["email", "whatsapp", "sem_contato"] as CanalLote[]).map(c => {
                      const d = loteDetalhe.composicao.canais[c];
                      const rotulo = c === "email" ? "E-mail" : c === "whatsapp" ? "WhatsApp" : "Sem contato";
                      return (
                        <div key={c} className="rounded-xl border border-slate-200 p-3">
                          <p className="text-[11px] uppercase tracking-wide text-slate-500">{rotulo}</p>
                          <p className="text-xl font-semibold tabular-nums text-slate-800">
                            {(d?.total ?? 0).toLocaleString("pt-BR")}
                          </p>
                          {!!d?.enviados && (
                            <p className="text-[11px] text-emerald-700">{d.enviados} já enviados</p>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                      Fila de envio
                    </h4>
                    <div className="border border-slate-200 rounded-xl divide-y divide-slate-100">
                      {loteDetalhe.composicao.blocos.map((b: any) => (
                        <div key={`${b.canal}-${b.bloco}`} className="flex flex-wrap items-center gap-2 p-2.5 text-sm">
                          <span className="font-medium text-slate-700 w-32">
                            {b.canal === "email" ? "E-mail" : b.canal === "whatsapp" ? "WhatsApp" : "Sem contato"} · bloco {b.bloco}
                          </span>
                          <span className="text-xs text-slate-500 w-24">{b.empresas} empresas</span>
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            b.status === "enviado" ? "bg-emerald-50 text-emerald-700"
                            : b.status === "enviando" ? "bg-amber-50 text-amber-700"
                            : "bg-slate-100 text-slate-600"}`}>
                            {b.status}
                          </span>
                          {b.canal === "email" && (
                            <select
                              value={b.template_id ?? ""}
                              onChange={e => salvarTemplateBloco(b.canal, b.bloco, e.target.value)}
                              className="ml-auto rounded-lg border border-slate-300 px-2 py-1 text-xs"
                            >
                              <option value="">Escolher modelo...</option>
                              {templates.map(t => <option key={t.id} value={t.id}>{t.nome}</option>)}
                            </select>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800">
                  Lote criado antes da composição por canal. Ele ainda funciona pelo filtro
                  salvo, mas não mostra blocos nem separação de e-mail e WhatsApp.
                </div>
              )}
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Amostra de Empresas (Até 50 registros)</h4>
              {loteDetalhe.amostra_empresas?.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-6">Nenhuma empresa encontrada com estes filtros.</p>
              ) : (
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-100 text-slate-600 border-b border-slate-200">
                      <tr>
                        <th className="p-3">CNPJ</th>
                        <th className="p-3">Razão Social</th>
                        <th className="p-3">Município</th>
                        <th className="p-3">CNAE</th>
                        <th className="p-3">Capital Social</th>
                        <th className="p-3">Contato</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {loteDetalhe.amostra_empresas?.map((emp: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="p-3 font-mono">{emp.cnpj_completo}</td>
                          <td className="p-3 font-medium text-slate-800">{emp.razao_social || emp.nome_fantasia}</td>
                          <td className="p-3 text-slate-600">{emp.municipio}</td>
                          <td className="p-3 text-slate-600">{emp.cnae_descricao || emp.cnae_principal || "—"}</td>
                          <td className="p-3 text-slate-600">R$ {Number(emp.capital_social || 0).toLocaleString("pt-BR")}</td>
                          <td className="p-3 text-slate-500">{emp.email || emp.contato_fone || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button onClick={() => setLoteDetalhe(null)} className="px-4 py-2 rounded-xl bg-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-300">Fechar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Criar Campanha do Lote */}
      {modalCampanhaLote && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full flex flex-col shadow-xl overflow-hidden">
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h3 className="font-bold text-slate-800">📧 Criar Campanha para: {modalCampanhaLote.nome}</h3>
              <button onClick={() => setModalCampanhaLote(null)} className="text-slate-400 hover:text-slate-700 text-xl font-bold">✕</button>
            </div>
            <form onSubmit={handleCriarCampanha} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Nome da Campanha</label>
                <input
                  type="text"
                  value={nomeCampanha}
                  onChange={e => setNomeCampanha(e.target.value)}
                  placeholder={`Campanha - Lote: ${modalCampanhaLote.nome}`}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Canal de Envio</label>
                <select
                  value={canalCampanha}
                  onChange={e => setCanalCampanha(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="email">E-mail</option>
                  <option value="whatsapp">WhatsApp (Twilio)</option>
                </select>
              </div>

              {canalCampanha === "email" ? (
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Template de E-mail *</label>
                  <select
                    value={templateIdCampanha}
                    onChange={e => setTemplateIdCampanha(e.target.value ? Number(e.target.value) : "")}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    required
                  >
                    <option value="">Selecione um template...</option>
                    {templates.map(t => (
                      <option key={t.id} value={t.id}>{t.nome} ({t.assunto})</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Mensagem WhatsApp *</label>
                  <textarea
                    value={mensagemCampanha}
                    onChange={e => setMensagemCampanha(e.target.value)}
                    placeholder="Olá {{empresa}}, tudo bem? Somos da..."
                    rows={4}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    required
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Tamanho do Lote Diário</label>
                <input
                  type="number"
                  value={tamanhoLoteEnvio}
                  onChange={e => setTamanhoLoteEnvio(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalCampanhaLote(null)}
                  className="px-4 py-2 rounded-xl bg-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={enviandoCampanha}
                  className="px-5 py-2 rounded-xl bg-indigo-600 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {enviandoCampanha ? "Criando..." : "Confirmar e Campanha"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
