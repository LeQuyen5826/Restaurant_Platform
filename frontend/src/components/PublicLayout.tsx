import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { api, type PublicHome } from "../lib/api";
import { HOME, useAuth } from "../lib/auth";

const LINKS = [
  { to: "/", label: "Trang chủ", end: true },
  { to: "/mon-an", label: "Món ăn" },
  { to: "/dich-vu", label: "Dịch vụ" },
  { to: "/lien-he", label: "Liên hệ" },
];

export function useHome() {
  const [h, setH] = useState<PublicHome | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<PublicHome>("/public/home").then(setH).catch((e) => setErr(e.message)); }, []);
  return { home: h, err };
}

export function DishPhoto({ src, name, className = "" }: { src: string | null; name: string; className?: string }) {
  return src ? (
    <img className={`photo ${className}`} src={src} alt={name} loading="lazy" />
  ) : (
    <div className={`photo photo-ph ${className}`} aria-hidden="true"><span>{name.trim().charAt(0).toUpperCase()}</span></div>
  );
}

export default function PublicLayout({ children }: { children?: ReactNode }) {
  const { user, logout } = useAuth();
  const { home } = useHome();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [loc.pathname]);
  const r = home?.restaurant;
  return (
    <div className="site">
      <header className="site-top">
        <div className="site-bar">
          <Link to="/" className="site-brand">{r?.name ?? "Quán Nhà Mình"}</Link>
          <button className="site-burger btn-quiet" aria-expanded={open} aria-controls="site-nav" onClick={() => setOpen(!open)}>{open ? "Đóng" : "Menu"}</button>
          <nav id="site-nav" className={`site-nav ${open ? "open" : ""}`} aria-label="Điều hướng chính">
            {LINKS.map((l) => <NavLink key={l.to} to={l.to} end={l.end}>{l.label}</NavLink>)}
            <span className="site-auth">
              {!user && <Link to="/dang-nhap" className="btn-ghost-link">Đăng nhập</Link>}
              {user?.role === "customer" && (
                <>
                  <NavLink to="/lich-su">Lượt đặt của tôi</NavLink>
                  <button className="btn-quiet" onClick={logout}>Đăng xuất</button>
                </>
              )}
              {user && user.role !== "customer" && <Link to={HOME[user.role]}>Khu làm việc</Link>}
              {(!user || user.role === "customer") && <Link to="/dat-ban" className="btn site-cta">Đặt bàn</Link>}
            </span>
          </nav>
        </div>
      </header>
      <main>{children ?? <Outlet />}</main>
      <footer className="site-foot">
        <div className="site-foot-in">
          <div>
            <p className="site-brand">{r?.name ?? "Quán Nhà Mình"}</p>
            <p className="muted">{r?.address}</p>
            {r?.phone && <p className="muted">Điện thoại {r.phone}</p>}
          </div>
          <div className="site-foot-links">
            {LINKS.map((l) => <Link key={l.to} to={l.to}>{l.label}</Link>)}
          </div>
        </div>
      </footer>
    </div>
  );
}
