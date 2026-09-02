// Badge de score no card do kanban. Import no componente de card existente
// do dashboard (o mesmo lugar que já mostra CAPITAL_SOCIAL / DIVIDA_TOTAL).
"use client";

import { useEffect, useState } from "react";
import { req } from "@/lib/api"; // já existe: req<T>(path, options) com Bearer token

type ScoreResponse = {
  cnpj: string;
  score: number | null;
  faixa: "quente" | "morno" | "frio" | null;
};

const CORES: Record<string, string> = {
  quente: "bg-red-100 text-red-800",
  morno: "bg-yellow-100 text-yellow-800",
  frio: "bg-blue-100 text-blue-800",
};

export function ScoreBadge({ cnpj }: { cnpj: string }) {
  const [dado, setDado] = useState<ScoreResponse | null>(null);

  useEffect(() => {
    req<ScoreResponse>(`/empresas/${cnpj}/score`).then(setDado).catch(() => setDado(null));
  }, [cnpj]);

  if (!dado?.faixa) return null; // cold start: sem modelo ainda, não mostra nada

  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${CORES[dado.faixa]}`}>
      {dado.faixa} · {Math.round((dado.score ?? 0) * 100)}%
    </span>
  );
}
