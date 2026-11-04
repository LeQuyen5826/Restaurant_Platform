import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { usePoll } from "../../hooks/usePoll";
import { api, hm, RES_STATUS, type ResStatus } from "../../lib/api";

interface Ov {
  tables: number; seats: number; dishes: number; dishes_out: number; reservations_today: number; guests_today: number;
  sessions_open: number; kitchen_queue: number; today_shifts: string[];
  upcoming: { id: string; party_size: number; starts_at: string; status: ResStatus; name: string | null; tables: string | null }[];
}

export default function Overview() {
  const [o, setO] = useState<Ov | null>(null);
  const load = useCallback(async () => setO(await api<Ov>("/overview")), []);
  usePoll(() => load().catch(() => {}), 10000);
  if (!o) return <p className="muted">Đang tải…</p>;
  const stats: [string, number | string, string][] = [
    ["Lượt đặt hôm nay", o.reservations_today, `${o.guests_today} khách`],
    ["Bàn đang có khách", o.sessions_open, `trên tổng ${o.tables} bàn`],
    ["Phiếu bếp đang chờ", o.kitchen_queue, "mới và đang làm"],
    ["Món đang hết", o.dishes_out, `trên ${o.dishes} món`],
  ];
  return (
    <>
      <header className="page-head"><div><h1>Tổng quan</h1><p className="muted">Hôm nay mở cửa: {o.today_shifts.length ? o.today_shifts.join(" · ") : "nghỉ"}. Tự cập nhật.</p></div></header>
      <ul className="stats">{stats.map(([l, v, s]) => <li key={l}><span>{l}</span><b>{v}</b><small className="muted">{s}</small></li>)}</ul>
      <section className="panel">
        <h2>Lượt đặt sắp tới hôm nay</h2>
        {o.upcoming.length === 0 ? <p className="muted" style={{ marginBottom: 14 }}>Hôm nay chưa có lượt đặt nào.</p> : (
          <ul className="up-list">
            {o.upcoming.map((u) => <li key={u.id}><b>{hm(u.starts_at)}</b><span>{u.name ?? "Khách"} · {u.party_size} khách · Bàn {u.tables ?? "—"}</span><em>{RES_STATUS[u.status]}</em></li>)}
          </ul>
        )}
        <p style={{ marginBottom: 14 }}><Link to="/quan-ly/dat-ban">Xem tất cả lượt đặt và xác nhận cọc</Link></p>
      </section>
    </>
  );
}
