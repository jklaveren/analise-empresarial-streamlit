"use client";

import { useEffect, useState } from "react";
import {
  listarHistoricoAtividade,
  comentarAtividade,
  alterarPrazoAtividade,
  type HistoricoAtividade,
  type AtividadeCrm,
} from "@/lib/api";

const ROTULO_STATUS: Record<string, string> = {
  pendente: "Pendente",
  em_andamento: "Em andamento",
  concluida: "Concluída",
};

function quando(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function dataBR(valor: string | null): string {
  if (!valor) return "sem prazo";
  const [a, m, d] = valor.split("-");
  return `${d}/${m}/${a}`;
}

/** Uma linha da linha do tempo, já no jeito "Juliana moveu para Em andamento". */
function descrever(h: HistoricoAtividade): string {
  const autor = h.autor || "alguém";
  if (h.tipo === "comentario") return h.texto || "";
  if (h.tipo === "status") return `${autor} moveu de ${ROTULO_STATUS[h.de || ""] || h.de} para ${ROTULO_STATUS[h.para || ""] || h.para}`;
  return `${autor} mudou o prazo de ${dataBR(h.de)} para ${dataBR(h.para)}`;
}

const ICONE: Record<string, string> = { comentario: "💬", status: "🔀", prazo: "📅" };

export default function AcompanhamentoAtividade({
  atividade,
  onMudou,
}: {
  atividade: AtividadeCrm;
  /** Chamado quando algo muda no servidor, pra lista recarregar prazo/semáforo. */
  onMudou: () => void;
}) {
  const [historico, setHistorico] = useState<HistoricoAtividade[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [texto, setTexto] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [novoPrazo, setNovoPrazo] = useState(atividade.prazo || "");

  async function carregar() {
    setCarregando(true);
    try {
      setHistorico(await listarHistoricoAtividade(atividade.id));
    } finally {
      setCarregando(false);
    }
  }

  // status/prazo entram nas dependencias porque a mudanca acontece FORA deste
  // painel (o select do card) e tambem vira uma linha do historico.
  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atividade.id, atividade.status, atividade.prazo]);

  useEffect(() => {
    setNovoPrazo(atividade.prazo || "");
  }, [atividade.prazo]);

  async function comentar(e: React.FormEvent) {
    e.preventDefault();
    if (!texto.trim()) return;
    setSalvando(true);
    try {
      await comentarAtividade(atividade.id, texto.trim());
      setTexto("");
      await carregar();
      onMudou();
    } finally {
      setSalvando(false);
    }
  }

  async function salvarPrazo(valor: string) {
    setNovoPrazo(valor);
    if (valor === (atividade.prazo || "")) return;
    await alterarPrazoAtividade(atividade.id, valor);
    await carregar();
    onMudou();
  }

  return (
    <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
      <div className="flex items-center gap-2">
        <label className="text-[11px] uppercase tracking-wide text-slate-400 font-medium">Prazo</label>
        <input
          type="date"
          value={novoPrazo}
          onChange={e => salvarPrazo(e.target.value)}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 cursor-pointer"
        />
      </div>

      <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
        {carregando ? (
          <p className="text-xs text-slate-400">Carregando acompanhamento...</p>
        ) : historico.length === 0 ? (
          <p className="text-xs text-slate-400">Nada registrado ainda. Escreva o primeiro comentário abaixo.</p>
        ) : (
          historico.map(h => (
            <div key={h.id} className="flex gap-2 text-xs">
              <span className="shrink-0">{ICONE[h.tipo] || "•"}</span>
              <div className="min-w-0 flex-1">
                <p className={h.tipo === "comentario" ? "text-slate-700 whitespace-pre-wrap" : "text-slate-500"}>
                  {descrever(h)}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5">
                  {h.tipo === "comentario" && h.autor ? `${h.autor} · ` : ""}
                  {quando(h.criado_em)}
                </p>
              </div>
            </div>
          ))
        )}
      </div>

      <form onSubmit={comentar} className="flex gap-2">
        <input
          type="text"
          value={texto}
          onChange={e => setTexto(e.target.value)}
          placeholder="Escrever um comentário..."
          className="flex-1 rounded-md border border-slate-200 px-2 py-1.5 text-xs outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={salvando || !texto.trim()}
          className="text-xs bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white px-3 rounded-md"
        >
          {salvando ? "..." : "Enviar"}
        </button>
      </form>
    </div>
  );
}
