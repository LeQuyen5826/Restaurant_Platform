import { useCallback, useMemo, useState } from "react";
import { Empty, Switch, useToast } from "../../components/ui";
import { usePoll } from "../../hooks/usePoll";
import { api, send, type Dish } from "../../lib/api";

interface Item { id: string; name: string; quantity: number; note: string | null; status: "new" | "preparing" | "ready"; created_at: string; table_code: string; guest_name: string | null }
const mins = (iso: string) => Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
const REASONS = ["Hết nguyên liệu", "Khách đổi ý", "Gọi nhầm món", "Lý do khác"];

export function KitchenTickets() {
  const toast = useToast();
  const [items, setItems] = useState<Item[] | null>(null);
  const [filter, setFilter] = useState<"all" | "new" | "preparing" | "ready">("all");
  const [cancelling, setCancelling] = useState<Item | null>(null);
  const load = useCallback(async () => setItems(await api<Item[]>("/kitchen/items")), []);
  usePoll(() => load().catch(() => {}), 3000);
  const set = async (x: Item, status: string, reason?: string) => {
    try { await send("PATCH", `/kitchen/items/${x.id}`, { status, reason }); setCancelling(null); await load(); }
    catch (e) { toast((e as Error).message, "err"); load(); }
  };
  const groups = useMemo(() => {
    const m = new Map<string, Item[]>();
    (items ?? []).filter((i) => filter === "all" || i.status === filter).forEach((i) => m.set(i.table_code, [...(m.get(i.table_code) ?? []), i]));
    return [...m.entries()].sort((a, b) => a[1][0].created_at.localeCompare(b[1][0].created_at));
  }, [items, filter]);
  const count = (s: string) => (items ?? []).filter((i) => i.status === s).length;
  return (
    <>
      <header className="page-head"><div><h1>Phiếu bếp</h1><p className="muted">Tự cập nhật mỗi 3 giây. Bấm Xong thì phục vụ thấy ngay món và số bàn.</p></div>
        <div className="seg" role="group" aria-label="Lọc phiếu">
          {([["all", "Tất cả"], ["new", `Mới (${count("new")})`], ["preparing", `Đang làm (${count("preparing")})`], ["ready", `Xong (${count("ready")})`]] as const).map(([k, l]) => <button key={k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>{l}</button>)}
        </div>
      </header>
      {items && groups.length === 0 && <Empty title="Không có phiếu nào" hint="Món khách gửi sẽ hiện ở đây kèm số bàn." />}
      <div className="tickets">
        {groups.map(([code, list]) => {
          const old = mins(list[0].created_at) >= 15 && list.some((i) => i.status !== "ready");
          return (
            <section key={code} className={`ticket-card ${old ? "old" : ""}`}>
              <header><b className="tk-table">Bàn {code}</b><span className={old ? "late" : "muted"}>{mins(list[0].created_at)} phút</span></header>
              <ul>
                {list.map((i) => (
                  <li key={i.id}>
                    <div className="tk-line"><b>{i.quantity} × {i.name}</b><span className={`badge badge-${i.status === "ready" ? "good" : i.status === "new" ? "warn" : "dim"}`}>{i.status === "new" ? "Mới" : i.status === "preparing" ? "Đang làm" : "Xong"}</span></div>
                    {i.note && <p className="tk-note">{i.note}</p>}
                    {i.guest_name && <p className="muted">{i.guest_name}</p>}
                    <div className="tk-act">
                      {i.status === "new" && <button className="btn-ghost" onClick={() => set(i, "preparing")}>Bắt đầu làm</button>}
                      {i.status !== "ready" && <button className="btn" onClick={() => set(i, "ready")}>Xong</button>}
                      {i.status === "ready" && <button className="btn-quiet" onClick={() => set(i, "preparing")}>Hoàn tác</button>}
                      {i.status !== "ready" && <button className="btn-quiet" onClick={() => setCancelling(i)}>Hủy món</button>}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
      {cancelling && (
        <div className="scrim center" onMouseDown={(e) => e.target === e.currentTarget && setCancelling(null)}>
          <div className="dialog" role="dialog" aria-label="Hủy món">
            <h2>Hủy {cancelling.name}?</h2>
            <p className="muted" style={{ margin: "4px 0 14px" }}>Bàn {cancelling.table_code}. Chọn lý do để khách và phục vụ biết.</p>
            <div className="reasons">{REASONS.map((r) => <button key={r} className="btn-ghost" onClick={() => set(cancelling, "cancelled", r)}>{r}</button>)}</div>
            <button className="btn-quiet" onClick={() => setCancelling(null)}>Không hủy</button>
          </div>
        </div>
      )}
    </>
  );
}

export function KitchenStock() {
  const toast = useToast();
  const [dishes, setDishes] = useState<Dish[]>([]);
  const load = useCallback(() => api<Dish[]>("/menu/dishes").then(setDishes).catch((e) => toast(e.message, "err")), [toast]);
  usePoll(load, 10000);
  const flip = async (d: Dish, v: boolean) => {
    try { await send("PATCH", `/menu/dishes/${d.id}/availability`, { is_available: v }); toast(v ? `${d.name} đã còn món` : `${d.name} đã hết món`); load(); }
    catch (e) { toast((e as Error).message, "err"); }
  };
  const active = dishes.filter((d) => d.is_active);
  const out = active.filter((d) => !d.is_available).length;
  return (
    <>
      <header className="page-head"><div><h1>Còn / hết món</h1><p className="muted">{out === 0 ? "Tất cả món đang còn" : `${out} món đang hết`}. Món hết sẽ không cho khách chọn.</p></div></header>
      {active.length === 0 ? <Empty title="Thực đơn đang trống" hint="Nhờ quản lý thêm món." /> : (
        <ul className="kitchen-list">
          {active.map((d) => (
            <li key={d.id} className={d.is_available ? "" : "out"}>
              <span>{d.name}</span>
              <span className="muted">{d.is_available ? "Còn món" : "Hết món"}</span>
              <Switch on={d.is_available} onChange={(v) => flip(d, v)} label={`${d.name} còn món`} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
