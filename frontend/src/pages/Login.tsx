import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { HOME, useAuth } from "../lib/auth";

const DEMO = [["Quản lý", "quanly@demo.vn"], ["Phục vụ", "phucvu@demo.vn"], ["Bếp", "bep@demo.vn"], ["Khách", "khach@demo.vn"]];

export default function Login() {
  const { user, login, register } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const next = sp.get("next");
  const [mode, setMode] = useState<"in" | "up">(sp.get("dang-ky") ? "up" : "in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={user.role === "customer" && next ? next : HOME[user.role]} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const u = mode === "in" ? await login(email.trim(), password) : await register(name.trim(), email.trim(), password);
      nav(u.role === "customer" && next ? next : HOME[u.role], { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <section className="login-art" aria-hidden="true">
        <Link to="/" className="login-mark">Quán Nhà Mình</Link>
        <div className="slip">
          <div className="slip-head"><span>Bàn A03</span><span>19:00</span></div>
          <p className="slip-sub">4 khách · Tầng 1</p>
          <ul>
            <li><span>Gỏi cuốn tôm thịt</span><i /><b>2</b></li>
            <li><span>Bún chả Hà Nội</span><i /><b>3</b></li>
            <li><span>Cà phê sữa đá</span><i /><b>4</b></li>
          </ul>
          <span className="slip-note">Khách dị ứng đậu phộng</span>
        </div>
        <p className="login-line">Đặt bàn trước, gọi món tại bàn, bếp nhận phiếu ngay.</p>
      </section>
      <section className="login-form">
        <Link to="/" className="btn-quiet back">← Về trang chủ</Link>
        <h1>{mode === "in" ? "Đăng nhập" : "Tạo tài khoản"}</h1>
        {next && <p className="muted" style={{ marginBottom: 14 }}>Bạn cần đăng nhập để đặt bàn và xem bàn còn trống.</p>}
        <form onSubmit={submit}>
          {mode === "up" && <label className="field"><span>Họ tên</span><input autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} required /></label>}
          <label className="field"><span>Email</span><input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
          <label className="field"><span>Mật khẩu</span><input type="password" autoComplete={mode === "in" ? "current-password" : "new-password"} minLength={mode === "up" ? 8 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} required />{mode === "up" && <small className="muted">Tối thiểu 8 ký tự</small>}</label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn" type="submit" disabled={busy}>{busy ? "Đang xử lý" : mode === "in" ? "Đăng nhập" : "Tạo tài khoản"}</button>
        </form>
        <p className="switch-mode muted">
          {mode === "in" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
          <button className="btn-quiet" type="button" onClick={() => { setMode(mode === "in" ? "up" : "in"); setError(""); }}>{mode === "in" ? "Đăng ký" : "Đăng nhập"}</button>
        </p>
        {import.meta.env.DEV && (
          <div className="demo">
            <p className="muted">Tài khoản mẫu (mật khẩu demo1234). Bấm để điền sẵn.</p>
            <div className="demo-row">
              {DEMO.map(([l, e]) => (
                <button key={e} type="button" className="chip" onClick={() => { setMode("in"); setEmail(e); setPassword("demo1234"); }}>{l}</button>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
