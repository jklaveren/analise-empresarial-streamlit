"use client";
import { useState, useEffect } from "react";
import { getSistemaStatus, SistemaStatus, getSlaConfig, updateSlaConfig, SlaConfig, trocarMinhaSenha, listarUsuarios, criarUsuarioAdmin, atualizarUsuarioAdmin, redefinirSenhaUsuarioAdmin, UsuarioAdmin, ApiError, listarOrganizacoesAdmin, getOrgEmailConfig, setOrgEmailConfig, uploadOrgLogo, definirEmpresasUsuario, Organizacao, OrgEmailConfig } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

function EmailTab() {
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
  return (<div className="space-y-6"><div className={`rounded-xl p-5 border-2 ${cfg?.configurado ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}`}><div className="flex items-center gap-3"><div>{cfg?.configurado ? "OK" : "!"}</div><div><h2 className={`font-semibold ${cfg?.configurado ? "text-green-800" : "text-amber-800"}`}>{cfg?.configurado ? "SMTP Configurado" : "SMTP Nao Configurado"}</h2>{cfg?.configurado ? <div className="text-sm text-green-700 mt-1"><div>Servidor: <strong>{cfg.smtp_host}:{cfg.smtp_port}</strong></div><div>Usuario: <strong>{cfg.smtp_username}</strong></div></div> : <p className="text-sm text-amber-700 mt-1">Edite o arquivo .env</p>}</div></div></div><div className="rounded-xl bg-white border p-5"><h3 className="font-semibold mb-3">Provedores</h3><div className="grid grid-cols-2 md:grid-cols-4 gap-2">{Object.entries(pre).map(([k, x]) => <button key={k} onClick={() => selP(k)} className={`p-2 rounded border-2 text-sm ${sel === k ? "border-indigo-500 bg-indigo-50" : "border-slate-200"}`}>{x.name}</button>)}</div></div><div className="rounded-xl bg-white border p-5"><h3 className="font-semibold mb-3">Testar Conexao</h3><div className="grid grid-cols-2 gap-3"><input placeholder="Host" value={h} onChange={e => setH(e.target.value)} className="border rounded px-3 py-2" /><input type="number" placeholder="Porta" value={p} onChange={e => setP(Number(e.target.value))} className="border rounded px-3 py-2" /><input placeholder="Usuario" value={u} onChange={e => setU(e.target.value)} className="border rounded px-3 py-2" /><input type="password" placeholder="Senha" value={pw} onChange={e => setPw(e.target.value)} className="border rounded px-3 py-2" /></div><div className="mt-3"><label className="flex items-center gap-2"><input type="checkbox" checked={tls} onChange={e => setTls(e.target.checked)} /><span>Usar TLS</span></label></div><button onClick={tCon} disabled={tt} className="mt-3 bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50">{tt ? "Testando..." : "Testar Conexao"}</button></div><div className="rounded-xl bg-white border p-5"><h3 className="font-semibold mb-3">Enviar Email de Teste</h3><div className="flex gap-2"><input type="email" placeholder="seu@email.com" value={te} onChange={e => setTe(e.target.value)} className="flex-1 border rounded px-3 py-2" /><button onClick={tSend} disabled={et || !cfg?.configurado} className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-50 whitespace-nowrap">{et ? "Enviando..." : "Enviar Teste"}</button></div></div>{fb && <div className={`p-4 rounded ${fb.t === "s" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>{fb.m}</div>}</div>);
}

function formatarData(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function SobreTab() {
  const [status, setStatus] = useState<SistemaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const s = await getSistemaStatus();
        setStatus(s);
      } catch {
        setErro("Nao foi possivel carregar as informacoes do sistema.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="p-8 text-slate-500">Carregando...</div>;

  if (erro) {
    return <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{erro}</div>;
  }

  if (!status || !status.pipeline_ja_rodou) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
        <h2 className="font-semibold text-amber-800">Pipeline ainda nao rodou</h2>
        <p className="text-sm text-amber-700 mt-1">
          Assim que o ETL (Receita Federal / PGFN) rodar pela primeira vez e sincronizar com o banco,
          as informacoes de atualizacao aparecem aqui.
        </p>
      </div>
    );
  }

  const cards = [
    { label: "Mes de referencia (Receita Federal)", valor: status.mes_referencia_rf || "—" },
    { label: "Trimestre de referencia (PGFN)", valor: status.trimestre_pgfn || "—" },
    { label: "Ultima extracao do pipeline", valor: formatarData(status.gerado_em) },
    { label: "Ultima sincronizacao com o banco", valor: formatarData(status.ultima_sincronizacao) },
    { label: "Matrizes ativas extraidas", valor: status.total_matrizes || "—" },
    { label: "Empresas sincronizadas no banco", valor: status.total_empresas_sincronizadas || "—" },
    { label: "Socios sincronizados no banco", valor: status.total_socios_sincronizados || "—" },
  ];

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-white border border-slate-200 divide-y divide-slate-100">
        {cards.map((c) => (
          <div key={c.label} className="flex items-center justify-between px-5 py-3">
            <span className="text-sm text-slate-500">{c.label}</span>
            <span className="text-sm font-medium text-slate-800">{c.valor}</span>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-400">
        Os dados sao atualizados automaticamente pelo pipeline (GitHub Actions), toda segunda-feira,
        ou manualmente pela aba &quot;Actions&quot; do repositorio.
      </p>
    </div>
  );
}

function PerfilTab() {
  const { username } = useAuth();
  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmSenha, setConfirmSenha] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [fb, setFb] = useState<{ t: "s" | "e"; m: string } | null>(null);

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    setFb(null);
    if (novaSenha.length < 8) {
      setFb({ t: "e", m: "A nova senha precisa ter ao menos 8 caracteres." });
      return;
    }
    if (novaSenha !== confirmSenha) {
      setFb({ t: "e", m: "As senhas nao coincidem." });
      return;
    }
    setSalvando(true);
    try {
      const r = await trocarMinhaSenha(senhaAtual, novaSenha);
      setFb({ t: "s", m: r.message || "Senha atualizada com sucesso." });
      setSenhaAtual("");
      setNovaSenha("");
      setConfirmSenha("");
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao atualizar a senha." });
    } finally {
      setSalvando(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl bg-white border p-5">
        <h3 className="font-semibold mb-1">Conta</h3>
        <p className="text-sm text-slate-500">Usuario logado: <strong>{username}</strong></p>
      </div>
      <form onSubmit={salvar} className="rounded-xl bg-white border p-5 space-y-3">
        <h3 className="font-semibold mb-1">Trocar senha</h3>
        <input type="password" placeholder="Senha atual" value={senhaAtual} onChange={e => setSenhaAtual(e.target.value)} required className="w-full border rounded px-3 py-2" />
        <input type="password" placeholder="Nova senha (min. 8 caracteres)" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} required className="w-full border rounded px-3 py-2" />
        <input type="password" placeholder="Confirmar nova senha" value={confirmSenha} onChange={e => setConfirmSenha(e.target.value)} required className="w-full border rounded px-3 py-2" />
        {fb && <div className={`p-3 rounded text-sm ${fb.t === "s" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>{fb.m}</div>}
        <button type="submit" disabled={salvando} className="bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50">{salvando ? "Salvando..." : "Salvar nova senha"}</button>
      </form>
    </div>
  );
}

function RegrasTab() {
  const { isAdmin } = useAuth();
  const [cfg, setCfg] = useState<SlaConfig | null>(null);
  const [verde, setVerde] = useState(2);
  const [amarelo, setAmarelo] = useState(5);
  const [loading, setLoading] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [fb, setFb] = useState<{ t: "s" | "e"; m: string } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const c = await getSlaConfig();
        setCfg(c);
        setVerde(c.sla_verde_dias);
        setAmarelo(c.sla_amarelo_dias);
      } catch { }
      setLoading(false);
    })();
  }, []);

  const salvar = async () => {
    setFb(null);
    setSalvando(true);
    try {
      const c = await updateSlaConfig({ sla_verde_dias: verde, sla_amarelo_dias: amarelo });
      setCfg(c);
      setFb({ t: "s", m: "Regras atualizadas com sucesso." });
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao salvar." });
    } finally {
      setSalvando(false);
    }
  };

  if (loading) return <div className="p-8 text-slate-500">Carregando...</div>;

  return (
    <div className="space-y-6">
      <div className="rounded-xl bg-white border p-5 space-y-3">
        <h3 className="font-semibold">Semaforo do Monitor de E-mails</h3>
        <p className="text-sm text-slate-500">
          Define quantos dias sem resposta um e-mail pode esperar antes de virar amarelo ou vermelho no Monitor/CRM.
        </p>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          <label className="text-sm text-slate-600">
            🟢 Verde (dias)
            <input type="number" min={1} value={verde} onChange={e => setVerde(Number(e.target.value))} disabled={!isAdmin} className="mt-1 w-full border rounded px-3 py-2 disabled:bg-slate-50" />
          </label>
          <label className="text-sm text-slate-600">
            🟡 Amarelo até (dias)
            <input type="number" min={1} value={amarelo} onChange={e => setAmarelo(Number(e.target.value))} disabled={!isAdmin} className="mt-1 w-full border rounded px-3 py-2 disabled:bg-slate-50" />
          </label>
        </div>
        <p className="text-xs text-slate-400">Acima de {amarelo} dias sem resposta, o status fica vermelho.</p>
        {fb && <div className={`p-3 rounded text-sm ${fb.t === "s" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>{fb.m}</div>}
        {isAdmin ? (
          <button onClick={salvar} disabled={salvando} className="bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50">{salvando ? "Salvando..." : "Salvar regras"}</button>
        ) : (
          <p className="text-xs text-slate-400">Somente administradores podem alterar estes valores.</p>
        )}
      </div>
    </div>
  );
}

function UsuariosTab() {
  const { username: meuUsername } = useAuth();
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [orgs, setOrgs] = useState<Organizacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [fb, setFb] = useState<{ t: "s" | "e"; m: string } | null>(null);
  const [mostrarNovo, setMostrarNovo] = useState(false);
  const [novoUser, setNovoUser] = useState("");
  const [novoEmail, setNovoEmail] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [novoAdmin, setNovoAdmin] = useState(false);
  const [novoOrgs, setNovoOrgs] = useState<number[]>([]);
  const [criando, setCriando] = useState(false);

  const carregar = async () => {
    try {
      const [us, os] = await Promise.all([listarUsuarios(), listarOrganizacoesAdmin()]);
      setUsuarios(us);
      setOrgs(os);
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao carregar usuarios." });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { carregar(); }, []);

  const toggleOrgUsuario = async (u: UsuarioAdmin, orgId: number) => {
    setFb(null);
    const atual = u.organizacao_ids || [];
    const novos = atual.includes(orgId) ? atual.filter(id => id !== orgId) : [...atual, orgId];
    try {
      await definirEmpresasUsuario(u.id, novos);
      await carregar();
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao definir empresas." });
    }
  };

  const toggle = async (u: UsuarioAdmin, campo: "is_admin" | "is_active") => {
    setFb(null);
    try {
      await atualizarUsuarioAdmin(u.id, { [campo]: !u[campo] });
      await carregar();
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao atualizar usuario." });
    }
  };

  const resetarSenha = async (u: UsuarioAdmin) => {
    const nova = window.prompt(`Nova senha para ${u.username} (min. 8 caracteres):`);
    if (!nova) return;
    try {
      const r = await redefinirSenhaUsuarioAdmin(u.id, nova);
      setFb({ t: "s", m: r.message || "Senha redefinida." });
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao redefinir senha." });
    }
  };

  const criar = async (e: React.FormEvent) => {
    e.preventDefault();
    setFb(null);
    setCriando(true);
    try {
      await criarUsuarioAdmin({ username: novoUser, password: novaSenha, email: novoEmail || undefined, is_admin: novoAdmin, organizacao_ids: novoOrgs });
      setFb({ t: "s", m: `Usuario '${novoUser}' criado.` });
      setNovoUser(""); setNovoEmail(""); setNovaSenha(""); setNovoAdmin(false); setNovoOrgs([]); setMostrarNovo(false);
      await carregar();
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao criar usuario." });
    } finally {
      setCriando(false);
    }
  };

  if (loading) return <div className="p-8 text-slate-500">Carregando...</div>;

  return (
    <div className="space-y-4">
      {fb && <div className={`p-3 rounded text-sm ${fb.t === "s" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>{fb.m}</div>}

      <div className="rounded-xl bg-white border divide-y divide-slate-100">
        {usuarios.map(u => (
          <div key={u.id} className="flex items-center justify-between px-5 py-3 gap-3 flex-wrap">
            <div>
              <div className="font-medium text-slate-800">{u.username} {u.username === meuUsername && <span className="text-xs text-slate-400">(você)</span>}</div>
              <div className="text-xs text-slate-500">{u.email || "sem e-mail"}</div>
            </div>
            <div className="flex items-center gap-3 text-sm flex-wrap">
              {orgs.length > 0 && (
                <div className="flex items-center gap-2 border-r border-slate-200 pr-3">
                  <span className="text-xs text-slate-400">Empresas:</span>
                  {orgs.map(o => (
                    <label key={o.id} className="flex items-center gap-1 text-slate-600">
                      <input type="checkbox" checked={(u.organizacao_ids || []).includes(o.id)} onChange={() => toggleOrgUsuario(u, o.id)} />
                      {o.nome}
                    </label>
                  ))}
                </div>
              )}
              <label className="flex items-center gap-1 text-slate-600">
                <input type="checkbox" checked={u.is_admin} onChange={() => toggle(u, "is_admin")} />
                Admin
              </label>
              <label className="flex items-center gap-1 text-slate-600">
                <input type="checkbox" checked={u.is_active} onChange={() => toggle(u, "is_active")} />
                Ativo
              </label>
              <button onClick={() => resetarSenha(u)} className="text-indigo-600 hover:underline text-xs">Redefinir senha</button>
            </div>
          </div>
        ))}
      </div>

      {mostrarNovo ? (
        <form onSubmit={criar} className="rounded-xl bg-white border p-5 space-y-3">
          <h3 className="font-semibold">Novo usuario</h3>
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Usuario" value={novoUser} onChange={e => setNovoUser(e.target.value)} required className="border rounded px-3 py-2" />
            <input type="email" placeholder="E-mail (opcional)" value={novoEmail} onChange={e => setNovoEmail(e.target.value)} className="border rounded px-3 py-2" />
            <input type="password" placeholder="Senha (min. 8 caracteres)" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} required className="border rounded px-3 py-2" />
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={novoAdmin} onChange={e => setNovoAdmin(e.target.checked)} />
              Administrador
            </label>
          </div>
          {orgs.length > 0 && (
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm text-slate-500">Empresas que pode acessar:</span>
              {orgs.map(o => (
                <label key={o.id} className="flex items-center gap-1 text-sm text-slate-600">
                  <input type="checkbox" checked={novoOrgs.includes(o.id)} onChange={e => setNovoOrgs(v => e.target.checked ? [...v, o.id] : v.filter(id => id !== o.id))} />
                  {o.nome}
                </label>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <button type="submit" disabled={criando} className="bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50">{criando ? "Criando..." : "Criar usuario"}</button>
            <button type="button" onClick={() => setMostrarNovo(false)} className="px-4 py-2 rounded text-slate-600 hover:bg-slate-100">Cancelar</button>
          </div>
        </form>
      ) : (
        <button onClick={() => setMostrarNovo(true)} className="bg-indigo-600 text-white px-4 py-2 rounded">+ Novo usuario</button>
      )}
    </div>
  );
}

function EmpresasTab() {
  const [orgs, setOrgs] = useState<Organizacao[]>([]);
  const [orgId, setOrgId] = useState<number | null>(null);
  const [cfg, setCfg] = useState<OrgEmailConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [fb, setFb] = useState<{ t: "s" | "e"; m: string } | null>(null);
  const [logoV, setLogoV] = useState(0); // cache-buster do preview do logo

  // Form
  const [emailFrom, setEmailFrom] = useState("");
  const [emailFromName, setEmailFromName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState(587);
  const [user, setUser] = useState("");
  const [pw, setPw] = useState("");
  const [tls, setTls] = useState(true);
  const [assinatura, setAssinatura] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const os = await listarOrganizacoesAdmin();
        setOrgs(os);
        if (os[0]) setOrgId(os[0].id);
      } catch (err) {
        setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao carregar empresas." });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (orgId == null) return;
    (async () => {
      setFb(null);
      try {
        const c = await getOrgEmailConfig(orgId);
        setCfg(c);
        setEmailFrom(c.email_from || "");
        setEmailFromName(c.email_from_name || "");
        setHost(c.smtp_host || "");
        setPort(c.smtp_port || 587);
        setUser(c.smtp_username || "");
        setPw("");
        setTls(c.smtp_use_tls ?? true);
        setAssinatura(c.assinatura_html || "");
        setLogoV(v => v + 1);
      } catch (err) {
        setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao carregar config." });
      }
    })();
  }, [orgId]);

  const salvar = async () => {
    if (orgId == null) return;
    setFb(null);
    setSalvando(true);
    try {
      const c = await setOrgEmailConfig(orgId, {
        email_from: emailFrom, email_from_name: emailFromName,
        smtp_host: host, smtp_port: port, smtp_username: user,
        smtp_use_tls: tls, assinatura_html: assinatura,
        ...(pw ? { smtp_password: pw } : {}),
      });
      setCfg(c);
      setPw("");
      setFb({ t: "s", m: "Configuração da empresa salva." });
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao salvar." });
    } finally {
      setSalvando(false);
    }
  };

  const enviarLogo = async (file: File | null) => {
    if (!file || orgId == null) return;
    setFb(null);
    try {
      await uploadOrgLogo(orgId, file);
      setLogoV(v => v + 1);
      setCfg(c => c ? { ...c, tem_logo: true } : c);
      setFb({ t: "s", m: "Logo atualizado." });
    } catch (err) {
      setFb({ t: "e", m: err instanceof ApiError ? err.message : "Erro ao enviar logo." });
    }
  };

  if (loading) return <div className="p-8 text-slate-500">Carregando...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-slate-600">Empresa:</span>
        <select value={orgId ?? ""} onChange={e => setOrgId(Number(e.target.value))} className="border rounded px-3 py-2 text-sm font-semibold">
          {orgs.map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
        </select>
        {cfg && <span className={`text-xs px-2 py-1 rounded ${cfg.configurado ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{cfg.configurado ? "SMTP configurado" : "SMTP não configurado"}</span>}
      </div>

      <div className="rounded-xl bg-white border p-5 space-y-3">
        <h3 className="font-semibold">Remetente</h3>
        <div className="grid grid-cols-2 gap-3">
          <input placeholder="Nome do remetente (ex: NRA Consultoria)" value={emailFromName} onChange={e => setEmailFromName(e.target.value)} className="border rounded px-3 py-2" />
          <input type="email" placeholder="E-mail do remetente" value={emailFrom} onChange={e => setEmailFrom(e.target.value)} className="border rounded px-3 py-2" />
        </div>
      </div>

      <div className="rounded-xl bg-white border p-5 space-y-3">
        <h3 className="font-semibold">Servidor SMTP</h3>
        <div className="grid grid-cols-2 gap-3">
          <input placeholder="Host (ex: smtp.gmail.com)" value={host} onChange={e => setHost(e.target.value)} className="border rounded px-3 py-2" />
          <input type="number" placeholder="Porta" value={port} onChange={e => setPort(Number(e.target.value))} className="border rounded px-3 py-2" />
          <input placeholder="Usuário SMTP" value={user} onChange={e => setUser(e.target.value)} className="border rounded px-3 py-2" />
          <input type="password" placeholder="Senha (deixe em branco p/ manter)" value={pw} onChange={e => setPw(e.target.value)} className="border rounded px-3 py-2" />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={tls} onChange={e => setTls(e.target.checked)} /> Usar TLS</label>
      </div>

      <div className="rounded-xl bg-white border p-5 space-y-3">
        <h3 className="font-semibold">Assinatura de e-mail</h3>
        <p className="text-xs text-slate-500">HTML livre. Use <code>{"{{logo}}"}</code> onde quiser o logo da empresa. Ex: <code>{'<img src="{{logo}}" height="48"> NRA Consultoria — (51) 9999-9999'}</code></p>
        <textarea value={assinatura} onChange={e => setAssinatura(e.target.value)} rows={5} className="w-full border rounded px-3 py-2 font-mono text-sm" placeholder="<img src='{{logo}}' height='48'><br>Sua assinatura aqui" />
      </div>

      <div className="rounded-xl bg-white border p-5 space-y-3">
        <h3 className="font-semibold">Logo</h3>
        <div className="flex items-center gap-4">
          {orgId != null && cfg?.tem_logo && (
            <img src={`${API_BASE}/api/v1/organizacoes/${orgId}/logo?v=${logoV}`} alt="Logo" className="h-14 border rounded bg-slate-50 p-1" />
          )}
          <input type="file" accept="image/*" onChange={e => enviarLogo(e.target.files?.[0] ?? null)} className="text-sm" />
        </div>
      </div>

      {fb && <div className={`p-3 rounded text-sm ${fb.t === "s" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>{fb.m}</div>}
      <button onClick={salvar} disabled={salvando} className="bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50">{salvando ? "Salvando..." : "Salvar configuração"}</button>
    </div>
  );
}

type Aba = "perfil" | "regras" | "usuarios" | "empresas" | "email" | "sobre";

export default function ConfiguracoesPage() {
  const { isAdmin } = useAuth();
  const [aba, setAba] = useState<Aba>("perfil");

  const abas: { id: Aba; label: string; icone: string; somenteAdmin?: boolean }[] = [
    { id: "perfil", label: "Perfil", icone: "👤" },
    { id: "regras", label: "Regras do CRM/Monitor", icone: "🎯" },
    { id: "usuarios", label: "Usuários", icone: "👥", somenteAdmin: true },
    { id: "empresas", label: "Empresas", icone: "🏢", somenteAdmin: true },
    { id: "email", label: "Email (global)", icone: "✉️", somenteAdmin: true },
    { id: "sobre", label: "Sobre", icone: "ℹ️" },
  ];

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Configurações</h1>
        <p className="text-sm text-slate-500">Sua conta, regras do sistema, usuários e status dos dados.</p>
      </div>

      <div className="mb-6 flex gap-1 border-b border-slate-200 overflow-x-auto">
        {abas.filter(a => !a.somenteAdmin || isAdmin).map(a => (
          <button
            key={a.id}
            onClick={() => setAba(a.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              aba === a.id ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {a.icone} {a.label}
          </button>
        ))}
      </div>

      {aba === "perfil" && <PerfilTab />}
      {aba === "regras" && <RegrasTab />}
      {aba === "usuarios" && isAdmin && <UsuariosTab />}
      {aba === "empresas" && isAdmin && <EmpresasTab />}
      {aba === "email" && isAdmin && <EmailTab />}
      {aba === "sobre" && <SobreTab />}
    </div>
  );
}
