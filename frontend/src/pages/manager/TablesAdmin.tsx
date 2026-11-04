import { useCallback, useEffect, useState, type FormEvent } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Drawer, Empty, useToast } from "../../components/ui";
import { api, send, type Area, type DiningTable } from "../../lib/api";

const blank = (area: string | null): DiningTable => ({ id: "", code: "", capacity: 4, min_party: 1, area_id: area, is_active: true });

export default function TablesAdmin() {
  const toast = useToast();
  const [areas, setAreas] = useState<Area[]>([]);
  const [tables, setTables] = useState<DiningTable[]>([]);
  const [edit, setEdit] = useState<DiningTable | null>(null);
  const [areaName, setAreaName] = useState("");
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try { const [a, t] = await Promise.all([api<Area[]>("/areas"), api<DiningTable[]>("/tables")]); setAreas(a); setTables(t); }
    catch (e) { toast((e as Error).message, "err"); }
    setLoaded(true);
  }, [toast]);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); toast(ok); load(); } catch (e) { toast((e as Error).message, "err"); }
  };
  const groups: { id: string | null; name: string; items: DiningTable[] }[] = [
    ...areas.map((a) => ({ id: a.id, name: a.name, items: tables.filter((t) => t.area_id === a.id) })),
    { id: null, name: "Chưa gán khu vực", items: tables.filter((t) => !t.area_id) },
  ].filter((g) => g.id || g.items.length);
  const seats = tables.filter((t) => t.is_active).reduce((s, t) => s + t.capacity, 0);

  return (
    <>
      <header className="page-head">
        <div><h1>Bàn</h1><p className="muted">{tables.filter((t) => t.is_active).length} bàn đang mở · {seats} chỗ ngồi</p></div>
        <div className="head-actions"><button className="btn" onClick={() => setEdit(blank(areas[0]?.id ?? null))}>Thêm bàn</button></div>
      </header>

      <form className="inline-add" onSubmit={(e) => { e.preventDefault(); if (!areaName.trim()) return; run(() => send("POST", "/areas", { name: areaName }), `Đã thêm khu ${areaName}`).then(() => setAreaName("")); }}>
        <input value={areaName} onChange={(e) => setAreaName(e.target.value)} placeholder="Tên khu vực mới, ví dụ Tầng 2" aria-label="Tên khu vực mới" />
        <button className="btn-ghost">Thêm khu vực</button>
      </form>

      {loaded && tables.length === 0 && areas.length === 0 && (
        <Empty title="Chưa có bàn nào" hint="Tạo khu vực trước (Tầng 1, Sân vườn…), sau đó thêm bàn vào từng khu." />
      )}

      {groups.map((g) => (
        <section key={g.id ?? "none"} className="area">
          <header className="area-head">
            {g.id ? (
              <input className="area-name" defaultValue={g.name} aria-label={`Tên khu vực ${g.name}`}
                onBlur={(e) => e.target.value.trim() && e.target.value !== g.name && run(() => send("PATCH", `/areas/${g.id}`, { name: e.target.value }), "Đã đổi tên khu vực")} />
            ) : <h2>{g.name}</h2>}
            <span className="muted">{g.items.length} bàn</span>
            {g.id && <button className="btn-quiet" onClick={() => confirm(`Xóa khu "${g.name}"? Các bàn trong khu sẽ chuyển sang "Chưa gán khu vực".`) && run(() => send("DELETE", `/areas/${g.id}`), `Đã xóa khu ${g.name}`)}>Xóa khu</button>}
          </header>
          {g.items.length === 0 ? <p className="muted">Khu này chưa có bàn.</p> : (
            <ul className="tiles">
              {g.items.map((t) => (
                <li key={t.id}>
                  <button className={`tile ${t.is_active ? "" : "off"}`} onClick={() => setEdit(t)} aria-label={`Bàn ${t.code}, ${t.capacity} chỗ${t.is_active ? "" : ", đang tắt"}`}>
                    <b>{t.code}</b>
                    <span>{t.capacity} chỗ</span>
                    {!t.is_active && <small>Đang tắt</small>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
      {edit && <TableForm t={edit} areas={areas} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />}
    </>
  );
}

function TableForm({ t, areas, onClose, onSaved }: { t: DiningTable; areas: Area[]; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [d, setD] = useState(t);
  const [busy, setBusy] = useState(false);
  const isNew = !t.id;
  const [qrPath, setQrPath] = useState<string | null>(null);
  useEffect(() => { if (t.id) api<{ path: string }>(`/tables/${t.id}/qr`).then((r) => setQrPath(r.path)).catch(() => {}); }, [t.id]);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const body = { code: d.code, capacity: d.capacity, min_party: d.min_party, area_id: d.area_id, is_active: d.is_active };
      await (isNew ? send("POST", "/tables", body) : send("PUT", `/tables/${d.id}`, body));
      toast(isNew ? `Đã thêm bàn ${d.code}` : `Đã lưu bàn ${d.code}`);
      onSaved();
    } catch (err) { toast((err as Error).message, "err"); setBusy(false); }
  };
  const remove = async () => {
    if (!confirm(`Xóa bàn ${d.code}? Nếu bàn đã có lịch đặt, hãy tắt bàn thay vì xóa.`)) return;
    try { await send("DELETE", `/tables/${d.id}`); toast(`Đã xóa bàn ${d.code}`); onSaved(); }
    catch (err) { toast((err as Error).message, "err"); }
  };
  return (
    <Drawer title={isNew ? "Thêm bàn" : `Bàn ${t.code}`} onClose={onClose}>
      <form className="form" onSubmit={save}>
        <label className="field"><span>Mã bàn</span><input value={d.code} onChange={(e) => setD({ ...d, code: e.target.value })} placeholder="A01" required autoFocus /><small className="muted">Mã này được in trên mã QR đặt ở bàn.</small></label>
        <label className="field"><span>Khu vực</span>
          <select value={d.area_id ?? ""} onChange={(e) => setD({ ...d, area_id: e.target.value || null })}>
            <option value="">Chưa gán khu vực</option>
            {areas.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </label>
        <div className="two">
          <label className="field"><span>Sức chứa</span><input type="number" min={1} max={50} value={d.capacity} onChange={(e) => setD({ ...d, capacity: Number(e.target.value) })} required /></label>
          <label className="field"><span>Khách tối thiểu</span><input type="number" min={1} value={d.min_party} onChange={(e) => setD({ ...d, min_party: Number(e.target.value) })} required /></label>
        </div>
        <label className="check"><input type="checkbox" checked={!d.is_active} onChange={(e) => setD({ ...d, is_active: !e.target.checked })} /> Tắt bàn (không nhận đặt chỗ)</label>
        {qrPath && (
          <section className="qr-box">
            <h3>Mã QR đặt tại bàn {t.code}</h3>
            <div className="qr-print" id="qr-print"><QRCodeSVG value={`${window.location.origin}${qrPath}`} size={180} marginSize={2} title={`QR bàn ${t.code}`} /><b>Bàn {t.code}</b><span>Quét để gọi món</span></div>
            <p className="muted">Khách vãng lai quét mã này sau khi nhân viên mở bàn. Khách đặt trước không cần quét.</p>
            <button type="button" className="btn-ghost" onClick={() => window.print()}>In mã QR</button>
          </section>
        )}
        <footer className="form-foot">
          {!isNew && <button type="button" className="btn-danger" onClick={remove}>Xóa bàn</button>}
          <span className="grow" />
          <button type="button" className="btn-ghost" onClick={onClose}>Hủy</button>
          <button className="btn" disabled={busy}>{busy ? "Đang lưu" : "Lưu bàn"}</button>
        </footer>
      </form>
    </Drawer>
  );
}
