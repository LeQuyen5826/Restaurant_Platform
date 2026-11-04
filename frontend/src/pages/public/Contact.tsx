import { useHome } from "../../components/PublicLayout";
import { DAY_NAMES } from "../../lib/api";

const SOCIAL: [keyof import("../../lib/api").PublicHome["restaurant"], string][] = [
  ["facebook_url", "Facebook"], ["tiktok_url", "TikTok"], ["instagram_url", "Instagram"], ["youtube_url", "YouTube"], ["zalo_url", "Zalo"],
];

export default function Contact() {
  const { home, err } = useHome();
  if (err) return <p className="form-error wrap" role="alert">{err}</p>;
  if (!home) return <p className="loading">Đang tải…</p>;
  const r = home.restaurant;
  return (
    <div className="wrap page">
      <h1 className="page-title">Liên hệ</h1>
      <div className="two-col">
        <dl className="contact">
          {r.address && <><dt>Địa chỉ</dt><dd>{r.address}{r.map_url && <> · <a href={r.map_url} target="_blank" rel="noreferrer">Xem bản đồ</a></>}</dd></>}
          {r.phone && <><dt>Điện thoại</dt><dd><a href={`tel:${r.phone.replace(/\s/g, "")}`}>{r.phone}</a></dd></>}
          {r.email && <><dt>Email</dt><dd><a href={`mailto:${r.email}`}>{r.email}</a></dd></>}
          <dt>Mạng xã hội</dt>
          <dd className="social">
            {SOCIAL.filter(([k]) => r[k]).map(([k, label]) => <a key={k} className="chip" href={String(r[k])} target="_blank" rel="noreferrer">{label}</a>)}
          </dd>
        </dl>
        <div>
          <h2 className="block-title">Giờ mở cửa</h2>
          <ul className="hours">
            {home.hours.map((h) => <li key={h.weekday}><span>{DAY_NAMES[h.weekday - 1]}</span><i /><b>{h.shifts.length ? h.shifts.join(" · ") : "Nghỉ"}</b></li>)}
          </ul>
        </div>
      </div>
    </div>
  );
}
