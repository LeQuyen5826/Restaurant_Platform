import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { DishPhoto } from "../../components/PublicLayout";
import { useToast } from "../../components/ui";
import { api, send, vnd, type PubMenu } from "../../lib/api";

interface State {
  table_code: string; me: string; my_name: string; guests: { id: string; name: string }[];
  cart: { id: string; guest_id: string; guest_name: string; dish_id: string; name: string; price_vnd: number; quantity: number; note: string | null }[];
  cart_total: number;
  items: { id: string; name: string; price_vnd: number; quantity: number; note: string | null; status: string; cancel_reason: string | null; guest_name: string | null }[];
  ordered_total: number;
}
const ST: Record<string, string> = { new: "Đã gửi bếp", preparing: "Đang làm", ready: "Sắp mang ra", served: "Đã phục vụ", cancelled: "Đã hủy" };
const tokKey = (k: string) => `guest:${k}`;
const gtok = (k: string) => { try { return sessionStorage.getItem(tokKey(k)); } catch { return null; } };

/** Gọi món tại bàn. mode="mine": khách đã đăng nhập và được check-in; mode="table": khách vãng lai quét QR trên bàn. */
export default function Dining({ mode }: { mode: "mine" | "table" }) {
  const { code = "" } = useParams();
  const key = mode === "mine" ? "mine" : code;
  const toast = useToast();
  const [token, setToken] = useState<string | null>(() => gtok(key));
  const [label, setLabel] = useState("");
  const [name, setName] = useState("");
  const [info, setInfo] = useState<{ code: string; area: string | null; session_open: boolean } | null>(null);
  const [fatal, setFatal] = useState("");
  const [st, setSt] = useState<State | null>(null);
  const [menu, setMenu] = useState<PubMenu | null>(null);
  const [tab, setTab] = useState<"menu" | "cart" | "ordered">("menu");
  const [cat, setCat] = useState("");
  const [busy, setBusy] = useState(false);
  const hdr = useMemo(() => ({ "X-Guest-Token": token ?? "" }), [token]);

  const save = (t: string) => { try { sessionStorage.setItem(tokKey(key), t); } catch { /* bỏ qua */ } setToken(t); };
  const drop = useCallback(() => { try { sessionStorage.removeItem(tokKey(key)); } catch { /* bỏ qua */ } setToken(null); setSt(null); }, [key]);

  // khách đăng nhập: tự vào bàn bằng tài khoản
  useEffect(() => {
    if (mode !== "mine" || token) return;
    api<{ token: string; table_label: string }>("/dining/mine/join", { method: "POST" })
      .then((r) => { setLabel(r.table_label); save(r.token); })
      .catch((e) => setFatal(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, token]);
  // khách vãng lai: xem thông tin bàn
  useEffect(() => {
    if (mode !== "table") return;
    api<{ code: string; area: string | null; session_open: boolean }>(`/dining/table/${code}`).then(setInfo).catch((e) => setFatal(e.message));
  }, [mode, code]);
  useEffect(() => { api<PubMenu>("/public/menu").then((m) => { setMenu(m); setCat(m.sections[0]?.name ?? ""); }).catch(() => {}); }, []);

  const load = useCallback(async () => {
    if (!token) return;
    try { setSt(await api<State>("/dining/state", { headers: hdr })); }
    catch (e) { const m = (e as Error).message; if (/đóng|hết hạn|không hợp lệ|Chưa vào/.test(m)) { drop(); setFatal("Bàn đã đóng hoặc phiên gọi món đã kết thúc. Cảm ơn bạn đã dùng bữa."); } }
  }, [token, hdr, drop]);
  useEffect(() => { load(); const h = setInterval(load, 3000); return () => clearInterval(h); }, [load]);

  const join = async () => {
    setBusy(true);
    try { const r = await send<{ token: string }>("POST", `/dining/table/${code}/join`, { name: name.trim() || null }); save(r.token); setFatal(""); }
    catch (e) { toast((e as Error).message, "err"); }
    setBusy(false);
  };
  const setQ = async (dish_id: string, quantity: number) => {
    try { await api("/dining/cart", { method: "PUT", headers: hdr, body: JSON.stringify({ dish_id, quantity: Math.max(0, quantity) }) }); load(); }
    catch (e) { toast((e as Error).message, "err"); }
  };
  const sendOrder = async () => {
    setBusy(true);
    try { const r = await api<{ items: number }>("/dining/orders", { method: "POST", headers: hdr }); toast(`Đã gửi ${r.items} món xuống bếp`); setTab("ordered"); load(); }
    catch (e) { toast((e as Error).message, "err"); }
    setBusy(false);
  };
  const cancelItem = async (id: string) => {
    try { await api(`/dining/items/${id}/cancel`, { method: "POST", headers: hdr }); toast("Đã hủy món"); load(); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  // ---------- trước khi vào bàn ----------
  if (!token) {
    return (
      <div className="wrap page narrow">
        <h1 className="page-title">{mode === "mine" ? "Chọn món" : info ? `Bàn ${info.code}` : "Gọi món tại bàn"}</h1>
        {fatal && <p className="form-error" role="alert">{fatal}</p>}
        {mode === "mine" && !fatal && <p className="muted">Đang vào bàn của bạn…</p>}
        {mode === "mine" && fatal && <Link to="/lich-su">Về lượt đặt của tôi</Link>}
        {mode === "table" && info && !fatal && (
          info.session_open ? (
            <div className="note-box">
              <p>{info.area ? `${info.area} · ` : ""}Nhập tên để cả bàn nhìn thấy ai gọi món nào (không bắt buộc).</p>
              <label className="field"><span>Tên của bạn</span><input value={name} maxLength={40} onChange={(e) => setName(e.target.value)} placeholder="Ví dụ: Lan" /></label>
              <button className="btn btn-lg" onClick={join} disabled={busy}>Vào chọn món</button>
            </div>
          ) : <p className="form-error">Bàn này chưa được mở. Vui lòng báo nhân viên phục vụ.</p>
        )}
      </div>
    );
  }
  if (!st || !menu) return <p className="loading">Đang tải…</p>;

  const qtyOf = (id: string) => st.cart.find((c) => c.dish_id === id && c.guest_id === st.me)?.quantity ?? 0;
  const cartCount = st.cart.reduce((s, c) => s + c.quantity, 0);
  const active = st.items.filter((i) => i.status !== "cancelled");
  const readyN = st.items.filter((i) => i.status === "ready").length;
  const section = menu.sections.find((s) => s.name === cat) ?? menu.sections[0];

  return (
    <div className="dine">
      <header className="dine-top">
        <div className="wrap dine-top-in">
          <div><p className="eyebrow">Bàn</p><h1 className="dine-table">{st.table_code || label}</h1></div>
          <p className="muted">Xin chào {st.my_name}. Cả bàn dùng chung một giỏ.</p>
        </div>
        <div className="wrap tabs" role="tablist">
          <button role="tab" aria-selected={tab === "menu"} className={tab === "menu" ? "on" : ""} onClick={() => setTab("menu")}>Chọn món</button>
          <button role="tab" aria-selected={tab === "cart"} className={tab === "cart" ? "on" : ""} onClick={() => setTab("cart")}>Giỏ chung{cartCount ? ` (${cartCount})` : ""}</button>
          <button role="tab" aria-selected={tab === "ordered"} className={tab === "ordered" ? "on" : ""} onClick={() => setTab("ordered")}>Đã gọi{readyN ? ` · ${readyN} sắp ra` : active.length ? ` (${active.length})` : ""}</button>
        </div>
      </header>

      <div className="wrap dine-body">
        {tab === "menu" && (
          <>
            <div className="catbar" role="tablist" aria-label="Danh mục">
              {menu.sections.map((s) => <button key={s.name} className={`chip ${cat === s.name ? "chip-on" : ""}`} onClick={() => setCat(s.name)}>{s.name}</button>)}
            </div>
            <ul className="pick">
              {section?.dishes.map((d) => (
                <li key={d.id} className={d.is_available ? "" : "soldout"}>
                  <DishPhoto src={d.image_url} name={d.name} className="pick-photo" />
                  <div className="pick-body">
                    <b>{d.name}</b>
                    <span className="muted">{d.is_available ? vnd(d.price_vnd) : "Hết món"}</span>
                    {d.allergens.length > 0 && <small className="muted">Chứa: {d.allergens.map((a) => a.name.replace(/ \(.*\)/, "")).join(", ")}</small>}
                  </div>
                  {d.is_available && (
                    <div className="stepper">
                      {qtyOf(d.id) > 0 && <><button className="step-btn" onClick={() => setQ(d.id, qtyOf(d.id) - 1)} aria-label={`Bớt ${d.name}`}>−</button><b>{qtyOf(d.id)}</b></>}
                      <button className="step-btn" onClick={() => setQ(d.id, qtyOf(d.id) + 1)} aria-label={`Thêm ${d.name}`}>+</button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}

        {tab === "cart" && (
          st.cart.length === 0 ? <p className="muted">Giỏ đang trống. Chọn món ở tab Chọn món.</p> : (
            <ul className="order-lines big">
              {st.cart.map((c) => (
                <li key={c.id}>
                  <span>{c.quantity} × {c.name}<small className="muted"> {c.guest_name}</small></span><i /><b>{vnd(c.price_vnd * c.quantity)}</b>
                  {c.guest_id === st.me && <button className="btn-quiet" onClick={() => setQ(c.dish_id, 0)} aria-label={`Bỏ ${c.name}`}>Bỏ</button>}
                </li>
              ))}
              <li className="total"><span>Tạm tính</span><i /><b>{vnd(st.cart_total)}</b></li>
            </ul>
          )
        )}

        {tab === "ordered" && (
          st.items.length === 0 ? <p className="muted">Chưa có món nào được gửi xuống bếp.</p> : (
            <>
              <ul className="ordered">
                {st.items.map((i) => (
                  <li key={i.id} className={`o-${i.status}`}>
                    <div><b>{i.quantity} × {i.name}</b>{i.note && <small className="muted"> · {i.note}</small>}{i.guest_name && <small className="muted"> · {i.guest_name}</small>}</div>
                    <span className={`badge badge-${i.status === "ready" ? "good" : i.status === "cancelled" ? "bad" : i.status === "served" ? "dim" : "warn"}`}>{ST[i.status]}</span>
                    {i.status === "cancelled" && i.cancel_reason && <small className="muted">{i.cancel_reason}</small>}
                    {i.status === "new" && <button className="btn-quiet" onClick={() => cancelItem(i.id)}>Hủy món</button>}
                  </li>
                ))}
              </ul>
              <p className="total-line">Tổng đã gọi <b>{vnd(st.ordered_total)}</b></p>
            </>
          )
        )}
      </div>

      {tab !== "ordered" && cartCount > 0 && (
        <div className="dine-bar"><div className="wrap dine-bar-in">
          <span><b>{cartCount} món</b> · {vnd(st.cart_total)}</span>
          <button className="btn btn-lg" disabled={busy} onClick={sendOrder}>Gửi xuống bếp</button>
        </div></div>
      )}
    </div>
  );
}
