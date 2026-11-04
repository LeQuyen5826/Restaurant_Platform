import { useCallback, useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { usePoll } from "../hooks/usePoll";
import { api, type Role, type Settings } from "../lib/api";
import { ROLE_LABEL, useAuth } from "../lib/auth";

const NAV: Partial<Record<Role, { to: string; label: string; badge?: "ready"; end?: boolean }[]>> = {
  manager: [
    { to: "/quan-ly/tong-quan", label: "Tổng quan" },
    { to: "/quan-ly/dat-ban", label: "Đặt bàn" },
    { to: "/quan-ly/thuc-don", label: "Thực đơn" },
    { to: "/quan-ly/ban", label: "Bàn" },
    { to: "/quan-ly/nhan-su", label: "Nhân sự" },
    { to: "/quan-ly/cai-dat", label: "Cài đặt" },
  ],
  waiter: [
    { to: "/phuc-vu", label: "Sơ đồ bàn", end: true },
    { to: "/phuc-vu/check-in", label: "Check-in" },
    { to: "/phuc-vu/vang-lai", label: "Khách vãng lai" },
    { to: "/phuc-vu/mon-cho", label: "Món chờ ra", badge: "ready" },
    { to: "/phuc-vu/dat-ban", label: "Đặt bàn" },
  ],
  kitchen: [
    { to: "/bep", label: "Phiếu bếp", end: true },
    { to: "/bep/het-mon", label: "Còn / hết món" },
  ],
};

export default function Shell({ role, children }: { role: Role; children: ReactNode }) {
  const { user, logout } = useAuth();
  const [name, setName] = useState("");
  const [ready, setReady] = useState(0);
  useEffect(() => { api<Settings>("/restaurant/settings").then((s) => setName(s.name)).catch(() => {}); }, []);
  const countReady = useCallback(async () => { if (role === "waiter") setReady((await api<unknown[]>("/floor/ready")).length); }, [role]);
  usePoll(() => countReady().catch(() => {}), 4000);
  return (
    <div className="shell">
      <nav className="rail" aria-label="Điều hướng chính">
        <div className="rail-brand">
          <span className="rail-name">{name || "Nhà hàng"}</span>
          <span className="rail-role">{ROLE_LABEL[role]}</span>
        </div>
        <ul className="rail-nav">
          {(NAV[role] ?? []).map((n) => (
            <li key={n.to}>
              <NavLink to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
                {n.label}{n.badge === "ready" && ready > 0 && <span className="nav-badge" aria-label={`${ready} món chờ`}>{ready}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="rail-foot">
          <span className="rail-user">{user?.full_name}</span>
          <button className="btn-rail" onClick={logout}>Đăng xuất</button>
        </div>
      </nav>
      <main className="stage">{children}</main>
    </div>
  );
}
