import { Link } from "react-router-dom";
import { useHome } from "../../components/PublicLayout";
import { vnd } from "../../lib/api";

const ICON: Record<string, string> = { calendar: "M7 2v3M17 2v3M3 8h18M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z",
  restaurant: "M6 2v9M10 2v9M6 7h4M8 11v11M17 2c-2 2-3 5-3 8h3v12", gift: "M3 9h18v4H3zM12 9v13M5 13v8h14v-8M12 9c-2-4-6-4-6-1s4 1 6 1Zm0 0c2-4 6-4 6-1s-4 1-6 1Z",
  qr: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h3v3h-3zM20 14v3M14 20h3M20 20v1", leaf: "M5 19C5 9 11 4 20 4c0 9-5 15-15 15ZM5 19c3-5 6-8 10-10" };

export default function Services() {
  const { home, err } = useHome();
  if (err) return <p className="form-error wrap" role="alert">{err}</p>;
  if (!home) return <p className="loading">Đang tải…</p>;
  const r = home.restaurant;
  return (
    <div className="wrap page">
      <h1 className="page-title">Dịch vụ</h1>
      <p className="muted lead-sm">Ngoài bữa ăn thường ngày, quán nhận giữ bàn trước, chuẩn bị món sẵn và tổ chức các dịp đặc biệt.</p>
      <ul className="svc">
        {home.services.map((s) => (
          <li key={s.title}>
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={ICON[s.icon ?? ""] ?? ICON.restaurant} /></svg>
            <h2>{s.title}</h2>
            <p className="muted">{s.description}</p>
          </li>
        ))}
      </ul>
      <section className="note-box">
        <h2>Quy định đặt cọc</h2>
        <ul>
          <li>Đặt bàn thường (chọn món sau khi đến) không cần đặt cọc.</li>
          <li>Đặt bàn kèm món cần cọc {r.deposit_percent}% giá trị món đặt trước, tối thiểu {vnd(r.deposit_amount)}. Tiền cọc được trừ vào hóa đơn.</li>
          <li>Hủy trước giờ hẹn {r.free_cancel_hours} giờ: hoàn lại toàn bộ tiền cọc. Hủy muộn hơn hoặc vắng mặt: không hoàn cọc.</li>
        </ul>
        <Link to="/dat-ban" className="btn">Đặt bàn kèm yêu cầu dịch vụ</Link>
      </section>
    </div>
  );
}
