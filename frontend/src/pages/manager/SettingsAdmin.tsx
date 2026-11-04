import { useEffect, useState, type FormEvent } from "react";
import { useToast } from "../../components/ui";
import { api, send, type Settings, type Shift } from "../../lib/api";

const DAYS = ["Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Chủ nhật"];

export default function SettingsAdmin() {
  const toast = useToast();
  const [s, setS] = useState<Settings | null>(null);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [busy, setBusy] = useState(false);
  const [svcs, setSvcs] = useState<{ title: string; description: string | null; icon: string | null }[]>([]);

  useEffect(() => {
    Promise.all([api<Settings>("/restaurant/settings"), api<Shift[]>("/service-windows"), api<typeof svcs>("/restaurant/services")])
      .then(([a, b, c]) => { setS(a); setShifts(b); setSvcs(c); })
      .catch((e) => toast(e.message, "err"));
  }, [toast]);
  if (!s) return <p className="muted">Đang tải…</p>;

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS({ ...s, [k]: v });
  const num = (k: keyof Settings) => (e: React.ChangeEvent<HTMLInputElement>) => set(k, Number(e.target.value) as never);
  const txt = (k: keyof Settings) => (e: React.ChangeEvent<HTMLInputElement>) => set(k, (e.target.value || null) as never);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { id: _id, ...body } = s;
      await send("PUT", "/restaurant/settings", body);
      setShifts(await send<Shift[]>("PUT", "/service-windows", shifts));
      await send("PUT", "/restaurant/services", svcs.filter((x) => x.title.trim()).map(({ title, description, icon }) => ({ title, description, icon })));
      toast("Đã lưu cài đặt");
    } catch (err) { toast((err as Error).message, "err"); }
    setBusy(false);
  };
  const upd = (i: number, p: Partial<Shift>) => setShifts(shifts.map((x, j) => (j === i ? { ...x, ...p } : x)));

  return (
    <form onSubmit={save}>
      <header className="page-head">
        <div><h1>Cài đặt</h1><p className="muted">Thông tin quán, quy tắc đặt bàn và giờ mở cửa</p></div>
        <div className="head-actions"><button className="btn" disabled={busy}>{busy ? "Đang lưu" : "Lưu thay đổi"}</button></div>
      </header>

      <section className="panel">
        <h2>Thông tin quán</h2>
        <label className="field"><span>Tên quán</span><input value={s.name} onChange={(e) => set("name", e.target.value)} required /></label>
        <div className="two">
          <label className="field"><span>Địa chỉ</span><input value={s.address ?? ""} onChange={txt("address")} /></label>
          <label className="field"><span>Điện thoại</span><input value={s.phone ?? ""} onChange={txt("phone")} /></label>
        </div>
        <label className="field"><span>Khẩu hiệu (hiện ở trang chủ)</span><input value={s.tagline ?? ""} onChange={txt("tagline")} /></label>
        <label className="field"><span>Giới thiệu quán</span><textarea rows={4} value={s.about ?? ""} onChange={(e) => set("about", (e.target.value || null) as never)} /></label>
      </section>

      <section className="panel">
        <h2>Liên hệ và mạng xã hội</h2>
        <p className="muted">Hiện ở trang Liên hệ. Để trống mạng nào thì mạng đó không hiện.</p>
        <div className="two">
          <label className="field"><span>Email</span><input type="email" value={s.email ?? ""} onChange={txt("email")} /></label>
          <label className="field"><span>Liên kết bản đồ</span><input value={s.map_url ?? ""} onChange={txt("map_url")} placeholder="https://maps.google.com/…" /></label>
          <label className="field"><span>Facebook</span><input value={s.facebook_url ?? ""} onChange={txt("facebook_url")} /></label>
          <label className="field"><span>TikTok</span><input value={s.tiktok_url ?? ""} onChange={txt("tiktok_url")} /></label>
          <label className="field"><span>Instagram</span><input value={s.instagram_url ?? ""} onChange={txt("instagram_url")} /></label>
          <label className="field"><span>YouTube</span><input value={s.youtube_url ?? ""} onChange={txt("youtube_url")} /></label>
          <label className="field"><span>Zalo</span><input value={s.zalo_url ?? ""} onChange={txt("zalo_url")} /></label>
        </div>
      </section>

      <section className="panel">
        <h2>Dịch vụ của quán</h2>
        <p className="muted">Hiện ở trang Dịch vụ. Biểu tượng: calendar, restaurant, gift, qr, leaf.</p>
        {svcs.map((x, i) => (
          <div key={i} className="svc-edit">
            <input value={x.title} placeholder="Tên dịch vụ" aria-label="Tên dịch vụ" onChange={(e) => setSvcs(svcs.map((y, j) => (j === i ? { ...y, title: e.target.value } : y)))} />
            <input value={x.icon ?? ""} placeholder="Biểu tượng" aria-label="Biểu tượng" onChange={(e) => setSvcs(svcs.map((y, j) => (j === i ? { ...y, icon: e.target.value || null } : y)))} />
            <input value={x.description ?? ""} placeholder="Mô tả ngắn" aria-label="Mô tả" onChange={(e) => setSvcs(svcs.map((y, j) => (j === i ? { ...y, description: e.target.value || null } : y)))} />
            <button type="button" className="btn-quiet" onClick={() => setSvcs(svcs.filter((_, j) => j !== i))}>Bỏ</button>
          </div>
        ))}
        <p style={{ marginBottom: 14 }}><button type="button" className="btn-ghost" onClick={() => setSvcs([...svcs, { title: "", description: null, icon: "restaurant" }])}>Thêm dịch vụ</button></p>
      </section>

      <section className="panel">
        <h2>Quy tắc đặt bàn</h2>
        <div className="three">
          <label className="field"><span>Bước khung giờ (phút)</span><input type="number" min={5} value={s.slot_minutes} onChange={num("slot_minutes")} required /></label>
          <label className="field"><span>Thời gian một bữa (phút)</span><input type="number" min={15} value={s.dining_minutes} onChange={num("dining_minutes")} required /></label>
          <label className="field"><span>Đệm dọn bàn (phút)</span><input type="number" min={0} value={s.turn_buffer_minutes} onChange={num("turn_buffer_minutes")} required /></label>
        </div>
        <p className="muted">Một bàn được giữ trong {s.dining_minutes + s.turn_buffer_minutes} phút cho mỗi lượt đặt ({s.dining_minutes} phút ăn + {s.turn_buffer_minutes} phút dọn).</p>
      </section>

      <section className="panel">
        <h2>Đặt cọc</h2>
        <div className="three">
          <label className="field"><span>Cọc theo % giá trị món đặt trước</span><input type="number" min={0} max={100} value={s.deposit_percent} onChange={num("deposit_percent")} required /><small className="muted">Chỉ áp dụng cho đặt bàn kèm món.</small></label>
          <label className="field"><span>Tiền cọc tối thiểu (đồng)</span><input type="number" min={0} step={10000} value={s.deposit_amount} onChange={num("deposit_amount")} required /></label>
          <label className="field"><span>Giữ chỗ chờ chuyển khoản (phút)</span><input type="number" min={1} value={s.deposit_hold_minutes} onChange={num("deposit_hold_minutes")} required /></label>
          <label className="field"><span>Hoàn cọc nếu hủy trước (giờ)</span><input type="number" min={0} value={s.free_cancel_hours} onChange={num("free_cancel_hours")} required /></label>
          <label className="field"><span>Giữ bàn sau giờ hẹn (phút)</span><input type="number" min={0} value={s.late_grace_minutes} onChange={num("late_grace_minutes")} required /><small className="muted">Quá thời gian này nhân viên được ghi vắng mặt.</small></label>
        </div>
        <div className="three">
          <label className="field"><span>Mã ngân hàng</span><input value={s.bank_code ?? ""} onChange={txt("bank_code")} placeholder="VCB, MB, ACB…" /></label>
          <label className="field"><span>Số tài khoản nhận cọc</span><input value={s.bank_account_number ?? ""} onChange={txt("bank_account_number")} inputMode="numeric" /></label>
          <label className="field"><span>Tên chủ tài khoản</span><input value={s.bank_account_name ?? ""} onChange={txt("bank_account_name")} /></label>
        </div>
      </section>

      <section className="panel">
        <h2>Giờ mở cửa</h2>
        <p className="muted">Mỗi ngày có thể có nhiều ca, ví dụ ca trưa và ca tối. Ngày không có ca nào là ngày nghỉ.</p>
        <ul className="week">
          {DAYS.map((label, i) => {
            const day = i + 1;
            const mine = shifts.map((x, idx) => ({ x, idx })).filter(({ x }) => x.weekday === day);
            return (
              <li key={day}>
                <b>{label}</b>
                <div className="week-shifts">
                  {mine.length === 0 && <span className="muted">Nghỉ</span>}
                  {mine.map(({ x, idx }) => (
                    <span key={idx} className="shift">
                      <input type="time" value={x.open_time} onChange={(e) => upd(idx, { open_time: e.target.value })} aria-label={`${label} giờ mở`} />
                      <span aria-hidden="true">–</span>
                      <input type="time" value={x.close_time} onChange={(e) => upd(idx, { close_time: e.target.value })} aria-label={`${label} giờ đóng`} />
                      <button type="button" className="btn-quiet" onClick={() => setShifts(shifts.filter((_, j) => j !== idx))} aria-label={`Bỏ ca ${x.open_time} ${label}`}>Bỏ</button>
                    </span>
                  ))}
                  <button type="button" className="btn-quiet" onClick={() => setShifts([...shifts, { weekday: day, open_time: "10:00", close_time: "22:00" }])}>Thêm ca</button>
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </form>
  );
}
