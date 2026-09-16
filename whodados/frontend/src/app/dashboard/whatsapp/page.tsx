"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError, ConversaWhatsApp, MensagemWhatsApp,
  listarConversasWhatsApp, listarMensagensWhatsApp, enviarWhatsApp,
} from "@/lib/api";

// Sem WebSocket no backend ainda -- poll simples. 8s e' rapido o bastante pra
// parecer "quase em tempo real" sem martelar o Twilio/Postgres.
const POLL_MS = 8000;

function formatHora(iso: string) {
  const d = new Date(iso);
  const hoje = new Date();
  const mesmoDia = d.toDateString() === hoje.toDateString();
  return mesmoDia
    ? d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export default function WhatsAppPage() {
  const qc = useQueryClient();
  const [telefoneAtivo, setTelefoneAtivo] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const fimDaThreadRef = useRef<HTMLDivElement>(null);

  const conversasQuery = useQuery({
    queryKey: ["whatsapp-conversas"],
    queryFn: listarConversasWhatsApp,
    refetchInterval: POLL_MS,
  });
  const conversas: ConversaWhatsApp[] = conversasQuery.data ?? [];

  // Abre a primeira conversa automaticamente quando a lista carrega.
  useEffect(() => {
    if (!telefoneAtivo && conversas.length > 0) setTelefoneAtivo(conversas[0].telefone);
  }, [conversas, telefoneAtivo]);

  const mensagensQuery = useQuery({
    queryKey: ["whatsapp-mensagens", telefoneAtivo],
    queryFn: () => listarMensagensWhatsApp(telefoneAtivo as string),
    enabled: !!telefoneAtivo,
    refetchInterval: telefoneAtivo ? POLL_MS : false,
  });
  const mensagens: MensagemWhatsApp[] = mensagensQuery.data ?? [];
  const conversaAtiva = useMemo(() => conversas.find(c => c.telefone === telefoneAtivo) ?? null, [conversas, telefoneAtivo]);

  useEffect(() => {
    fimDaThreadRef.current?.scrollIntoView({ block: "end" });
  }, [mensagens.length, telefoneAtivo]);

  const handleAbrirConversa = (telefone: string) => {
    setTelefoneAtivo(telefone);
    setErro("");
  };

  const handleEnviar = async () => {
    if (!telefoneAtivo || !rascunho.trim()) return;
    setEnviando(true);
    setErro("");
    try {
      await enviarWhatsApp(telefoneAtivo, rascunho.trim(), conversaAtiva?.cnpj ?? undefined);
      setRascunho("");
      await qc.invalidateQueries({ queryKey: ["whatsapp-mensagens", telefoneAtivo] });
      await qc.invalidateQueries({ queryKey: ["whatsapp-conversas"] });
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Falha ao enviar mensagem.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="space-y-4 h-full">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">WhatsApp</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Conversas via Twilio. Configure SID/Token/Número em{" "}
          <Link href="/dashboard/configuracoes" className="text-indigo-600 hover:underline">Configurações → Integrações</Link>
          {" "}para enviar; para receber, aponte o webhook do WhatsApp no Twilio para{" "}
          <code className="bg-slate-100 px-1 rounded text-xs">/api/v1/integracoes/whatsapp/webhook</code> da API pública.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 rounded-xl bg-white shadow-sm border border-slate-200 overflow-hidden" style={{ height: "70vh" }}>
        {/* Lista de conversas */}
        <div className="border-r border-slate-200 overflow-y-auto">
          {conversasQuery.isPending ? (
            <div className="p-4 text-center text-slate-400 text-sm">Carregando...</div>
          ) : conversas.length === 0 ? (
            <div className="p-4 text-center text-slate-400 text-sm">Nenhuma conversa ainda. Mensagens recebidas via Twilio aparecem aqui.</div>
          ) : conversas.map(c => (
            <button
              key={c.telefone}
              onClick={() => handleAbrirConversa(c.telefone)}
              className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition-colors ${
                c.telefone === telefoneAtivo ? "bg-indigo-50" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-sm text-slate-800 truncate">
                  {c.razao_social || c.telefone}
                </span>
                {c.nao_lidas > 0 && (
                  <span className="flex-shrink-0 bg-emerald-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
                    {c.nao_lidas}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 font-mono">{c.telefone}</p>
              <p className="text-xs text-slate-400 truncate mt-0.5">
                {c.ultima_direcao === "saida" ? "Você: " : ""}{c.ultima_mensagem}
              </p>
            </button>
          ))}
        </div>

        {/* Thread */}
        <div className="md:col-span-2 flex flex-col">
          {!telefoneAtivo ? (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
              Selecione uma conversa
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-slate-800 text-sm">{conversaAtiva?.razao_social || telefoneAtivo}</p>
                  <p className="text-xs text-slate-500 font-mono">{telefoneAtivo}</p>
                </div>
                {conversaAtiva?.cnpj && (
                  <Link
                    href={`/dashboard/empresa/${encodeURIComponent(conversaAtiva.cnpj)}`}
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    Ver empresa
                  </Link>
                )}
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-slate-50">
                {mensagensQuery.isPending ? (
                  <p className="text-center text-slate-400 text-sm">Carregando...</p>
                ) : mensagens.length === 0 ? (
                  <p className="text-center text-slate-400 text-sm">Sem mensagens ainda.</p>
                ) : mensagens.map(m => (
                  <div key={m.id} className={`flex ${m.direcao === "saida" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[75%] rounded-2xl px-3 py-2 text-sm ${
                      m.direcao === "saida" ? "bg-indigo-600 text-white" : "bg-white border border-slate-200 text-slate-800"
                    }`}>
                      <p className="whitespace-pre-wrap break-words">{m.corpo}</p>
                      <p className={`text-[10px] mt-1 ${m.direcao === "saida" ? "text-indigo-200" : "text-slate-400"}`}>
                        {formatHora(m.criado_em)}
                      </p>
                    </div>
                  </div>
                ))}
                <div ref={fimDaThreadRef} />
              </div>

              {erro && <div className="px-4 py-2 text-xs text-red-600 bg-red-50">{erro}</div>}

              <div className="p-3 border-t border-slate-100 flex gap-2">
                <input
                  type="text"
                  value={rascunho}
                  onChange={e => setRascunho(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !enviando) handleEnviar(); }}
                  placeholder="Digite uma mensagem..."
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
                />
                <button
                  onClick={handleEnviar}
                  disabled={enviando || !rascunho.trim()}
                  className="bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  Enviar
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
