// Campo de busca em linguagem natural. Sugestão de onde plugar: topo de
// /dashboard, acima da tabela de empresas que já existe.
"use client";

import { useState } from "react";
import { req } from "@/lib/api";

type RespostaConsulta = {
  resumo_em_texto: string;
  total_encontrado: number;
  empresas: Record<string, unknown>[];
};

export function BuscaNatural({ onResultado }: { onResultado: (empresas: Record<string, unknown>[]) => void }) {
  const [pergunta, setPergunta] = useState("");
  const [resumo, setResumo] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function buscar() {
    if (!pergunta.trim()) return;
    setCarregando(true);
    setErro(null);
    try {
      const resposta = await req<RespostaConsulta>("/empresas/consulta-natural", {
        method: "POST",
        body: JSON.stringify({ pergunta }),
      });
      setResumo(resposta.resumo_em_texto);
      onResultado(resposta.empresas);
    } catch (e) {
      setErro("Não consegui interpretar essa pergunta. Tente reformular.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="mb-4">
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border px-3 py-2 text-sm"
          placeholder='Ex: "empresas de comércio em Porto Alegre com dívida acima de 100 mil"'
          value={pergunta}
          onChange={(e) => setPergunta(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && buscar()}
        />
        <button
          onClick={buscar}
          disabled={carregando}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {carregando ? "Buscando..." : "Buscar"}
        </button>
      </div>
      {resumo && <p className="mt-2 text-sm text-slate-600">{resumo}</p>}
      {erro && <p className="mt-2 text-sm text-red-600">{erro}</p>}
    </div>
  );
}
