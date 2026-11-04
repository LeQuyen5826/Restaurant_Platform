"""Dữ liệu mẫu để dev: 1 nhà hàng, 4 tài khoản (mật khẩu: demo1234), khu vực, bàn, giờ mở cửa, thực đơn.

Chạy lại được nhiều lần: đặt lại mật khẩu tài khoản mẫu và chỉ thêm dữ liệu khi còn thiếu.
"""
import uuid

from sqlalchemy import text

from .db import SessionLocal
from .security import hash_password

DEMO_PASSWORD = "demo1234"
ACCOUNTS = [
    ("customer", "khach@demo.vn", "Khách Demo"),
    ("manager", "quanly@demo.vn", "Quản Lý Demo"),
    ("waiter", "phucvu@demo.vn", "Phục Vụ Demo"),
    ("kitchen", "bep@demo.vn", "Bếp Demo"),
]
# (danh mục, tên, mô tả, giá, cay, chay, dị ứng, ẩm thực)
MENU = [
    ("Khai vị", "Gỏi cuốn tôm thịt", "Tôm, thịt luộc, bún, rau thơm cuốn bánh tráng, chấm tương đậu phộng.", 59000, 0, False, ["crustacean", "peanut"], "Việt"),
    ("Khai vị", "Chả giò hải sản", "Cuốn giòn rụm nhân tôm, mực, miến, chấm nước mắm chua ngọt.", 69000, 0, False, ["crustacean", "mollusc", "gluten"], "Việt"),
    ("Khai vị", "Gỏi ngó sen chay", "Ngó sen, cà rốt, rau răm, đậu phộng rang.", 65000, 0, True, ["peanut"], "Việt"),
    ("Món chính", "Phở bò tái nạm", "Nước dùng hầm xương 12 giờ, bánh phở tươi, bò tái và nạm.", 75000, 0, False, ["gluten"], "Việt"),
    ("Món chính", "Bún chả Hà Nội", "Chả nướng than hoa, bún tươi, nước chấm, rau sống.", 85000, 0, False, ["fish", "gluten"], "Việt"),
    ("Món chính", "Cá kho tộ", "Cá lóc kho tộ với tiêu, hành, ăn kèm cơm trắng.", 129000, 1, False, ["fish"], "Việt"),
    ("Món chính", "Bò lúc lắc", "Thăn bò xào tỏi, ớt chuông, khoai tây chiên.", 149000, 1, False, ["soy"], "Việt"),
    ("Món chính", "Cà ri nấm chay", "Nấm các loại hầm nước cốt dừa, ăn với bánh mì.", 99000, 2, True, ["gluten"], "Thái"),
    ("Tráng miệng", "Chè ba màu", "Đậu đỏ, đậu xanh, thạch, nước cốt dừa.", 39000, 0, True, [], "Việt"),
    ("Tráng miệng", "Bánh flan cà phê", "Flan mềm, caramel, phin cà phê đậm.", 45000, 0, True, ["egg", "milk"], "Việt"),
    ("Đồ uống", "Cà phê sữa đá", "Phin truyền thống, sữa đặc.", 35000, 0, True, ["milk"], "Việt"),
    ("Đồ uống", "Trà đào cam sả", "Trà nóng ủ cùng đào, cam, sả.", 49000, 0, True, [], "Việt"),
]


