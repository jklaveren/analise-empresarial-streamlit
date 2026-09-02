"use client";
import { useState, useEffect } from "react";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
async function get<T>(p: string) {
  const r = await fetch(`${API}${p}`, { headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` } });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json() as T;
}
async function post<T>(p: string, b: object) {
  const r = await fetch(`${API}${p}`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("token") || ""}` }, body: JSON.stringify(b) });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json() as T;
}
interface Cfg { smtp_host: string; smtp_port: number; smtp_username: string; smtp_use_tls: boolean; email_from: string; email_from_name: string; configurado: boolean; }
interface Pres { presets: Record<string, { name: string; host: string; port: number; tls: boolean }> }
export default function EmailConfigPage() {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [pre, setPre] = useState<Record<string, { name: string; host: string; port: number; tls: boolean }>>({});
  const [sel, setSel] = useState("custom");
  const [load, setLoad] = useState(true);
  const [h, setH] = useState("");
  const [p, setP] = useState(587);
  const [u, setU] = useState("");
  const [pw, setPw] = useState("");
  const [tls, setTls] = useState(true);
  const [te, setTe] = useState("");
  const [fb, setFb] = useState<{ t: "s" | "e"; m: string } | null>(null);
  const [tt, setTt] = useState(false);
  const [et, setEt] = useState(false);
  useEffect(() => { (async () => { setLoad(true); try { const [c, ps] = await Promise.all([get<Cfg>("/api/v1/admin/smtp/config"), get<Pres>("/api/v1/admin/smtp/presets")]); setCfg(c); setPre(ps.presets || {}); setH(c.smtp_host); setP(c.smtp_port); setU(c.smtp_username); setTls(c.smtp_use_tls); } catch { } setLoad(false); })(); }, []);
  const selP = (k: string) => { setSel(k); const x = pre[k]; if (x?.host) { setH(x.host); setP(x.port); setTls(x.tls); } };
  const tCon = async () => { if (!h || !u || !pw) { setFb({ t: "e", m: "Preencha host, usuario e senha" }); return; } setFb(null); setTt(true); try { const r = await post<{ sucesso: boolean; message: string }>("/api/v1/admin/smtp/test-connection", { host: h, port: p, username: u, password: pw, use_tls: tls }); setFb({ t: r.sucesso ? "s" : "e", m: r.message }); } catch { setFb({ t: "e", m: "Erro" }); } setTt(false); };
  const tSend = async () => { if (!te || !te.includes("@")) { setFb({ t: "e", m: "Email invalido" }); return; } setFb(null); setEt(true); try { const r = await post<{ sucesso: boolean; message: string }>("/api/v1/admin/smtp/test-send", { para: te }); setFb({ t: r.sucesso ? "s" : "e", m: r.message }); } catch { setFb({ t: "e", m: "Erro" }); } setEt(false); };
  if (load) return <div className="p-8 text-slate-500">Carregando...</div>;
  return (<div className="max-w-4xl mx-auto p-6 space-y-6"><h1 className="text-2xl font-bold">Configuracao de Email</h1><p className="text-slate-500">Configure o servidor SMTP</p><div className={`rounded-xl p-5 border-2 ${cfg?.configurado ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}`}><div className="flex items-center gap-3"><div>{cfg?.configurado ? "OK" : "!"}</div><div><h2 className={`font-semibold ${cfg?.configurado ? "text-green-800" : "text-amber-800"}`}>{cfg?.configurado ? "SMTP Configurado" : "SMTP Nao Configurado"}</h2>{cfg?.configurado ? <div className="text-sm text-green-700 mt-1"><div>Servidor: <strong>{cfg.smtp_host}:{cfg.smtp_port}</strong></div><div>Usuario: <strong>{cfg.smtp_username}</strong></div></div> : <p className="text-sm text-amber-700 mt-1">Edite o arquivo .env</p>}</div></div></div><div className="rounded-xl bg-white border p-5"><h3 className="font-semibold mb-3">Provedores</h3><div className="grid grid-cols-2 md:grid-cols-4 gap-2">{Object.entries(pre).map(([k, x]) => <button key={k} onClick={() => selP(k)} className={`p-2 rounded border-2 text-sm ${sel === k ? "border-indigo-500 bg-indigo-50" : "border-slate-200"}`}>{x.name}</button>)}</div></div><div className="rounded-xl bg-white border p-5"><h3 className="font-semibold mb-3">Testar Conexao</h3><div className="grid grid-cols-2 gap-3"><input placeholder="Host" value={h} onChange={e => setH(e.target.value)} className="border rounded px-3 py-2" /><input type="number" placeholder="Porta" value={p} onChange={e => setP(Number(e.target.value))} className="border rounded px-3 py-2" /><input placeholder="Usuario" value={u} onChange={e => setU(e.target.value)} className="border rounded px-3 py-2" /><input type="password" placeholder="Senha" value={pw} onChange={e => setPw(e.target.value)} className="border rounded px-3 py-2" /></div><div className="mt-3"><label className="flex items-center gap-2"><input type="checkbox" checked={tls} onChange={e => setTls(e.target.checked)} /><span>Usar TLS</span></label></div><button onClick={tCon} disabled={tt} className="mt-3 bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50">{tt ? "Testando..." : "Testar Conexao"}</button></div><div className="rounded-xl bg-white border p-5"><h3 className="font-semibold mb-3">Enviar Email de Teste</h3><div className="flex gap-2"><input type="email" placeholder="seu@email.com" value={te} onChange={e => setTe(e.target.value)} className="flex-1 border rounded px-3 py-2" /><button onClick={tSend} disabled={et || !cfg?.configurado} className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-50 whitespace-nowrap">{et ? "Enviando..." : "Enviar Teste"}</button></div></div>{fb && <div className={`p-4 rounded ${fb.t === "s" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>{fb.m}</div>}</div>);
}