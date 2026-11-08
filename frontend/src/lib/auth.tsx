import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiError, User } from "./api";

type AuthState = {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<User | null>;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, fullName: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User | null) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const u = await api<User>("/auth/me/");
      setUser(u);
      return u;
    } catch (e) {
      if ((e as ApiError).status !== 403 && (e as ApiError).status !== 401) console.warn(e);
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const login = async (email: string, password: string) => {
    const u = await api<User>("/auth/login/", { method: "POST", json: { email, password } });
    setUser(u);
    return u;
  };
  const register = async (email: string, password: string, full_name: string) => {
    const u = await api<User>("/auth/register/", { method: "POST", json: { email, password, full_name } });
    setUser(u);
    return u;
  };
  const logout = async () => {
    try { await api("/auth/logout/", { method: "POST" }); } finally { setUser(null); }
  };

  return (
    <AuthContext.Provider value={{ user, loading, refresh, login, register, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
