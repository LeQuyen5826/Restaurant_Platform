import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

/* ---------- Toast ---------- */
const ToastCtx = createContext<(msg: string, kind?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [t, setT] = useState<{ msg: string; kind: "ok" | "err"; id: number } | null>(null);
  const show = useCallback((msg: string, kind: "ok" | "err" = "ok") => setT({ msg, kind, id: Date.now() }), []);
  useEffect(() => {
    if (!t) return;
    const h = setTimeout(() => setT(null), t.kind === "err" ? 6000 : 2800);
    return () => clearTimeout(h);
  }, [t]);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {t && <div key={t.id} className={`toast toast-${t.kind}`} role="status">{t.msg}</div>}
    </ToastCtx.Provider>
  );
}

/* ---------- Drawer ---------- */
export function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-label={title}>
        <header className="drawer-head">
          <h2>{title}</h2>
          <button className="btn-quiet" onClick={onClose} aria-label="Đóng">Đóng</button>
        </header>
        {children}
      </aside>
    </div>
  );
}

/* ---------- nhỏ ---------- */
export const Chili = ({ n }: { n: number }) =>
  n > 0 ? (
    <span className="chili" title={["", "Cay nhẹ", "Cay vừa", "Rất cay"][n]} aria-label={["", "Cay nhẹ", "Cay vừa", "Rất cay"][n]}>
      {Array.from({ length: n }, (_, i) => (
        <svg key={i} viewBox="0 0 14 16" width="13" height="15" aria-hidden="true">
          <path d="M10.5 1.5c.4-.7 1.5-.6 1.600.3 0 .6-.6.9-1.1 1 .8 5.500-3.9 10.7-10 11.2 3.5-1.800 5.8-5 6.1-8.6.1-1.5.9-3.2 2.300-3.7.5-.2.9-.1 1.1-.2Z" fill="currentColor" />
        </svg>
      ))}
    </span>
  ) : null;

export function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} className={`switch ${on ? "on" : ""}`} onClick={() => onChange(!on)}>
      <span />
    </button>
  );
}

export function Empty({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {hint && <p className="muted">{hint}</p>}
      {children}
    </div>
  );
}