def run() -> None:
    with SessionLocal() as db:
        rid = db.execute(text("SELECT id FROM restaurants ORDER BY created_at LIMIT 1")).scalar()
        if rid is None:
            rid = uuid.uuid4()
            db.execute(text("INSERT INTO restaurants (id, name, address, phone, deposit_amount) VALUES (:i, 'Quán Nhà Mình', '12 Phố Huế, Hà Nội', '0243 000 000', 100000)"), {"i": rid})
        db.execute(text(
            "UPDATE restaurants SET tagline = COALESCE(tagline, 'Món Việt nấu như ở nhà'), "
            "about = COALESCE(about, 'Quán Nhà Mình mở cửa từ năm 2019 với một mong muốn đơn giản: nấu những món Việt quen thuộc bằng nguyên liệu tươi mỗi ngày, "
            "trong không gian ấm cúng để cả gia đình ngồi lại bên nhau. Thực đơn đổi theo mùa, nước dùng được ninh từ sáng sớm và mọi món đều làm sau khi khách gọi.'), "
            "email = COALESCE(email, 'xinchao@quannhaminh.vn'), "
            "facebook_url = COALESCE(facebook_url, 'https://facebook.com/quannhaminh'), "
            "tiktok_url = COALESCE(tiktok_url, 'https://tiktok.com/@quannhaminh'), "
            "instagram_url = COALESCE(instagram_url, 'https://instagram.com/quannhaminh'), "
            "bank_code = COALESCE(bank_code, 'MB'), bank_account_number = COALESCE(bank_account_number, '0000000000'), "
            "bank_account_name = COALESCE(bank_account_name, 'QUAN NHA MINH') WHERE id = :r"), {"r": rid})
        if not db.execute(text("SELECT 1 FROM restaurant_services WHERE restaurant_id = :r"), {"r": rid}).first():
            for i, (t, d, ic) in enumerate([
                ("Đặt bàn trước", "Chọn khung giờ, giữ bàn, nhận mã QR để check-in khi đến.", "calendar"),
                ("Đặt bàn kèm món", "Chọn món trước để bếp chuẩn bị ngay khi bạn đến. Cần đặt cọc.", "restaurant"),
                ("Tiệc sinh nhật và sự kiện", "Trang trí, bánh kem, bàn dài cho nhóm đông. Ghi yêu cầu khi đặt bàn.", "gift"),
                ("Gọi món tại bàn qua QR", "Quét mã trên bàn, cả bàn cùng chọn món, bếp nhận phiếu ngay.", "qr"),
                ("Sân vườn thoáng mát", "Khu sân vườn có chỗ cho nhóm 6 đến 8 người.", "leaf"),
            ]):
                db.execute(text("INSERT INTO restaurant_services (restaurant_id, title, description, icon, sort_order) VALUES (:r, :t, :d, :c, :o)"),
                           {"r": rid, "t": t, "d": d, "c": ic, "o": i})
        pw = hash_password(DEMO_PASSWORD)
        for role, email, name in ACCOUNTS:
            r = None if role == "customer" else rid
            n = db.execute(
                text("UPDATE users SET password_hash = :p WHERE lower(email) = :e"), {"p": pw, "e": email}
            ).rowcount
            if n == 0:
                db.execute(
                    text("INSERT INTO users (restaurant_id, role, email, password_hash, full_name) "
                         "VALUES (:r, CAST(:role AS user_role), :e, :p, :n)"),
                    {"r": r, "role": role, "e": email, "p": pw, "n": name},
                )
        if not db.execute(text("SELECT 1 FROM areas WHERE restaurant_id = :r"), {"r": rid}).first():
            areas = {}
            for n in ("Tầng 1", "Sân vườn"):
                areas[n] = db.execute(text("INSERT INTO areas (restaurant_id, name) VALUES (:r, :n) RETURNING id"), {"r": rid, "n": n}).scalar()
            for code, cap, area in [("A01", 2, "Tầng 1"), ("A02", 2, "Tầng 1"), ("A03", 4, "Tầng 1"), ("A04", 4, "Tầng 1"),
                                    ("A05", 6, "Tầng 1"), ("B01", 4, "Sân vườn"), ("B02", 6, "Sân vườn"), ("B03", 8, "Sân vườn")]:
                db.execute(text("INSERT INTO dining_tables (restaurant_id, area_id, code, capacity) VALUES (:r, :a, :c, :cap)"),
                           {"r": rid, "a": areas[area], "c": code, "cap": cap})
        if not db.execute(text("SELECT 1 FROM service_windows WHERE restaurant_id = :r"), {"r": rid}).first():
            for d in range(1, 8):
                for o, c in (("10:30", "14:00"), ("17:00", "22:00")):
                    db.execute(text("INSERT INTO service_windows (restaurant_id, weekday, open_time, close_time) VALUES (:r, :d, :o, :c)"),
                               {"r": rid, "d": d, "o": o, "c": c})
        if not db.execute(text("SELECT 1 FROM dishes WHERE restaurant_id = :r"), {"r": rid}).first():
            cats = {}
            for i, (cat, *_rest) in enumerate(MENU):
                if cat not in cats:
                    cats[cat] = db.execute(
                        text("INSERT INTO menu_categories (restaurant_id, name, sort_order) VALUES (:r, :n, :s) RETURNING id"),
                        {"r": rid, "n": cat, "s": len(cats)},
                    ).scalar()
            for cat, name, desc, price, spicy, veg, allergens, cuisine in MENU:
                did = db.execute(
                    text("INSERT INTO dishes (restaurant_id, category_id, name, description, price_vnd, spiciness, is_vegetarian, cuisine) "
                         "VALUES (:r, :c, :n, :d, :p, :s, :v, :cu) RETURNING id"),
                    {"r": rid, "c": cats[cat], "n": name, "d": desc, "p": price, "s": spicy, "v": veg, "cu": cuisine},
                ).scalar()
                for a in allergens:
                    db.execute(text("INSERT INTO dish_allergens (dish_id, allergen_code) VALUES (:d, :a)"), {"d": did, "a": a})
        db.commit()
        print("Đã cập nhật dữ liệu mẫu")


if __name__ == "__main__":
    run()
