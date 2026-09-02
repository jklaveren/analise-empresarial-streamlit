"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "./api";

interface AuthState {
  username: string | null;
  isAdmin: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function decodeUsernameFromToken(token: string): { username: string | null; isAdmin: boolean } {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return { username: payload.sub ?? null, isAdmin: !!payload.is_admin };
  } catch {
    return { username: null, isAdmin: false };
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ username: null, isAdmin: false, isLoading: true });

  useEffect(() => {
    const token = api.getToken();
    if (token) {
      const { username, isAdmin } = decodeUsernameFromToken(token);
      setState({ username, isAdmin, isLoading: false });
    } else {
      setState(s => ({ ...s, isLoading: false }));
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.login(username, password);
    api.setToken(res.access_token);
    const { isAdmin } = decodeUsernameFromToken(res.access_token);
    setState({ username, isAdmin, isLoading: false });
  }, []);

  const logout = useCallback(() => {
    api.removeToken();
    setState({ username: null, isAdmin: false, isLoading: false });
  }, []);

  const value = useMemo(() => ({ ...state, login, logout }), [state, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de <AuthProvider>");
  return ctx;
}

export function useRequireAuth() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.isLoading && !auth.username) {
      router.replace("/login");
    }
  }, [auth.isLoading, auth.username, router]);

  return auth;
}
