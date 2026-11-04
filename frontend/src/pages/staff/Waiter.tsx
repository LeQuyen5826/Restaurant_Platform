import { useCallback, useState } from "react";
import { Drawer, Empty, useToast } from "../../components/ui";
import { usePoll } from "../../hooks/usePoll";
import { api, hm, send, vnd } from "../../lib/api";

export interface FloorTable {
  id: string; code: string; capacity: number; area: string | null; state: "free" | "reserved" | "occupied";
  session: { id: string; opened_at: string; guests: number; new: number; preparing: number; ready: number } | null;
  reservation: { id: string; starts_at: string; party_size: number; status: string; name: string | null } | null;
}
interface Detail { id: string; table_code: string; items: { id: string; name: string; quantity: number; price_vnd: number; status: string; guest_name: string | null }[]; total: number; deposit_paid: number; amount_due: number }
const ST: Record<string, string> = { new: "Mới", preparing: "Đang làm", ready: "Chờ mang ra", served: "Đã ra", cancelled: "Đã hủy" };

export default function Waiter() {
  const toast = useToast();
  const [tables, setTables] = useState<FloorTable[] | null>(null);
  const [sel, setSel] = useState<FloorTable | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const t = await api<FloorTable[]>("/floor");
    setTables(t);
    setSel((cur) => (cur ? t.find((x) => x.id === cur.id) ?? null : cur));
  }, []);
  usePoll(() => load().catch(() => {}), 4000);
  usePoll(async () => {
    if (sel?.session) setDetail(await api<Detail>(`/floor/sessions/${sel.session.id}`).catch(() => null));
    else setDetail(null);
  }, 4000);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try { await fn(); toast(ok); setSel(null); await load(); } catch (e) { toast((e as Error).message, "err"); load(); }
    setBusy(false);
  };
  const areas = [...new Set((tables ?? []).map((t) => t.area ?? "Chưa gán khu vực"))];
  const counts = { free: 0, reserved: 0, occupied: 0 };
  tables?.forEach((t) => counts[t.state]++);

  return (
    <>
      <header className="page-head"><div><h1>Sơ đồ bàn</h1><p className="muted">{counts.free} trống · {counts.reserved} có đặt trước · {counts.occupied} đang có khách. Tự cập nhật.</p></div></header>
      {tables && tables.length === 0 && <Empty title="Chưa có bàn nào" hint="Nhờ quản lý tạo bàn." />}
      {areas.map((a) => (
        <section key={a} className="area">
          <header className="area-head"><h2>{a}</h2></header>
          <ul className="tiles">
            {tables?.filter((t) => (t.area ?? "Chưa gán khu vực") === a).map((t) => (
              <li key={t.id}>
                <button className={`tile st-${t.state}`} onClick={() => { setSel(t); setDetail(null); }}>
                  <b>{t.code}</b>
                  <span>{t.capacity} chỗ</span>
                  {t.state === "reserved" && t.reservation && <small>{hm(t.reservation.starts_at)} · {t.reservation.name ?? "Khách"}</small>}
                  {t.state === "occupied" && t.session && <small>{t.session.guests} người{t.session.ready > 0 ? ` · ${t.session.ready} món xong` : ""}</small>}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {sel && (
        <Drawer title={`Bàn ${sel.code}`} onClose={() => setSel(null)}>
          <p className="muted" style={{ marginBottom: 16 }}>{sel.capacity} chỗ{sel.area ? ` · ${sel.area}` : ""}</p>
          {sel.state === "free" && <button className="btn" disabled={busy} onClick={() => act(() => send("POST", "/floor/sessions", { table_id: sel.id }), `Đã mở bàn ${sel.code}`)}>Mở bàn cho khách vãng lai</button>}
          {sel.state === "reserved" && sel.reservation && (
            <>
              <p><b>{hm(sel.reservation.starts_at)} · {sel.reservation.name ?? "Khách"} · {sel.reservation.party_size} người</b></p>
              <p className="muted" style={{ margin: "6px 0 16px" }}>Khách đặt trước nên hãy dùng mục Check-in để quét mã của khách. Mở bàn thủ công chỉ khi khách không có mã.</p>
              {sel.reservation.status === "confirmed" && <button className="btn" disabled={busy} onClick={() => act(() => send("POST", "/floor/sessions", { table_id: sel.id, reservation_id: sel.reservation!.id }), `Đã nhận khách vào bàn ${sel.code}`)}>Khách đã đến, mở bàn</button>}
              {sel.reservation.status === "pending_deposit" && <p className="form-error">Khách chưa hoàn tất đặt cọc nên chưa nhận bàn được.</p>}
            </>
          )}
          {sel.state === "occupied" && (
            <>
              {!detail ? <p className="muted">Đang tải…</p> : detail.items.length === 0 ? <p className="muted">Khách chưa gọi món.</p> : (
                <ul className="ordered">
                  {detail.items.map((i) => (
                    <li key={i.id} className={`o-${i.status}`}>
                      <div><b>{i.quantity} × {i.name}</b>{i.guest_name && <small className="muted"> · {i.guest_name}</small>}</div>
                      <span className={`badge badge-${i.status === "ready" ? "good" : i.status === "cancelled" ? "bad" : i.status === "served" ? "dim" : "warn"}`}>{ST[i.status]}</span>
                    </li>
                  ))}
                </ul>
              )}
              {detail && (
                <dl className="bill">
                  <dt>Tạm tính</dt><dd>{vnd(detail.total)}</dd>
                  {detail.deposit_paid > 0 && <><dt>Đã cọc</dt><dd>− {vnd(detail.deposit_paid)}</dd></>}
                  <dt><b>Khách còn phải trả</b></dt><dd><b>{vnd(detail.amount_due)}</b></dd>
                </dl>
              )}
              <div className="form-foot"><button className="btn-danger" disabled={busy} onClick={() => act(() => send("POST", `/floor/sessions/${sel.session!.id}/close`), `Đã đóng bàn ${sel.code}`)}>Đóng bàn</button></div>
            </>
          )}
        </Drawer>
      )}
    </>
  );
}
