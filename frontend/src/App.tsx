import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactElement } from "react";
import PublicLayout from "./components/PublicLayout";
import Shell from "./components/Shell";
import type { Role } from "./lib/api";
import { HOME, useAuth } from "./lib/auth";
import Login from "./pages/Login";
import Book from "./pages/customer/Book";
import Dining from "./pages/customer/Dining";
import MyReservations from "./pages/customer/MyReservations";
import ReservationView from "./pages/customer/ReservationView";
import MenuAdmin from "./pages/manager/MenuAdmin";
import Overview from "./pages/manager/Overview";
import SettingsAdmin from "./pages/manager/SettingsAdmin";
import StaffAdmin from "./pages/manager/StaffAdmin";
import TablesAdmin from "./pages/manager/TablesAdmin";
import Contact from "./pages/public/Contact";
import Home from "./pages/public/Home";
import MenuPage from "./pages/public/MenuPage";
import Services from "./pages/public/Services";
import Checkin from "./pages/staff/Checkin";
import { KitchenStock, KitchenTickets } from "./pages/staff/Kitchen";
import ReadyItems from "./pages/staff/ReadyItems";
import TodayReservations from "./pages/staff/TodayReservations";
import WalkIn from "./pages/staff/WalkIn";
import Waiter from "./pages/staff/Waiter";

function Guard({ role, children }: { role: Role; children: ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="loading">Đang tải…</p>;
  if (!user) return <Navigate to="/dang-nhap" replace />;
  if (user.role !== role) return <Navigate to={HOME[user.role]} replace />;
  return <Shell role={role}>{children}</Shell>;
}

/** Khu vực khách: bắt buộc đăng nhập (đặt bàn, xem bàn trống, lượt đặt, gọi món sau check-in). */
function CustomerOnly({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <p className="loading">Đang tải…</p>;
  if (!user) return <Navigate to={`/dang-nhap?next=${encodeURIComponent(loc.pathname)}`} replace />;
  if (user.role !== "customer") return <Navigate to={HOME[user.role]} replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/dang-nhap" element={<Login />} />
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/mon-an" element={<MenuPage />} />
        <Route path="/dich-vu" element={<Services />} />
        <Route path="/lien-he" element={<Contact />} />
        <Route path="/dat-ban" element={<CustomerOnly><Book /></CustomerOnly>} />
        <Route path="/dat-ban/:id" element={<CustomerOnly><ReservationView /></CustomerOnly>} />
        <Route path="/lich-su" element={<CustomerOnly><MyReservations /></CustomerOnly>} />
        <Route path="/goi-mon" element={<CustomerOnly><Dining mode="mine" /></CustomerOnly>} />
        <Route path="/ban/:code" element={<Dining mode="table" />} />
      </Route>

      <Route path="/thuc-don" element={<Navigate to="/mon-an" replace />} />
      <Route path="/khach" element={<Navigate to="/" replace />} />
      <Route path="/quan-ly" element={<Navigate to="/quan-ly/tong-quan" replace />} />
      <Route path="/quan-ly/tong-quan" element={<Guard role="manager"><Overview /></Guard>} />
      <Route path="/quan-ly/dat-ban" element={<Guard role="manager"><TodayReservations /></Guard>} />
      <Route path="/quan-ly/thuc-don" element={<Guard role="manager"><MenuAdmin /></Guard>} />
      <Route path="/quan-ly/ban" element={<Guard role="manager"><TablesAdmin /></Guard>} />
      <Route path="/quan-ly/nhan-su" element={<Guard role="manager"><StaffAdmin /></Guard>} />
      <Route path="/quan-ly/cai-dat" element={<Guard role="manager"><SettingsAdmin /></Guard>} />
      <Route path="/phuc-vu" element={<Guard role="waiter"><Waiter /></Guard>} />
      <Route path="/phuc-vu/check-in" element={<Guard role="waiter"><Checkin /></Guard>} />
      <Route path="/phuc-vu/vang-lai" element={<Guard role="waiter"><WalkIn /></Guard>} />
      <Route path="/phuc-vu/mon-cho" element={<Guard role="waiter"><ReadyItems /></Guard>} />
      <Route path="/phuc-vu/dat-ban" element={<Guard role="waiter"><TodayReservations /></Guard>} />
      <Route path="/bep" element={<Guard role="kitchen"><KitchenTickets /></Guard>} />
      <Route path="/bep/het-mon" element={<Guard role="kitchen"><KitchenStock /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
