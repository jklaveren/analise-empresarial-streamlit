"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import OrgSwitcher from "@/components/OrgSwitcher";

const NAV_LINKS = [
  { href: "/dashboard", label: "Empresas", icon: "📊" },
  { href: "/dashboard/socios", label: "Sócios", icon: "🧑‍🤝‍🧑" },
  { href: "/dashboard/crm", label: "Clientes", icon: "🗂️" },
  { href: "/dashboard/atividades", label: "Atividades", icon: "✅" },
  { href: "/dashboard/campanhas", label: "Campanhas", icon: "📧" },
  { href: "/dashboard/whatsapp", label: "WhatsApp", icon: "💬" },
  { href: "/dashboard/templates", label: "Templates", icon: "📝" },
  { href: "/dashboard/notificacoes", label: "Notificações", icon: "🔔" },
  { href: "/dashboard/configuracoes", label: "Configurações", icon: "⚙️" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { username, isLoading, logout, activeOrg } = useRequireAuth();
  const router = useRouter();
  const pathname = usePathname();
  const isVisitante = activeOrg?.papel === "visitante";
  const navLinks = isVisitante ? NAV_LINKS.filter(l => l.href === "/dashboard") : NAV_LINKS;

  // !username inclui o instante entre "terminou de carregar" e o
  // redirect pro /login efetivamente acontecer (useRequireAuth so'
  // dispara o router.replace num efeito, que roda DEPOIS do render) --
  // sem isso, esse instante renderizava o dashboard inteiro (menu,
  // cabecalho) por um frame antes de sair da tela.
  if (isLoading || !username) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">🛡️</div>
          <p className="text-slate-500">Carregando...</p>
        </div>
      </div>
    );
  }

  return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 flex">
      <aside className="w-64 bg-white/70 border-r border-slate-200/50 flex flex-col shadow-sm">
        <div className="p-5 border-b border-slate-200/50 bg-gradient-to-b from-indigo-500 to-purple-600 text-white">
          <Link href="/dashboard" className="text-xl font-bold flex items-center gap-3">
            <span className="text-2xl">🛡️</span>
            <span>WhoDados</span>
          </Link>
          <p className="text-sm text-indigo-100 mt-1">Análise Empresarial</p>
        </div>
        {isVisitante && (
          <div className="mx-3 mt-3 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700 font-medium">
            👁️ Modo visitante — dados de exemplo, sem acesso de edição
          </div>
        )}
        <nav className="flex-1 p-3 space-y-1">
          {navLinks.map(link => {
            const active = pathname === link.href || (link.href !== "/dashboard" && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  active 
                    ? "bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-md" 
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 hover:shadow-sm"
                }`}
              >
                <span className="text-lg">{link.icon}</span>
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-200/50 bg-white/50">
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-xs text-slate-500">Logado como:</span>
              <span className="text-sm font-medium text-slate-700">@{username}</span>
            </div>
            <button 
              onClick={() => { logout(); router.push("/login"); }} 
              className="text-xs text-slate-400 hover:text-red-500 transition-all duration-200 hover:scale-105"
            >
              🡒 Sair
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col">
        <header className="flex items-center justify-end gap-4 border-b border-slate-200/50 bg-white/50 px-6 py-3 backdrop-blur-sm">
          <OrgSwitcher />
        </header>
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
