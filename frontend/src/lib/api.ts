export type Role = "customer" | "manager" | "waiter" | "kitchen";
export interface User {
  id: string;
  role: Role;
  full_name: string;
  email: string | null;
  restaurant_id: string | null;
}
export interface Category { id: string; name: string; sort_order: number }
export interface Allergen { code: string; name: string }
export interface Dish {
  id: string; name: string; description: string | null; price_vnd: number; category_id: string | null;
  image_url: string | null; spiciness: number; is_vegetarian: boolean; cuisine: string | null;
  tags: string[]; ingredients: string[]; meal_periods: string[]; allergens: string[];
  is_available: boolean; is_active: boolean;
}
export interface Area { id: string; name: string }
export interface DiningTable { id: string; code: string; capacity: number; min_party: number; area_id: string | null; is_active: boolean }
export interface Settings {
  id?: string; name: string; address: string | null; phone: string | null;
  slot_minutes: number; dining_minutes: number; turn_buffer_minutes: number;
  deposit_amount: number; deposit_hold_minutes: number; free_cancel_hours: number;
  bank_code: string | null; bank_account_number: string | null; bank_account_name: string | null;
  deposit_percent: number; late_grace_minutes: number;
  tagline: string | null; about: string | null; email: string | null;
  facebook_url: string | null; tiktok_url: string | null; instagram_url: string | null;
  youtube_url: string | null; zalo_url: string | null; map_url: string | null;
}
export interface Shift { weekday: number; open_time: string; close_time: string }
export interface StaffRow { id: string; full_name: string; email: string; role: Role; is_active: boolean }

const KEY = "rb_token";
export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY);

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`/api${path}`, { ...init, headers: { ...headers, ...(init.headers as object) } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    let msg = `Lỗi ${res.status}`;
    if (typeof body.detail === "string") msg = body.detail;
    else if (Array.isArray(body.detail)) msg = "Dữ liệu chưa hợp lệ, hãy kiểm tra lại các ô đã nhập";
    throw new Error(msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const send = <T,>(method: string, path: string, body?: unknown) =>
  api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export const vnd = (n: number) => new Intl.NumberFormat("vi-VN").format(n) + "đ";

export const imgUrl = (u: string | null) => (u ? u : null);

/* ---------- ngày giờ ---------- */
export const pad = (n: number) => String(n).padStart(2, "0");
export const ymd = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const hm = (iso: string) => { const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
export const dmy = (iso: string) => { const d = new Date(iso); return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`; };
export const WEEKDAYS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
export const DAY_NAMES = ["Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Chủ nhật"];

/* ---------- đặt bàn ---------- */
export type ResStatus = "pending_deposit" | "confirmed" | "seated" | "completed" | "cancelled" | "expired" | "no_show";
export const RES_STATUS: Record<ResStatus, string> = {
  pending_deposit: "Chờ đặt cọc", confirmed: "Đã xác nhận", seated: "Đang dùng bữa", completed: "Đã hoàn tất",
  cancelled: "Đã hủy", expired: "Hết hạn giữ chỗ", no_show: "Vắng mặt",
};
export interface Reservation {
  id: string; party_size: number; starts_at: string; ends_at: string; status: ResStatus; expires_at: string | null;
  note: string | null; kind: "table_only" | "with_food"; service_request: string | null; checkin_code: string;
  deposit_amount: number; customer_name: string | null; customer_phone: string | null; tables: string;
}
export interface ResDetail extends Reservation {
  items: { dish_id: string; name: string; price_vnd: number; quantity: number; note: string | null }[];
  items_total: number;
  payment: null | { code: string; expected_amount: number; status: string; expires_at: string; bank_code: string | null; bank_account_number: string | null; bank_account_name: string | null };
}

/* ---------- trang công khai ---------- */
export interface PubDish {
  id: string; name: string; description: string | null; price_vnd: number; image_url: string | null; spiciness: number;
  is_vegetarian: boolean; is_available: boolean; allergens: Allergen[]; category?: string | null;
}
export interface PublicHome {
  restaurant: {
    name: string; tagline: string | null; about: string | null; address: string | null; phone: string | null; email: string | null;
    facebook_url: string | null; tiktok_url: string | null; instagram_url: string | null; youtube_url: string | null;
    zalo_url: string | null; map_url: string | null; deposit_amount: number; deposit_percent: number; free_cancel_hours: number;
  };
  services: { title: string; description: string | null; icon: string | null }[];
  hours: { weekday: number; shifts: string[] }[];
  featured: PubDish[];
}
export interface PubMenu { restaurant: { name: string }; sections: { id: string | null; name: string; dishes: PubDish[] }[] }

export async function upload<T>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  const t = getToken();
  const res = await fetch(`/api${path}`, { method: "POST", body: fd, headers: t ? { Authorization: `Bearer ${t}` } : {} });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Lỗi ${res.status}`);
  return body as T;
}
