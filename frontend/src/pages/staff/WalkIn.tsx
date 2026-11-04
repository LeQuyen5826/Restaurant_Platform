import { useState } from "react";
import { Empty, useToast } from "../../components/ui";
import { api, send } from "../../lib/api";

interface Opt { id: string; code: string; capacity: number; area: string | null }

export default function WalkIn() {
  const toast = useToast();
  const [party, setParty] = useState(2);
  const [opts, setOpts] = useState<Opt[] | null>(null);
  const [busy, setBusy] = useState(false);
  const find = async (p = party) => { try { setOpts(await api<Opt[]>(`/floor/walk-in?party=${p}`)); } catch (e) { toast((e as Error).message, "err"); } };
  const open = async (t: Opt) => {
    setBusy(true);
    try { await send("POST", "/floor/sessions", { table_id: t.id }); toast(`Đã xếp khách vào bàn ${t.code}. Khách quét mã QR trên bàn để gọi món`); setOpts(null); }
    catch (e) { toast((e as Error).message, "err"); find(); }
    setBusy(false);
  };
  const change = (n: number) => { const p = Math.max(1, Math.min(30, n)); setParty(p); setOpts(null); };
  return (
    <>
      <header className="page-head"><div><h1>Nhận khách chưa đặt trước</h1><p className="muted">Nhập số khách, hệ thống gợi ý bàn trống nhỏ nhất phù hợp và không vướng lượt đặt sắp tới.</p></div></header>
      <section className="panel">
        <div className="party" style={{ marginBottom: 14 }}>
          <span>Số khách</span>
          <button className="step-btn" onClick={() => change(party - 1)} aria-label="Giảm">−</button><b>{party}</b>
          <button className="step-btn" onClick={() => change(party + 1)} aria-label="Tăng">+</button>
          <button className="btn" onClick={() => find()}>Tìm bàn trống</button>
        </div>
        {opts && opts.length === 0 && <Empty title={`Hiện không còn bàn trống cho ${party} khách`} hint="Thử ghép bàn hoặc mời khách chờ." />}
        {opts && opts.length > 0 && (
          <ul className="opts">
            {opts.map((t, i) => (
              <li key={t.id}>
                <div><b className="opt-code">Bàn {t.code}</b><span className="muted"> · {t.capacity} chỗ{t.area ? ` · ${t.area}` : ""}</span>{i === 0 && <span className="veg">phù hợp nhất</span>}</div>
                <button className="btn" disabled={busy} onClick={() => open(t)}>Xếp khách vào bàn</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
