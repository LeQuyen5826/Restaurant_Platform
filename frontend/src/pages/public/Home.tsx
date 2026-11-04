import { Link } from "react-router-dom";
import { DishPhoto, useHome } from "../../components/PublicLayout";
import { Chili } from "../../components/ui";
import { DAY_NAMES, vnd } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export default function Home() {
  const { home, err } = useHome();
  const { user } = useAuth();
  if (err) return <p className="form-error wrap" role="alert">{err}</p>;
  if (!home) return <p className="loading">Đang tải…</p>;
  const r = home.restaurant;
  // gom các ngày có cùng giờ mở cửa để bảng giờ ngắn gọn
  const rows: { days: number[]; shifts: string[] }[] = [];
  home.hours.forEach((h) => {
    const last = rows[rows.length - 1];
    if (last && last.shifts.join() === h.shifts.join()) last.days.push(h.weekday);
    else rows.push({ days: [h.weekday], shifts: h.shifts });
  });
  const label = (d: number[]) => (d.length === 1 ? DAY_NAMES[d[0] - 1] : `${DAY_NAMES[d[0] - 1]} – ${DAY_NAMES[d[d.length - 1] - 1]}`);
  return (
    <>
      <section className="hero">
        <div className="wrap hero-in">
          <div>
            <p className="eyebrow">{r.address}</p>
            <h1 className="hero-title">{r.name}</h1>
            <p className="hero-tag">{r.tagline}</p>
            <div className="hero-cta">
              <Link to={user?.role === "customer" || !user ? "/dat-ban" : "/"} className="btn btn-lg">Đặt bàn ngay</Link>
              <Link to="/mon-an" className="btn-ghost btn-lg">Xem món ăn</Link>
            </div>
          </div>
          <div className="slip hero-slip" aria-hidden="true">
            <div className="slip-head"><span>Bàn A03</span><span>19:00</span></div>
            <p className="slip-sub">4 khách · Tầng 1</p>
            <ul>
              <li><span>Gỏi cuốn tôm thịt</span><i /><b>2</b></li>
              <li><span>Bún chả Hà Nội</span><i /><b>3</b></li>
              <li><span>Cà phê sữa đá</span><i /><b>4</b></li>
            </ul>
            <span className="slip-note">Sinh nhật mẹ, cần bánh kem</span>
          </div>
        </div>
      </section>

      <section className="wrap block">
        <h2 className="block-title">Về quán</h2>
        <p className="lead">{r.about}</p>
      </section>

      <section className="wrap block">
        <div className="block-head"><h2 className="block-title">Món được gọi nhiều</h2><Link to="/mon-an">Xem toàn bộ thực đơn</Link></div>
        <ul className="cards">
          {home.featured.map((d) => (
            <li key={d.id} className="dcard">
              <DishPhoto src={d.image_url} name={d.name} />
              <div className="dcard-body">
                <p className="dish-name">{d.name}<Chili n={d.spiciness} />{d.is_vegetarian && <span className="veg">chay</span>}</p>
                {d.description && <p className="muted clamp">{d.description}</p>}
                <p className="dish-price">{vnd(d.price_vnd)}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="wrap block two-col">
        <div>
          <h2 className="block-title">Giờ mở cửa</h2>
          <ul className="hours">
            {rows.map((x) => (
              <li key={x.days[0]}><span>{label(x.days)}</span><i /><b>{x.shifts.length ? x.shifts.join(" · ") : "Nghỉ"}</b></li>
            ))}
          </ul>
        </div>
        <div className="how">
          <h2 className="block-title">Đặt bàn thế nào</h2>
          <ol>
            <li><b>Đăng nhập</b> rồi chọn ngày, giờ, số khách để xem bàn còn trống.</li>
            <li><b>Đặt bàn thường</b> hoặc <b>đặt bàn kèm món</b> (có đặt cọc {r.deposit_percent}%).</li>
            <li><b>Nhận mã QR</b> và đưa cho nhân viên khi đến quán để check-in.</li>
            <li><b>Chọn món</b> ngay trên điện thoại, bếp nhận phiếu và mang ra bàn.</li>
          </ol>
        </div>
      </section>
    </>
  );
}
