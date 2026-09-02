"use client";

import Link from "next/link";
import { useRequireAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { username, isLoading, logout } = useRequireAuth();
  const router = useRouter();

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
    <div className="min-h-screen bg-slate-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/dashboard" className="text-xl font-bold text-slate-800">
            🛡️ WhoDados
          </Link>
          <div className="flex gap-6 text-sm font-medium text-slate-600">
            <Link href="/dashboard" className="hover:text-indigo-600">Dashboard</Link>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-600">@{username}</span>
          <button
            onClick={() => { logout(); router.push("/login"); }}
            className="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            Sair
          </button>
        </div>
      </nav>

      {/* Content */}
      <main className="p-6">{children}</main>
    </div>
  );
}
