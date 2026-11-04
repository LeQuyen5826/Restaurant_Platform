import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useToast } from "../../components/ui";
import { api, dmy, hm, RES_STATUS, send, vnd, type ResDetail } from "../../lib/api";

export const statusTone = (s: string) => (s === "confirmed" || s === "seated" ? "good" : s === "pending_deposit" ? "warn" : "dim");

function Countdown({ to }: { to: string }) {
  const [left, setLeft] = useState(() => new Date(to).getTime() - Date.now());
  useEffect(() => { const h = setInterval(() => setLeft(new Date(to).getTime() - Date.now()), 1000); return () => clearInterval(h); }, [to]);
  if (left <= 0) return <b>đã hết hạn</b>;
  const m = Math.floor(left / 60000), s = Math.floor((left % 60000) / 1000);
  return <b>{m}:{String(s).padStart(2, "0")}</b>;
}

export default function ReservationView() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const [r, setR] = useState<ResDetail | null>(null);
  const [err, setErr] = useState("");
  const [confirm, setConfirm] = useState(false);

  const load = useCallback(async () => {
    try {
      setR(await api<ResDetail>(`/reservations/${id}`));
      const m = await api<{ active: boolean }>("/dining/mine");
      if (m.active) nav("/goi-mon", { replace: true });
    } catch (e) { setErr((e as Error).message); }
  }, [id, nav]);
  useEffect(() => { load(); const h = setInterval(load, 5000); return () => clearInterval(h); }, [load]);

  const cancel = async () => {
    try {
      const x = await send<{ refund: number; forfeited: number }>("POST", `/reservations/${id}/cancel`);
      toast(x.refund ? `Đã hủy. Tiền cọc ${vnd(x.refund)} sẽ được hoàn lại` : x.forfeited ? "Đã hủy. Hủy muộn nên không hoàn cọc" : "Đã hủy lượt đặt");
      setConfirm(false); load();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  if (err) return <div className="wrap page"><p className="form-error" role="alert">{err}</p><Link to="/lich-su">Về danh sách</Link></div>;
  if (!r) return <p className="loading">Đang tải…</p>;
  const p = r.payment;
  const qr = p && p.bank_code && p.bank_account_number
    ? `https://img.vietqr.io/image/${p.bank_code}-${p.bank_account_number}-compact2.png?amount=${p.expected_amount}&addInfo=${encodeURIComponent(p.code)}&accountName=${encodeURIComponent(p.bank_account_name ?? "")}`
    : null;
  const live = r.status === "pending_deposit" || r.status === "confirmed";

  return (
    <div className="wrap page narrow">
      <p><Link to="/lich-su" className="btn-quiet">← Lượt đặt của tôi</Link></p>
      <div className="res-head">
        <h1 className="page-title">{hm(r.starts_at)} · {dmy(r.starts_at)}</h1>
        <span className={`badge badge-${statusTone(r.status)}`}>{RES_STATUS[r.status]}</span>
      </div>
      <p className="muted">{r.party_size} khách · {r.kind === "with_food" ? "Đặt bàn kèm món" : "Đặt bàn, chọn món sau"}{r.tables ? ` · Bàn ${r.tables}` : ""}</p>

      {r.status === "confirmed" && (
        <section className="ticket">
          <p className="eyebrow">Mã check-in</p>
          <div className="ticket-qr"><QRCodeSVG value={r.checkin_code} size={200} marginSize={2} title={`Mã check-in ${r.checkin_code}`} /></div>
          <p className="ticket-code">{r.checkin_code}</p>
          <p className="muted">Đưa mã này cho nhân viên khi đến quán. Trang này sẽ tự chuyển sang chọn món sau khi bạn được check-in.</p>
        </section>
      )}

      {r.status === "pending_deposit" && p && (
        <section className="note-box pay">
          <h2>Đặt cọc {vnd(p.expected_amount)} để giữ bàn</h2>
          <p>Giữ chỗ còn <Countdown to={p.expires_at} />. Hết giờ mà chưa nhận được tiền, bàn sẽ được nhả cho khách khác.</p>
          <div className="pay-grid">
            {qr ? <img src={qr} alt="Mã VietQR chuyển khoản đặt cọc" width={220} /> : <div className="photo-ph" style={{ width: 220, height: 220 }} />}
            <dl className="contact">
              <dt>Ngân hàng</dt><dd>{p.bank_code}</dd>
              <dt>Số tài khoản</dt><dd>{p.bank_account_number}</dd>
              <dt>Chủ tài khoản</dt><dd>{p.bank_account_name}</dd>
              <dt>Số tiền</dt><dd>{vnd(p.expected_amount)}</dd>
              <dt>Nội dung chuyển khoản</dt><dd><b>{p.code}</b></dd>
            </dl>
          </div>
          <p className="muted">Nhập đúng nội dung chuyển khoản. Quản lý sẽ xác nhận khi nhận được tiền và mã check-in sẽ hiện ngay tại đây.</p>
        </section>
      )}

      {r.status === "expired" && <p className="form-error">Lượt đặt đã hết hạn giữ chỗ vì chưa nhận được tiền cọc. <Link to="/dat-ban">Đặt lại</Link></p>}

      {r.items.length > 0 && (
        <section className="panel">
          <h2>Món đặt trước</h2>
          <ul className="order-lines">
            {r.items.map((i) => <li key={i.dish_id}><span>{i.quantity} × {i.name}</span><i /><b>{vnd(i.price_vnd * i.quantity)}</b></li>)}
            <li className="total"><span>Tổng</span><i /><b>{vnd(r.items_total)}</b></li>
          </ul>
          {r.deposit_amount > 0 && <p className="muted" style={{ marginBottom: 14 }}>Tiền cọc {vnd(r.deposit_amount)} sẽ được trừ vào hóa đơn.</p>}
        </section>
      )}
      {r.service_request && <section className="panel"><h2>Yêu cầu dịch vụ</h2><p style={{ marginBottom: 14 }}>{r.service_request}</p></section>}
      {r.note && <p className="muted">Ghi chú: {r.note}</p>}

      {live && (
        <div className="actions" style={{ marginTop: 22 }}>
          {!confirm ? <button className="btn-danger" onClick={() => setConfirm(true)}>Hủy lượt đặt</button> : (
            <>
              <span>Hủy lượt đặt này?</span>
              <button className="btn-danger" onClick={cancel}>Hủy lượt đặt</button>
              <button className="btn-quiet" onClick={() => setConfirm(false)}>Giữ lại</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
