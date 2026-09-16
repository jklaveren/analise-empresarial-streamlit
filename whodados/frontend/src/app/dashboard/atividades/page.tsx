"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  listarTodasAtividades, moverAtividadeCrm, deletarAtividadeCrm,
  AtividadeCrm, StatusAtividade,
} from "@/lib/api";

const COLUNAS: { status: StatusAtividade; label: string; cor: string }[] = [
  { status: "pendente", label: "A fazer", cor: "border-slate-300 bg-slate-50" },
  { status: "em_andamento", label: "Em andamento", cor: "border-sky-300 bg-sky-50" },
  { status: "concluida", label: "Concluída", cor: "border-emerald-300 bg-emerald-50" },
];

const TIPO_ICONE: Record<string, string> = {
  tarefa: "📋", ligacao: "📞", reuniao: "🗓️", email: "📧", outro: "•",
};

function formatPrazo(prazo: string | null): { texto: string; atrasado: boolean } {
  if (!prazo) return { texto: "", atrasado: false };
  const d = new Date(prazo + "T00:00:00");
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
  return { texto: d.toLocaleDateString("pt-BR"), atrasado: d < hoje };
}

export default function AtividadesPage() {
  const [atividades, setAtividades] = useState<AtividadeCrm[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [movendo, setMovendo] = useState<number | null>(null);
  const [filtroResp, setFiltroResp] = useState<string>("");

  const carregar = async () => {
    try {
      setAtividades(await listarTodasAtividades());
    } catch {
      setErro("Erro ao carregar atividades.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { carregar(); }, []);

  const responsaveis = useMemo(
    () => Array.from(new Set(atividades.map(a => a.responsavel_username).filter(Boolean))) as string[],
    [atividades]
  );

  const filtradas = filtroResp ? atividades.filter(a => a.responsavel_username === filtroResp) : atividades;

  const mover = async (id: number, status: StatusAtividade) => {
    setMovendo(id);
    setAtividades(prev => prev.map(a => a.id === id ? { ...a, status } : a));
    try { await moverAtividadeCrm(id, status); }
    catch { await carregar(); }
    finally { setMovendo(null); }
  };

  const remover = async (id: number) => {
    if (!confirm("Excluir esta atividade?")) return;
    setAtividades(prev => prev.filter(a => a.id !== id));
    try { await deletarAtividadeCrm(id); } catch { await carregar(); }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Atividades</h1>
          <p className="text-slate-500 mt-1 text-sm">
            Todas as tarefas de todos os clientes, num board só. Pra criar uma nova, abra a empresa em{" "}
            <Link href="/dashboard/crm" className="text-indigo-600 hover:underline">Clientes</Link> e use o "+ Tarefa" no card dela.
          </p>
        </div>
        {responsaveis.length > 0 && (
          <select value={filtroResp} onChange={e => setFiltroResp(e.target.value)} className="text-sm rounded-lg border border-slate-300 px-3 py-2 bg-white">
            <option value="">Todos os responsáveis</option>
            {responsaveis.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        )}
      </header>

      {erro && <div className="rounded-lg bg-red-50 p-4 text-red-700 text-sm">{erro}</div>}

      {loading ? (
        <p className="text-center text-slate-400 py-12">Carregando...</p>
      ) : atividades.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200">
          <div className="text-5xl mb-3">📋</div>
          <p className="text-slate-600 font-medium">Nenhuma atividade ainda</p>
          <p className="text-sm text-slate-400 mt-1">Crie a primeira tarefa a partir do card de um cliente.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {COLUNAS.map(coluna => {
            const itens = filtradas.filter(a => a.status === coluna.status);
            return (
              <div key={coluna.status} className={`rounded-xl border ${coluna.cor} p-3 flex flex-col gap-2 min-h-[300px]`}>
                <div className="flex items-center justify-between px-1">
                  <h2 className="text-sm font-semibold text-slate-700">{coluna.label}</h2>
                  <span className="text-xs font-medium text-slate-500 bg-white rounded-full px-2 py-0.5">{itens.length}</span>
                </div>

                {itens.length === 0 && <p className="text-xs text-slate-400 px-1 py-4 text-center">Nada aqui</p>}

                {itens.map(a => {
                  const prazo = formatPrazo(a.prazo);
                  return (
                    <div key={a.id} className="bg-white rounded-lg border border-slate-200 p-3 shadow-sm">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-slate-800">
                          {TIPO_ICONE[a.tipo] || "•"} {a.titulo}
                        </p>
                        <button onClick={() => remover(a.id)} className="text-slate-300 hover:text-red-500 text-xs shrink-0" title="Excluir">✕</button>
                      </div>
                      <Link href={`/dashboard/empresa/${encodeURIComponent(a.cnpj)}`} className="text-xs text-indigo-600 hover:underline line-clamp-1 block mt-1">
                        {a.razao_social || a.cnpj}
                      </Link>
                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        {a.responsavel_username && (
                          <span className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-full">{a.responsavel_username}</span>
                        )}
                        {prazo.texto && (
                          <span className={`text-xs px-1.5 py-0.5 rounded-full ${prazo.atrasado && a.status !== "concluida" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-500"}`}>
                            {prazo.atrasado && a.status !== "concluida" ? "⚠️ " : ""}{prazo.texto}
                          </span>
                        )}
                      </div>
                      <select
                        value={a.status}
                        disabled={movendo === a.id}
                        onChange={e => mover(a.id, e.target.value as StatusAtividade)}
                        className="mt-2 w-full text-xs border border-slate-200 rounded-md px-2 py-1 text-slate-600 disabled:opacity-50"
                      >
                        {COLUNAS.map(c => (
                          <option key={c.status} value={c.status}>Mover para: {c.label}</option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
