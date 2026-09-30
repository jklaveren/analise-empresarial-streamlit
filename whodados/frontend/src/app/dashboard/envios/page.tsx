"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getPainelEnvios, type ItemFila } from "@/lib/api";

const num = (v: number | undefined) => (v ?? 0).toLocaleString("pt-BR");

function pct(parte: number | undefined, total: number | undefined) {
  // Sem total nao da' pra calcular: "—" (sem dado). Mas parte = 0 COM total
  // e' 0% de verdade, e num painel de entrega zero e' o alarme mais
  // importante que existe -- antes o `!parte` mandava ele pro mesmo "—" de
  // "ainda nao sei", escondendo justamente o caso critico.
  if (!total) return "—";
  if (parte == null) return "—";
  return `${Math.round((parte / total) * 100)}%`;
}

const ROTULO_CANAL: Record<string, string> = {
  email: "E-mail",
  whatsapp: "WhatsApp",
  sem_contato: "Sem contato",
};

function Indicador({ titulo, valor, apoio, destaque }: {
  titulo: string; valor: string; apoio?: string; destaque?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-4 ${destaque ? "border-indigo-200 bg-indigo-50/60" : "border-slate-200 bg-white"}`}>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{titulo}</div>
      <div className={`mt-1.5 text-2xl font-semibold tabular-nums ${destaque ? "text-indigo-700" : "text-slate-800"}`}>
        {valor}
      </div>
      {apoio && <div className="mt-0.5 text-[11px] text-slate-500">{apoio}</div>}
    </div>
  );
}


/** Funil de entrega. SVG inline em vez de biblioteca: sao 5 barras, e um
 *  grafico generico nao mostra a taxa entre etapas, que e o que interessa. */
function Funil({ etapas }: { etapas: { rotulo: string; valor: number; cor: string }[] }) {
  const base = etapas[0]?.valor || 0;
  if (!base) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">
        Nenhum envio nos últimos 30 dias. O funil aparece depois do primeiro disparo.
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="space-y-2.5">
        {etapas.map((et, i) => {
          const largura = Math.max((et.valor / base) * 100, et.valor ? 2 : 0);
          const anterior = i > 0 ? etapas[i - 1].valor : null;
          const queda = anterior && anterior > et.valor ? anterior - et.valor : 0;
          return (
            <div key={et.rotulo}>
              <div className="mb-1 flex items-baseline justify-between text-sm">
                <span className="font-medium text-slate-700">{et.rotulo}</span>
                <span className="tabular-nums text-slate-800">
                  {et.valor.toLocaleString("pt-BR")}
                  {anterior ? (
                    <span className="ml-2 text-xs text-slate-400">
                      {Math.round((et.valor / anterior) * 100)}% do anterior
                    </span>
                  ) : null}
                </span>
              </div>
              <div className="h-7 w-full overflow-hidden rounded-md bg-slate-100">
                <div
                  className="h-full rounded-md transition-all"
                  style={{ width: `${largura}%`, backgroundColor: et.cor }}
                />
              </div>
              {queda > 0 && (
                <div className="mt-0.5 text-[11px] text-slate-400">
                  −{queda.toLocaleString("pt-BR")} nesta etapa
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Volume diario. Barras finas com o eixo implicito -- o interesse e a
 *  regularidade do ritmo, nao o valor exato de cada dia. */
/** Completa os dias sem envio com zero.
 *
 *  O backend monta `por_dia` com GROUP BY dia, entao dia sem envio nao vem
 *  como zero: nao vem. Desenhando so' o que chega, duas semanas com 2 envios
 *  esparsos viravam o mesmo desenho de 2 dias seguidos -- e o grafico existe
 *  justamente pra mostrar regularidade de ritmo.
 *
 *  Preenche entre o primeiro e o ultimo dia recebidos. Nao estica ate' a
 *  borda da janela de 30 dias porque a API nao diz onde ela comeca; o que
 *  isto conserta e' o espacamento relativo, que era o erro. */
function preencherDias(dados: { dia: string; n: number }[]) {
  if (dados.length < 2) return dados;
  // Ordena antes de varrer: o backend hoje devolve ORDER BY dia, mas se um
  // dia vier fora de ordem o cursor ja' nasceria depois do fim, o laco nao
  // roda e o retorno vazio faz o grafico sumir da tela sem dizer nada.
  const ordenado = [...dados].sort((a, b) => a.dia.localeCompare(b.dia));
  const porDia = new Map(ordenado.map(d => [d.dia, d.n]));
  const cheio: { dia: string; n: number }[] = [];
  const fim = new Date(`${ordenado[ordenado.length - 1].dia}T00:00:00Z`);
  const cursor = new Date(`${ordenado[0].dia}T00:00:00Z`);
  // Guarda contra data invalida: sem isto um `dia` malformado viraria laco
  // infinito na tela.
  if (Number.isNaN(cursor.getTime()) || Number.isNaN(fim.getTime())) return dados;
  while (cursor <= fim && cheio.length < 400) {
    const chave = cursor.toISOString().slice(0, 10);
    cheio.push({ dia: chave, n: porDia.get(chave) ?? 0 });
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return cheio;
}

function VolumeDiario({ dados: recebidos }: { dados: { dia: string; n: number }[] }) {
  const dados = preencherDias(recebidos);
  if (!dados.length) return null;
  const max = Math.max(...dados.map(d => d.n), 1);
  const total = dados.reduce((s, d) => s + d.n, 0);
  const media = Math.round(total / dados.length);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-800">Volume por dia</h3>
        <span className="text-xs text-slate-500">
          média de {media.toLocaleString("pt-BR")}/dia
        </span>
      </div>
      <div className="flex h-24 items-end gap-1">
        {dados.map(d => (
          <div key={d.dia} className="group relative flex-1" title={`${d.dia}: ${d.n}`}>
            <div
              className="w-full rounded-t bg-indigo-400 transition-colors group-hover:bg-indigo-600"
              style={{ height: `${Math.max((d.n / max) * 96, 2)}px` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-slate-400">
        <span>{dados[0]?.dia.slice(5)}</span>
        <span>{dados[dados.length - 1]?.dia.slice(5)}</span>
      </div>
    </div>
  );
}

function LinhaFila({ item }: { item: ItemFila }) {
  const concluido = item.pendentes === 0;
  const enviados = item.total - item.pendentes;
  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-slate-50">
      <div className="min-w-48 flex-1">
        <Link href="/dashboard/lotes" className="font-medium text-slate-800 hover:text-indigo-700">
          {item.lote}
        </Link>
        <div className="text-xs text-slate-500">
          {ROTULO_CANAL[item.canal] ?? item.canal} · bloco {item.bloco}
          {item.template && <> · {item.template}</>}
          {!item.template && item.canal === "email" && (
            <span className="text-amber-600"> · sem modelo escolhido</span>
          )}
        </div>
      </div>

      <div className="w-40">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className={`h-full ${concluido ? "bg-emerald-500" : "bg-indigo-500"}`}
            style={{ width: `${item.total ? (enviados / item.total) * 100 : 0}%` }}
          />
        </div>
        <div className="mt-1 text-[11px] tabular-nums text-slate-500">
          {num(enviados)} de {num(item.total)}
        </div>
      </div>

      <span className={`rounded-full px-2.5 py-1 text-xs ${
        concluido ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
        {concluido ? "concluído" : `${num(item.pendentes)} na fila`}
      </span>
    </div>
  );
}

export default function EnviosPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["painel-envios"],
    queryFn: () => getPainelEnvios(30),
    refetchInterval: 60_000,
  });

  if (isLoading) return <p className="py-12 text-center text-slate-400">Carregando...</p>;
  if (isError || !data) {
    return <div className="rounded-lg bg-red-50 p-4 text-red-700">Não consegui carregar o painel.</div>;
  }

  const { resumo, engajamento: e, hoje, fila } = data;
  const naFila = fila.filter(f => f.pendentes > 0);
  const concluidos = fila.filter(f => f.pendentes === 0);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">Envios</h1>
        <p className="mt-1 text-slate-500">
          O que sai hoje, o que falta e o que aconteceu com o que já saiu.
        </p>
      </header>

      <section>
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">Hoje</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Indicador
            titulo="Enviados hoje" destaque
            valor={num(hoje.enviados)}
            apoio={hoje.limite ? `de ${num(hoje.limite)} do limite diário` : undefined}
          />
          <Indicador
            titulo="Ainda cabe hoje"
            valor={hoje.restante == null ? "sem limite" : num(hoje.restante)}
            apoio={`${hoje.por_rodada} a cada 10 min`}
          />
          <Indicador titulo="Janela de envio" valor={hoje.janela} apoio="segunda a sexta" />
          <Indicador
            titulo="Dias para esvaziar"
            valor={resumo.dias_para_esvaziar ? String(resumo.dias_para_esvaziar) : "—"}
            apoio={`${num(resumo.empresas_na_fila)} empresas na fila`}
          />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
          Últimos 30 dias
        </h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <Indicador titulo="Enviados" valor={num(e.enviados)} />
          <Indicador titulo="Entregues" valor={num(e.entregues)} apoio={pct(e.entregues, e.enviados)} />
          <Indicador titulo="Abriram" valor={num(e.abertos)} apoio={pct(e.abertos, e.entregues || e.enviados)} />
          <Indicador titulo="Clicaram" valor={num(e.clicados)} apoio={pct(e.clicados, e.abertos)} />
          <Indicador titulo="Não entregues" valor={num(e.bounces)} apoio={pct(e.bounces, e.enviados)} />
          <Indicador titulo="Barrados na conferência" valor={num(e.bloqueados)} />
        </div>
        {!e.entregues && !!e.enviados && (
          <p className="mt-2 text-xs text-amber-700">
            Entrega, abertura e clique dependem do rastreamento. Se ficarem zerados com
            envios acontecendo, o pixel e os links não estão sendo registrados.
          </p>
        )}

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Funil etapas={[
            { rotulo: "Enviados", valor: e.enviados ?? 0, cor: "#6366f1" },
            { rotulo: "Entregues", valor: e.entregues ?? 0, cor: "#0ea5e9" },
            { rotulo: "Abriram", valor: e.abertos ?? 0, cor: "#0d9488" },
            { rotulo: "Clicaram", valor: e.clicados ?? 0, cor: "#16a34a" },
          ]} />
          <VolumeDiario dados={data.por_dia} />
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
          Fila ({naFila.length})
        </h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {naFila.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-slate-500">
              Nada na fila.{" "}
              <Link href="/dashboard" className="font-medium text-indigo-600 hover:underline">
                Filtre empresas e crie um lote
              </Link>{" "}
              para começar.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {naFila.map(f => <LinhaFila key={`${f.lote_id}-${f.canal}-${f.bloco}`} item={f} />)}
            </div>
          )}
        </div>
      </section>

      {concluidos.length > 0 && (
        <section>
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
            Concluídos ({concluidos.length})
          </h2>
          <div className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white opacity-75">
            {concluidos.map(f => <LinhaFila key={`${f.lote_id}-${f.canal}-${f.bloco}`} item={f} />)}
          </div>
        </section>
      )}
    </div>
  );
}
