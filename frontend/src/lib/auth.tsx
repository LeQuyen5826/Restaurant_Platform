import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken, type Role, type User } from "./api";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (full_name: string, email: string, password: string) => Promise<User>;
  logout: () => void;
}
const Ctx = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(Ctx);

export const HOME: Record<Role, string> = {
  customer: "/",
  manager: "/quan-ly/tong-quan",
  waiter: "/phuc-vu",
  kitchen: "/bep",
};
export const ROLE_LABEL: Record<Role, string> = {
  customer: "Khách", manager: "Quản lý", waiter: "Phục vụ", kitchen: "Bếp",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const r = await api<{ token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(r.token);
    setUser(r.user);
    return r.user;
  };
  const register = async (full_name: string, email: string, password: string) => {
    const r = await api<{ token: string; user: User }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ full_name, email, password }),
    });
    setToken(r.token);
    setUser(r.user);
    return r.user;
  };
  const logout = () => {
    setToken(null);
    setUser(null);
  };
  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>;
}
