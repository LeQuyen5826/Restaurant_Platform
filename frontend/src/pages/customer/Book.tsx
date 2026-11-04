import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { DishPhoto } from "../../components/PublicLayout";
import { useToast } from "../../components/ui";
import { api, pad, send, vnd, WEEKDAYS, ymd, type PubMenu, type PublicHome, type ResDetail } from "../../lib/api";

interface Slot { time: string; free_tables: number; total_tables: number }
type Kind = "table_only" | "with_food";

export default function Book() {
  const nav = useNavigate();
  const toast = useToast();
  const [kind, setKind] = useState<Kind>("table_only");
  const [date, setDate] = useState(ymd(new Date()));
  const [party, setParty] = useState(2);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [time, setTime] = useState("");
  const [menu, setMenu] = useState<PubMenu | null>(null);
  const [home, setHome] = useState<PublicHome["restaurant"] | null>(null);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [request, setRequest] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const days = useMemo(() => Array.from({ length: 14 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return d; }), []);

  useEffect(() => {
    api<PublicHome>("/public/home").then((h) => setHome(h.restaurant)).catch(() => {});
    api<PubMenu>("/public/menu").then(setMenu).catch(() => {});
  }, []);
  useEffect(() => {
    setSlots(null); setTime("");
    api<{ slots: Slot[] }>(`/availability?date=${date}&party=${party}`).then((r) => setSlots(r.slots)).catch((e) => { toast(e.message, "err"); setSlots([]); });
  }, [date, party, toast]);

  const dishes = menu?.sections.flatMap((s) => s.dishes.map((d) => ({ ...d, cat: s.name }))) ?? [];
  const lines = dishes.filter((d) => (qty[d.id] ?? 0) > 0);
  const total = lines.reduce((s, d) => s + d.price_vnd * qty[d.id], 0);
  const deposit = home && total ? Math.min(Math.max(Math.ceil((total * home.deposit_percent) / 100 / 1000) * 1000, home.deposit_amount), total) : 0;
  const setQ = (id: string, n: number) => setQty((q) => ({ ...q, [id]: Math.max(0, Math.min(99, n)) }));

  const submit = async () => {
    if (!time) return toast("Hãy chọn khung giờ", "err");
    if (kind === "with_food" && lines.length === 0) return toast("Hãy chọn ít nhất một món", "err");
    setBusy(true);
    try {
      const r = await send<ResDetail>("POST", "/reservations", {
        date, time, party_size: party, kind, note: note || null,
        items: kind === "with_food" ? lines.map((d) => ({ dish_id: d.id, quantity: qty[d.id] })) : [],
        service_request: kind === "with_food" ? request || null : null,
      });
      nav(`/dat-ban/${r.id}`, { replace: true });
    } catch (e) { toast((e as Error).message, "err"); }
    setBusy(false);
  };

  return (
    <div className="wrap page">
      <h1 className="page-title">Đặt bàn</h1>

      <section className="step">
        <h2><span className="n">1</span> Chọn loại đặt bàn</h2>
        <div className="kinds" role="radiogroup" aria-label="Loại đặt bàn">
          <button role="radio" aria-checked={kind === "table_only"} className={`kind ${kind === "table_only" ? "on" : ""}`} onClick={() => setKind("table_only")}>
            <b>Đặt bàn, đến rồi chọn món</b>
            <span>Giữ chỗ miễn phí. Khi đến quán, nhân viên check-in rồi bạn chọn món ngay trên điện thoại.</span>
          </button>
          <button role="radio" aria-checked={kind === "with_food"} className={`kind ${kind === "with_food" ? "on" : ""}`} onClick={() => setKind("with_food")}>
            <b>Đặt bàn kèm món và dịch vụ</b>
            <span>Chọn món trước để bếp chuẩn bị, ghi yêu cầu sinh nhật, sự kiện. Cần đặt cọc{home ? ` ${home.deposit_percent}%` : ""}.</span>
          </button>
        </div>
      </section>

      <section className="step">
        <h2><span className="n">2</span> Ngày, giờ, số khách</h2>
        <div className="dayrow" role="listbox" aria-label="Chọn ngày">
          {days.map((d) => {
            const v = ymd(d);
            return (
              <button key={v} role="option" aria-selected={date === v} className={`day ${date === v ? "on" : ""}`} onClick={() => setDate(v)}>
                <small>{WEEKDAYS[d.getDay()]}</small><b>{pad(d.getDate())}</b><small>Th{d.getMonth() + 1}</small>
              </button>
            );
          })}
        </div>
        <div className="party">
          <span>Số khách</span>
          <button className="step-btn" onClick={() => setParty(Math.max(1, party - 1))} aria-label="Giảm số khách">−</button>
          <b aria-live="polite">{party}</b>
          <button className="step-btn" onClick={() => setParty(Math.min(20, party + 1))} aria-label="Tăng số khách">+</button>
        </div>
        {slots === null ? <p className="muted">Đang kiểm tra bàn trống…</p> : slots.length === 0 ? (
          <p className="muted">Không còn khung giờ nào trong ngày này cho {party} khách. Thử ngày khác.</p>
        ) : (
          <ul className="slots" aria-label="Khung giờ">
            {slots.map((s) => (
              <li key={s.time}>
                <button className={`slot ${time === s.time ? "on" : ""}`} disabled={s.free_tables === 0} aria-pressed={time === s.time} onClick={() => setTime(s.time)}>
                  <b>{s.time}</b><small>{s.free_tables === 0 ? "Hết bàn" : `Còn ${s.free_tables} bàn`}</small>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {kind === "with_food" && (
        <section className="step">
          <h2><span className="n">3</span> Món đặt trước</h2>
          <p className="muted">Món sẽ được gửi xuống bếp khi bạn check-in tại quán, nên vẫn nóng khi mang ra. Bạn vẫn gọi thêm được sau đó.</p>
          {menu?.sections.map((s) => (
            <div key={s.name} className="pick-sec">
              <h3>{s.name}</h3>
              <ul className="pick">
                {s.dishes.filter((d) => d.is_available).map((d) => (
                  <li key={d.id}>
                    <DishPhoto src={d.image_url} name={d.name} className="pick-photo" />
                    <div className="pick-body"><b>{d.name}</b><span className="muted">{vnd(d.price_vnd)}</span></div>
                    <div className="stepper">
                      {(qty[d.id] ?? 0) > 0 && <><button className="step-btn" onClick={() => setQ(d.id, qty[d.id] - 1)} aria-label={`Bớt ${d.name}`}>−</button><b>{qty[d.id]}</b></>}
                      <button className="step-btn" onClick={() => setQ(d.id, (qty[d.id] ?? 0) + 1)} aria-label={`Thêm ${d.name}`}>+</button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <label className="field" style={{ marginTop: 18 }}>
            <span>Yêu cầu kèm theo dịch vụ (không bắt buộc)</span>
            <textarea rows={3} maxLength={500} value={request} onChange={(e) => setRequest(e.target.value)} placeholder="Ví dụ: tổ chức sinh nhật mẹ, cần bánh kem và trang trí bóng bay" />
          </label>
        </section>
      )}

      <section className="step">
        <h2><span className="n">{kind === "with_food" ? 4 : 3}</span> Xác nhận</h2>
        <label className="field"><span>Ghi chú cho quán (không bắt buộc)</span><input maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ví dụ: có trẻ nhỏ, cần ghế em bé" /></label>
        <div className="summary">
          <p><b>{time || "Chưa chọn giờ"}</b>{time && <> · {date.split("-").reverse().join("/")} · {party} khách</>}</p>
          {kind === "with_food" && (
            <>
              <p>{lines.length} món · {vnd(total)}</p>
              <p>Tiền cọc: <b>{vnd(deposit)}</b>{home && <span className="muted"> ({home.deposit_percent}% giá trị món, tối thiểu {vnd(home.deposit_amount)}), trừ vào hóa đơn</span>}</p>
              {home && <p className="muted">Hủy trước giờ hẹn {home.free_cancel_hours} giờ được hoàn cọc, hủy muộn hoặc vắng mặt thì không hoàn.</p>}
            </>
          )}
        </div>
        <div className="actions">
          <button className="btn btn-lg" onClick={submit} disabled={busy}>{busy ? "Đang đặt" : kind === "with_food" ? "Đặt bàn và nhận hướng dẫn cọc" : "Xác nhận đặt bàn"}</button>
          <Link to="/lich-su" className="btn-quiet">Xem lượt đặt của tôi</Link>
        </div>
      </section>
    </div>
  );
}
