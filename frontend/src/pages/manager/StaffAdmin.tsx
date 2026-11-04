import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Drawer, useToast } from "../../components/ui";
import { api, send, type Role, type StaffRow } from "../../lib/api";
import { ROLE_LABEL } from "../../lib/auth";

export default function StaffAdmin() {
  const toast = useToast();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [open, setOpen] = useState(false);
  const load = useCallback(() => api<StaffRow[]>("/staff").then(setRows).catch((e) => toast(e.message, "err")), [toast]);
  useEffect(() => { load(); }, [load]);

  return (
    <>
      <header className="page-head">
        <div><h1>Nhân sự</h1><p className="muted">Tài khoản của quản lý, phục vụ và bếp</p></div>
        <div className="head-actions"><button className="btn" onClick={() => setOpen(true)}>Thêm nhân viên</button></div>
      </header>
      <div className="grid-table staff-grid" role="table" aria-label="Nhân sự">
        <div className="gt-head" role="row"><span>Họ tên</span><span>Email</span><span>Vai trò</span></div>
        {rows.map((r) => (
          <div className="gt-row" role="row" key={r.id}><b>{r.full_name}</b><span className="muted">{r.email}</span><span>{ROLE_LABEL[r.role]}</span></div>
        ))}
      </div>
      {open && <StaffForm onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load(); }} />}
    </>
  );
}

function StaffForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [d, setD] = useState({ full_name: "", email: "", password: "", role: "waiter" as Role });
  const save = async (e: FormEvent) => {
    e.preventDefault();
    try { await send("POST", "/staff", d); toast(`Đã tạo tài khoản cho ${d.full_name}`); onSaved(); }
    catch (err) { toast((err as Error).message, "err"); }
  };
  return (
    <Drawer title="Thêm nhân viên" onClose={onClose}>
      <form className="form" onSubmit={save}>
        <label className="field"><span>Họ tên</span><input value={d.full_name} onChange={(e) => setD({ ...d, full_name: e.target.value })} required autoFocus /></label>
        <label className="field"><span>Email đăng nhập</span><input type="email" value={d.email} onChange={(e) => setD({ ...d, email: e.target.value })} required /></label>
        <label className="field"><span>Mật khẩu ban đầu</span><input type="text" minLength={8} value={d.password} onChange={(e) => setD({ ...d, password: e.target.value })} required /><small className="muted">Tối thiểu 8 ký tự. Gửi cho nhân viên và nhờ họ đổi sau.</small></label>
        <label className="field"><span>Vai trò</span>
          <select value={d.role} onChange={(e) => setD({ ...d, role: e.target.value as Role })}>
            <option value="waiter">Phục vụ</option><option value="kitchen">Bếp</option><option value="manager">Quản lý</option>
          </select>
        </label>
        <footer className="form-foot"><span className="grow" /><button type="button" className="btn-ghost" onClick={onClose}>Hủy</button><button className="btn">Tạo tài khoản</button></footer>
      </form>
    </Drawer>
  );
}
