"use client";

import { useEffect, useState } from "react";
import { listarLotes, criarLote, getLote, deletarLote, criarCampanhaDoLote, listarTemplates } from "@/lib/api";

const PORTES_OPCOES = ["MICRO", "EPP", "DEMAIS"];

export default function LotesPage() {
  const [lotes, setLotes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  // Form para criar lote (focado em CNAE, Capital, Fundação, Potencial, etc.)
  const [nomeLote, setNomeLote] = useState("");
  const [potencialFiltro, setPotencialFiltro] = useState<string[]>([]);
  const [cidadeFiltro, setCidadeFiltro] = useState("");
  const [cnaeFiltro, setCnaeFiltro] = useState("");
  const [capitalMin, setCapitalMin] = useState("");
  const [fundacaoDe, setFundacaoDe] = useState("");
  const [porteFiltro, setPorteFiltro] = useState<string[]>([]);
  const [dividaMin, setDividaMin] = useState("");
  const [criando, setCriando] = useState(false);

  // Lote selecionado para detalhe / modal de campanha
  const [loteDetalhe, setLoteDetalhe] = useState<any | null>(null);
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
  }, []);

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
      const filtros: any = {};
      if (potencialFiltro.length > 0) filtros.potencial = potencialFiltro;
      if (cidadeFiltro.trim()) filtros.cidade = [cidadeFiltro.trim()];
      if (cnaeFiltro.trim()) filtros.cnae = cnaeFiltro.split(",").map(s => s.trim()).filter(Boolean);
      if (capitalMin) filtros.capital_min = parseFloat(capitalMin);
      if (fundacaoDe.trim()) filtros.fundacao_de = fundacaoDe.trim();
      if (porteFiltro.length > 0) filtros.porte = porteFiltro;
      if (dividaMin) filtros.divida_min = parseFloat(dividaMin);

      await criarLote({ nome: nomeLote.trim(), filtros });
      setSucesso("Lote criado com sucesso!");
      setNomeLote("");
      setPotencialFiltro([]);
      setCidadeFiltro("");
      setCnaeFiltro("");
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
        tamanho_lote: parseInt(tamanhoLoteEnvio) || 100,
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

  function togglePotencial(tier: string) {
    setPotencialFiltro(prev =>
      prev.includes(tier) ? prev.filter(t => t !== tier) : [...prev, tier]
    );
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
          <p className="text-sm text-slate-500">Crie lotes por CNAE, Capital Social, Fundação, Potencial e Cidade para campanhas em massa.</p>
        </div>
      </div>

      {erro && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700">{erro}</div>
      )}
      {sucesso && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-sm text-emerald-700">{sucesso}</div>
      )}

      {/* Formulário de Criação de Lote */}
      <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800 mb-4">✨ Criar Lote por Perfil Empresarial</h2>
        <form onSubmit={handleCriarLote} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Nome do Lote *</label>
              <input
                type="text"
                value={nomeLote}
                onChange={e => setNomeLote(e.target.value)}
                placeholder="Ex: Indústria - Capital > 100k - POA"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">CNAE / Setor (cabe vários separados por vírgula)</label>
              <input
                type="text"
                value={cnaeFiltro}
                onChange={e => setCnaeFiltro(e.target.value)}
                placeholder="Ex: 47113, 47121"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Capital Social Mínimo (R$)</label>
              <input
                type="number"
                value={capitalMin}
                onChange={e => setCapitalMin(e.target.value)}
                placeholder="Ex: 50000"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Fundada a partir de (Data)</label>
              <input
                type="date"
                value={fundacaoDe}
                onChange={e => setFundacaoDe(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Cidade (Opcional)</label>
              <input
                type="text"
                value={cidadeFiltro}
                onChange={e => setCidadeFiltro(e.target.value)}
                placeholder="Ex: Porto Alegre"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Dívida Mínima (Opcional)</label>
              <input
                type="number"
                value={dividaMin}
                onChange={e => setDividaMin(e.target.value)}
                placeholder="Ex: 0"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Filtro de Potencial</label>
              <div className="flex gap-2">
                {["alto", "medio", "baixo"].map(tier => {
                  const ativo = potencialFiltro.includes(tier);
                  return (
                    <button
                      key={tier}
                      type="button"
                      onClick={() => togglePotencial(tier)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                        ativo
                          ? tier === "alto"
                            ? "bg-emerald-600 text-white shadow-sm"
                            : tier === "medio"
                            ? "bg-amber-600 text-white shadow-sm"
                            : "bg-slate-600 text-white shadow-sm"
                          : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                      }`}
                    >
                      {tier === "alto" ? "🔥 Alto" : tier === "medio" ? "⚡ Médio" : "💤 Baixo"}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Porte da Empresa</label>
              <div className="flex gap-2">
                {PORTES_OPCOES.map(p => {
                  const ativo = porteFiltro.includes(p);
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => togglePorte(p)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                        ativo ? "bg-indigo-600 text-white shadow-sm" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                      }`}
                    >
                      {p}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={criando}
              className="rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-5 py-2.5 text-sm font-medium text-white shadow-md hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50"
            >
              {criando ? "Calculando e Salvando..." : "🚀 Criar e Salvar Lote por Perfil"}
            </button>
          </div>
        </form>
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
          <div className="p-12 text-center text-slate-400">Nenhum lote criado ainda. Use o formulário acima para criar o primeiro lote por perfil.</div>
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
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 text-xs font-medium text-white hover:bg-indigo-700"
                  >
                    📧 Criar Campanha
                  </button>
                  <button
                    onClick={() => handleExcluir(lote.id)}
                    className="px-3 py-1.5 rounded-lg border border-red-200 bg-red-50 text-xs font-medium text-red-600 hover:bg-red-100"
                  >
                    🗑️ Excluir
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
              <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-xs text-slate-600">
                <p className="font-semibold mb-1">Filtros salvos neste lote:</p>
                <pre className="whitespace-pre-wrap font-mono text-[11px]">{JSON.stringify(loteDetalhe.filtros || {}, null, 2)}</pre>
              </div>
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
