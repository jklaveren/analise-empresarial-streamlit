"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";

const NAV_LINKS = [
  { href: "/dashboard", label: "Empresas", icon: "📊" },
  { href: "/dashboard/crm", label: "CRM", icon: "🗂️" },
  { href: "/dashboard/campanhas", label: "Campanhas", icon: "📧" },
  { href: "/dashboard/templates", label: "Templates", icon: "📝" },
  { href: "/dashboard/notificacoes", label: "Notificações", icon: "🔔" },
  { href: "/dashboard/configuracoes/email", label: "Configurações", icon: "⚙️" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { username, isLoading, logout } = useRequireAuth();
  const router = useRouter();
  const pathname = usePathname();

  if (isLoading) {
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
    <div className="min-h-screen bg-slate-50 flex">
      <aside className="w-56 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-4 border-b border-slate-200">
          <Link href="/dashboard" className="text-lg font-bold text-slate-800 flex items-center gap-2">
            🛡️ WhoDados
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV_LINKS.map(link => {
            const active = pathname === link.href || (link.href !== "/dashboard" && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                <span>{link.icon}</span>
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-slate-200">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">@{username}</span>
            <button onClick={() => { logout(); router.push("/login"); }} className="text-xs text-slate-400 hover:text-red-500 transition-colors">
              Sair
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col">
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
