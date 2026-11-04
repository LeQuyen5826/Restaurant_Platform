import { useCallback, useState } from "react";
import { Empty, useToast } from "../../components/ui";
import { usePoll } from "../../hooks/usePoll";
import { api, hm, RES_STATUS, send, vnd, ymd, type Reservation } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function TodayReservations() {
  const toast = useToast();
  const { user } = useAuth();
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<Reservation[] | null>(null);
  const load = useCallback(async () => {
    const d = new Date(); d.setDate(d.getDate() + offset);
    setRows(await api<Reservation[]>(`/reservations?date=${ymd(d)}`));
  }, [offset]);
  usePoll(() => load().catch(() => {}), 6000);
  const run = async (fn: () => Promise<unknown>, ok: string) => { try { await fn(); toast(ok); load(); } catch (e) { toast((e as Error).message, "err"); } };
  const late = (r: Reservation) => new Date(r.starts_at).getTime() + 15 * 60000 < Date.now();
  return (
    <>
      <header className="page-head"><div><h1>Đặt bàn</h1><p className="muted">Danh sách theo ngày, tự cập nhật.</p></div>
        <div className="seg" role="group" aria-label="Chọn ngày">{["Hôm nay", "Ngày mai", "Ngày kia"].map((l, i) => <button key={l} className={offset === i ? "on" : ""} onClick={() => setOffset(i)}>{l}</button>)}</div>
      </header>
      {rows && rows.length === 0 && <Empty title="Chưa có lượt đặt nào" />}
      <ul className="res-rows">
        {rows?.map((r) => (
          <li key={r.id}>
            <div className="grow">
              <p><b>{hm(r.starts_at)} · {r.customer_name ?? "Khách"}</b> <span className={`badge badge-${r.status === "confirmed" || r.status === "seated" ? "good" : r.status === "pending_deposit" ? "warn" : "dim"}`}>{RES_STATUS[r.status]}</span></p>
              <p className="muted">{r.party_size} khách · Bàn {r.tables || "—"}{r.customer_phone ? ` · ${r.customer_phone}` : ""} · {r.kind === "with_food" ? `Kèm món, cọc ${vnd(r.deposit_amount)}` : "Chọn món sau"} · Mã {r.checkin_code}</p>
              {r.service_request && <p className="slip-note">Yêu cầu: {r.service_request}</p>}
              {r.note && <p className="muted">Ghi chú: {r.note}</p>}
            </div>
            <div className="row-act">
              {r.status === "pending_deposit" && user?.role === "manager" && <button className="btn" onClick={() => run(() => send("POST", `/reservations/${r.id}/confirm-deposit`), "Đã xác nhận nhận cọc")}>Đã nhận cọc</button>}
              {r.status === "confirmed" && late(r) && <button className="btn-ghost" onClick={() => run(() => send("POST", `/reservations/${r.id}/no-show`), "Đã ghi vắng mặt")}>Vắng mặt</button>}
              {(r.status === "confirmed" || r.status === "pending_deposit") && <button className="btn-danger" onClick={() => window.confirm("Hủy lượt đặt này?") && run(() => send("POST", `/reservations/${r.id}/cancel`), "Đã hủy lượt đặt")}>Hủy</button>}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
