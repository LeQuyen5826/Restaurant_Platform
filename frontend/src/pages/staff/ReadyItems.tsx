import { useCallback, useState } from "react";
import { Empty, useToast } from "../../components/ui";
import { usePoll } from "../../hooks/usePoll";
import { api, send } from "../../lib/api";

interface Ready { id: string; name: string; quantity: number; note: string | null; status_changed_at: string; table_code: string }
const mins = (iso: string) => Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));

export default function ReadyItems() {
  const toast = useToast();
  const [rows, setRows] = useState<Ready[] | null>(null);
  const load = useCallback(async () => setRows(await api<Ready[]>("/floor/ready")), []);
  usePoll(() => load().catch(() => {}), 3000);
  const served = async (x: Ready) => {
    try { await send("POST", `/floor/items/${x.id}/served`); toast(`Đã mang ${x.name} ra bàn ${x.table_code}`); load(); }
    catch (e) { toast((e as Error).message, "err"); load(); }
  };
  return (
    <>
      <header className="page-head"><div><h1>Món chờ mang ra</h1><p className="muted">Bếp đã làm xong. Tự cập nhật mỗi 3 giây.</p></div></header>
      {rows && rows.length === 0 && <Empty title="Chưa có món nào chờ" hint="Khi bếp bấm xong, món hiện ở đây kèm số bàn." />}
      <ul className="ready">
        {rows?.map((x) => (
          <li key={x.id}>
            <div className="ready-table"><small>Bàn</small><b>{x.table_code}</b></div>
            <div className="grow"><b className="ready-name">{x.quantity} × {x.name}</b>{x.note && <p className="muted">Ghi chú: {x.note}</p>}<p className={mins(x.status_changed_at) >= 5 ? "late" : "muted"}>Xong {mins(x.status_changed_at)} phút trước</p></div>
            <button className="btn" onClick={() => served(x)}>Đã mang ra</button>
          </li>
        ))}
      </ul>
    </>
  );
}
