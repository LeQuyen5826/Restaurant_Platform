import { useAuth } from "../lib/auth";

const TITLES = {
  customer: { title: "Khu vực khách hàng", todo: ["Đặt bàn theo khung giờ", "Đặt cọc VietQR", "Gợi ý món"] },
  manager: { title: "Khu vực quản lý", todo: ["Sơ đồ bàn & giờ mở cửa", "Thực đơn", "Nhân sự", "Báo cáo"] },
  waiter: { title: "Khu vực phục vụ", todo: ["Sơ đồ bàn", "Mở/đóng phiên bàn", "Xác nhận order"] },
  kitchen: { title: "Màn hình bếp", todo: ["Hàng đợi món", "Cập nhật trạng thái món"] },
} as const;

export default function RoleHome({ role }: { role: keyof typeof TITLES }) {
  const { user, logout } = useAuth();
  const t = TITLES[role];
  return (
    <main className="card">
      <header>
        <h1>{t.title}</h1>
        <button onClick={logout}>Đăng xuất</button>
      </header>
      <p>Xin chào, <b>{user?.full_name}</b></p>
      <p>Sẽ làm ở các tuần tiếp theo:</p>
      <ul>{t.todo.map((x) => <li key={x}>{x}</li>)}</ul>
    </main>
  );
}
