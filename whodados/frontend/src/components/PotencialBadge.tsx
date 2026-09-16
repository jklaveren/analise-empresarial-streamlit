import { PotencialTier } from "@/lib/api";

const ESTILOS: Record<PotencialTier, string> = {
  alto: "bg-emerald-100 text-emerald-700",
  medio: "bg-amber-100 text-amber-700",
  baixo: "bg-slate-100 text-slate-500",
};

const LABELS: Record<PotencialTier, string> = {
  alto: "Alto",
  medio: "Médio",
  baixo: "Baixo",
};

/** Badge do score de potencial (0-100) calculado no backend a partir de
 * porte, capital social, dívida, maturidade e contactabilidade. */
export function PotencialBadge({ tier, score }: { tier: PotencialTier; score?: number }) {
  return (
    <span
      title={score != null ? `Score: ${score}/100` : undefined}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${ESTILOS[tier]}`}
    >
      {LABELS[tier]}
    </span>
  );
}
