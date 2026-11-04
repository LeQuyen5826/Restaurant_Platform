import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Empty } from "../../components/ui";
import { api, dmy, hm, RES_STATUS, vnd, type Reservation } from "../../lib/api";
import { statusTone } from "./ReservationView";

export default function MyReservations() {
  const [rows, setRows] = useState<Reservation[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Reservation[]>("/reservations/mine").then(setRows).catch((e) => setErr(e.message)); }, []);
  return (
    <div className="wrap page narrow">
      <div className="block-head"><h1 className="page-title">Lượt đặt của tôi</h1><Link to="/dat-ban" className="btn">Đặt bàn mới</Link></div>
      {err && <p className="form-error" role="alert">{err}</p>}
      {rows && rows.length === 0 && <Empty title="Bạn chưa đặt bàn nào" hint="Chọn ngày giờ và giữ bàn trước khi đến."><Link to="/dat-ban" className="btn">Đặt bàn</Link></Empty>}
      <ul className="res-list">
        {rows?.map((r) => (
          <li key={r.id}>
            <Link to={`/dat-ban/${r.id}`} className="res-card">
              <div><b className="res-time">{hm(r.starts_at)}</b><span className="muted"> · {dmy(r.starts_at)}</span></div>
              <p className="muted">{r.party_size} khách · {r.kind === "with_food" ? `Kèm món, cọc ${vnd(r.deposit_amount)}` : "Chọn món sau"}{r.tables ? ` · Bàn ${r.tables}` : ""}</p>
              <span className={`badge badge-${statusTone(r.status)}`}>{RES_STATUS[r.status]}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
