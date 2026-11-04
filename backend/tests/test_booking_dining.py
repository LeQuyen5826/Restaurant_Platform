import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import seed
from app.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
TOMORROW = (datetime.now(TZ) + timedelta(days=1)).date().isoformat()
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _cleanup():
    """Dọn dữ liệu do test tạo để chạy lại nhiều lần không làm hết bàn."""
    from sqlalchemy import text
    from app.db import SessionLocal
    with SessionLocal() as db:
        db.execute(text("UPDATE dining_sessions SET status = 'closed', closed_at = now() WHERE status = 'open'"))
        db.execute(text("UPDATE reservations SET status = 'cancelled', cancelled_at = now() "
                        "WHERE status IN ('pending_deposit', 'confirmed', 'seated') "
                        "AND user_id IN (SELECT id FROM users WHERE email LIKE '%@khach.vn')"))
        db.commit()


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed.run()
    _cleanup()
    yield
    _cleanup()


def H(email, pw="demo1234"):
    return {"Authorization": "Bearer " + client.post("/api/auth/login", json={"email": email, "password": pw}).json()["token"]}


def new_customer():
    mail = f"{uuid.uuid4().hex[:8]}@khach.vn"
    t = client.post("/api/auth/register", json={"full_name": "Khách Thử", "email": mail, "password": "matkhau123"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def free_at(time, party=2):
    r = client.get("/api/availability", params={"date": TOMORROW, "party": party}, headers=H("khach@demo.vn")).json()
    return next(s["free_tables"] for s in r["slots"] if s["time"] == time)


def book(h, time="18:00", party=2, date=TOMORROW):
    return client.post("/api/reservations", headers=h, json={"date": date, "time": time, "party_size": party})


def test_availability_needs_login_and_validates():
    assert client.get("/api/availability", params={"date": TOMORROW, "party": 2}).status_code == 401
    kh = H("khach@demo.vn")
    r = client.get("/api/availability", params={"date": TOMORROW, "party": 2}, headers=kh)
    assert r.status_code == 200
    times = [s["time"] for s in r.json()["slots"]]
    assert "17:00" in times and "10:30" in times
    assert "14:00" not in times  # bữa 90 phút phải kết thúc trước giờ đóng cửa 14:00 (ca trưa: tối đa 12:30)
    assert client.get("/api/availability", params={"date": "2020-01-01", "party": 2}, headers=kh).status_code == 422
    assert client.get("/api/availability", params={"date": TOMORROW, "party": 0}, headers=kh).status_code == 422


def test_booking_reduces_free_tables_and_cancel_restores():
    h = new_customer()
    before = free_at("18:00")
    r = book(h)
    assert r.status_code == 201, r.text
    res = r.json()
    assert res["status"] == "confirmed" and res["tables"]
    assert free_at("18:00") == before - 1
    assert free_at("19:00") == before - 1 or free_at("19:00") < before  # bữa 90' + dọn 15' còn chồng sang 19:00
    assert free_at("20:00") >= free_at("19:00")
    assert any(x["id"] == res["id"] for x in client.get("/api/reservations/mine", headers=h).json())
    assert client.post(f"/api/reservations/{res['id']}/cancel", headers=h).status_code == 200
    assert free_at("18:00") == before
    assert client.post(f"/api/reservations/{res['id']}/cancel", headers=h).status_code == 404


def test_same_user_cannot_double_book_overlapping():
    h = new_customer()
    assert book(h, "18:00").status_code == 201
    assert book(h, "18:30").status_code == 409


def test_invalid_slots_and_roles():
    h = new_customer()
    assert book(h, "03:00").status_code == 422
    assert book(h, "18:00", date="2020-01-01").status_code == 422
    assert book(h, "18:00", party=60).status_code == 422
    assert client.post("/api/reservations", json={"date": TOMORROW, "time": "18:00", "party_size": 2}).status_code == 401
    assert book(H("phucvu@demo.vn")).status_code == 403


def test_full_table_blocks_second_booking():
    a, b = new_customer(), new_customer()
    first = book(a, "20:00", party=8)  # chỉ bàn 8 chỗ B03 vừa
    assert first.status_code == 201
    assert book(b, "20:00", party=8).status_code == 409
    assert free_at("20:00", party=8) == 0
    client.post(f"/api/reservations/{first.json()['id']}/cancel", headers=a)
    assert book(b, "20:00", party=8).status_code == 201


def test_staff_sees_day_list():
    h = new_customer()
    r = book(h, "10:30").json()
    rows = client.get("/api/reservations", params={"date": TOMORROW}, headers=H("phucvu@demo.vn")).json()
    assert any(x["id"] == r["id"] and x["customer_name"] == "Khách Thử" for x in rows)
    assert client.get("/api/reservations", params={"date": TOMORROW}, headers=H("bep@demo.vn")).status_code == 403
    assert client.get("/api/reservations", params={"date": TOMORROW}, headers=h).status_code == 403


def book_food(h, time="12:00", party=2, items=None, note="Sinh nhật mẹ"):
    items = items if items is not None else [{"dish_id": dish_id("Phở bò tái nạm"), "quantity": 2}]
    return client.post("/api/reservations", headers=h, json={"date": TOMORROW, "time": time, "party_size": party,
                                                            "kind": "with_food", "items": items, "service_request": note})


def test_with_food_needs_items_and_table_only_rejects_them():
    h = new_customer()
    assert client.post("/api/reservations", headers=h, json={"date": TOMORROW, "time": "12:00", "party_size": 2, "kind": "with_food"}).status_code == 422
    r = client.post("/api/reservations", headers=h, json={"date": TOMORROW, "time": "12:00", "party_size": 2, "service_request": "x"})
    assert r.status_code == 422
    dup = [{"dish_id": dish_id(), "quantity": 1}, {"dish_id": dish_id(), "quantity": 1}]
    assert book_food(h, items=dup).status_code == 422


def test_with_food_deposit_hold_expires():
    h = new_customer()
    r = book_food(h)
    assert r.status_code == 201, r.text
    r = r.json()
    price = next(d["price_vnd"] for d in client.get("/api/menu/dishes", headers=H("quanly@demo.vn")).json() if d["name"] == "Phở bò tái nạm")
    assert r["status"] == "pending_deposit" and r["expires_at"] and r["kind"] == "with_food"
    assert r["deposit_amount"] == min(max(-(-price * 2 * 30 // 100 // 1000) * 1000, 100000), price * 2)
    assert r["payment"]["status"] == "pending" and r["payment"]["expected_amount"] == r["deposit_amount"] and r["checkin_code"].startswith("BK")
    assert r["items"][0]["quantity"] == 2 and r["service_request"] == "Sinh nhật mẹ"
    from sqlalchemy import text
    from app.db import SessionLocal
    with SessionLocal() as db:
        db.execute(text("UPDATE reservations SET expires_at = now() - interval '1 minute' WHERE id = :i"), {"i": r["id"]})
        db.commit()
    mine = client.get("/api/reservations/mine", headers=h).json()
    assert next(x for x in mine if x["id"] == r["id"])["status"] == "expired"
    assert client.get(f"/api/reservations/{r['id']}", headers=h).json()["payment"]["status"] == "expired"
    assert client.post(f"/api/reservations/{r['id']}/confirm-deposit", headers=H("quanly@demo.vn")).status_code == 409
    assert book(h, "12:00").status_code == 201  # bàn đã nhả


def test_deposit_confirm_checkin_sends_preorder_to_kitchen_and_refund_rules():
    m, w, k = H("quanly@demo.vn"), H("phucvu@demo.vn"), H("bep@demo.vn")
    h = new_customer()
    r = book_food(h, "12:00").json()
    assert client.post(f"/api/reservations/{r['id']}/confirm-deposit", headers=w).status_code == 403
    assert client.post("/api/floor/checkin", headers=w, json={"code": r["checkin_code"]}).status_code == 409  # chưa cọc
    assert client.post(f"/api/reservations/{r['id']}/confirm-deposit", headers=m).status_code == 200
    assert client.get(f"/api/reservations/{r['id']}", headers=h).json()["status"] == "confirmed"
    assert client.get(f"/api/reservations/{r['id']}", headers=new_customer()).status_code == 404
    # ngày mai 12:00: chưa tới giờ check-in
    assert client.post("/api/floor/checkin", headers=w, json={"code": r["checkin_code"]}).status_code == 409
    # đưa giờ hẹn về hiện tại để check-in được
    from sqlalchemy import text
    from app.db import SessionLocal
    with SessionLocal() as db:
        db.execute(text("UPDATE reservations SET starts_at = now(), ends_at = now() + interval '90 minutes' WHERE id = :i"), {"i": r["id"]})
        db.commit()
    assert client.get("/api/dining/mine", headers=h).json() == {"active": False}
    c = client.post("/api/floor/checkin", headers=w, json={"code": r["checkin_code"].lower()})
    assert c.status_code == 200, c.text
    assert c.json()["pre_ordered_items"] == 1 and c.json()["service_request"] == "Sinh nhật mẹ"
    assert client.post("/api/floor/checkin", headers=w, json={"code": r["checkin_code"]}).status_code == 409  # đã check-in
    tk = [x for x in client.get("/api/kitchen/items", headers=k).json() if x["table_code"] == c.json()["table_code"]]
    assert len(tk) == 1 and tk[0]["quantity"] == 2 and tk[0]["note"].startswith("Đặt trước")
    # khách vào bàn bằng tài khoản, không cần quét QR bàn
    mine = client.get("/api/dining/mine", headers=h).json()
    assert mine["active"] and mine["table_label"] == c.json()["table_code"]
    tok = client.post("/api/dining/mine/join", headers=h).json()["token"]
    st = client.get("/api/dining/state", headers={"X-Guest-Token": tok}).json()
    assert st["items"][0]["quantity"] == 2 and st["my_name"] == "Khách Thử"
    again = client.post("/api/dining/mine/join", headers=h).json()
    assert len(client.get("/api/dining/state", headers={"X-Guest-Token": again["token"]}).json()["guests"]) == 1
    # hóa đơn trừ cọc
    sid = c.json()["session_id"]
    d = client.get(f"/api/floor/sessions/{sid}", headers=w).json()
    assert d["deposit_paid"] == r["deposit_amount"] and d["amount_due"] == max(d["total"] - r["deposit_amount"], 0)
    client.post(f"/api/floor/sessions/{sid}/close", headers=w)

    # hoàn cọc: hủy sớm -> hoàn; hủy muộn -> mất
    e = new_customer()
    early = book_food(e, "17:00").json()
    client.post(f"/api/reservations/{early['id']}/confirm-deposit", headers=m)
    res = client.post(f"/api/reservations/{early['id']}/cancel", headers=e).json()
    assert res["refund"] == early["deposit_amount"] and res["forfeited"] == 0
    late = book_food(e, "18:00").json()
    client.post(f"/api/reservations/{late['id']}/confirm-deposit", headers=m)
    with SessionLocal() as db:
        db.execute(text("UPDATE reservations SET starts_at = now() + interval '30 minutes', ends_at = now() + interval '2 hours' WHERE id = :i"), {"i": late["id"]})
        db.commit()
    res = client.post(f"/api/reservations/{late['id']}/cancel", headers=e).json()
    assert res["forfeited"] == late["deposit_amount"] and res["refund"] == 0
    pend = book_food(e, "19:00").json()  # hủy khi chưa cọc: hủy luôn phiếu thanh toán
    assert client.post(f"/api/reservations/{pend['id']}/cancel", headers=e).json()["refund"] == 0
    assert client.get(f"/api/reservations/{pend['id']}", headers=e).json()["payment"]["status"] == "cancelled"


def test_walk_in_options_and_no_show_grace():
    w = H("phucvu@demo.vn")
    opts = client.get("/api/floor/walk-in", params={"party": 5}, headers=w).json()
    assert opts and all(o["capacity"] >= 5 for o in opts) and opts == sorted(opts, key=lambda o: (o["capacity"], o["code"]))
    assert client.get("/api/floor/walk-in", params={"party": 2}, headers=H("khach@demo.vn")).status_code == 403
    r = book(new_customer(), "12:00").json()
    from sqlalchemy import text
    from app.db import SessionLocal
    with SessionLocal() as db:
        db.execute(text("UPDATE reservations SET starts_at = now() - interval '5 minutes', ends_at = now() + interval '85 minutes' WHERE id = :i"), {"i": r["id"]})
        db.commit()
    assert client.post(f"/api/reservations/{r['id']}/no-show", headers=w).status_code == 409  # còn trong 15 phút giữ bàn
    with SessionLocal() as db:
        db.execute(text("UPDATE reservations SET starts_at = now() - interval '20 minutes' WHERE id = :i"), {"i": r["id"]})
        db.commit()
    assert client.post(f"/api/reservations/{r['id']}/no-show", headers=w).status_code == 200


# ------------------------------------------------------------------ luồng gọi món
def make_table():
    m = H("quanly@demo.vn")
    code = "Q" + uuid.uuid4().hex[:5]
    t = client.post("/api/tables", headers=m, json={"code": code, "capacity": 4}).json()
    return t["id"], code


def dish_id(name="Phở bò tái nạm"):
    m = H("quanly@demo.vn")
    return next(d["id"] for d in client.get("/api/menu/dishes", headers=m).json() if d["name"] == name)


def test_full_dining_flow():
    w, k = H("phucvu@demo.vn"), H("bep@demo.vn")
    tid, code = make_table()
    qr = client.get(f"/api/tables/{tid}/qr", headers=w).json()["path"].replace("/ban/", "")
    assert client.get("/api/dining/table/" + qr).json()["session_open"] is False
    assert client.post(f"/api/dining/table/{qr}/join", json={}).status_code == 409  # bàn chưa mở
    bad = qr[:-1] + ("0" if qr[-1] != "0" else "1")
    assert client.get("/api/dining/table/" + bad).status_code == 404

    sid = client.post("/api/floor/sessions", headers=w, json={"table_id": tid}).json()["session_id"]
    assert client.post("/api/floor/sessions", headers=w, json={"table_id": tid}).status_code == 409
    j = client.post(f"/api/dining/table/{qr}/join", json={"name": "Lan"}).json()
    g = {"X-Guest-Token": j["token"]}
    j2 = client.post(f"/api/dining/table/{qr}/join", json={}).json()
    g2 = {"X-Guest-Token": j2["token"]}
    assert j2["name"] == "Khách 2"

    pho = dish_id()
    assert client.put("/api/dining/cart", headers=g, json={"dish_id": pho, "quantity": 2}).status_code == 200
    assert client.put("/api/dining/cart", headers=g2, json={"dish_id": dish_id("Cà phê sữa đá"), "quantity": 1, "note": "ít đá"}).status_code == 200
    st = client.get("/api/dining/state", headers=g).json()
    assert len(st["cart"]) == 2 and st["cart_total"] == 2 * 75000 + 35000 and len(st["guests"]) == 2

    o = client.post("/api/dining/orders", headers=g)
    assert o.status_code == 201 and o.json()["items"] == 2
    assert client.post("/api/dining/orders", headers=g).status_code == 422  # giỏ đã trống

    ki = [x for x in client.get("/api/kitchen/items", headers=k).json() if x["table_code"] == code]
    assert {x["name"] for x in ki} == {"Phở bò tái nạm", "Cà phê sữa đá"} and all(x["status"] == "new" for x in ki)
    assert next(x for x in ki if x["name"] == "Cà phê sữa đá")["note"] == "ít đá"
    a, b = ki[0]["id"], ki[1]["id"]

    # khách hủy được món mới; món đã vào bếp làm thì không
    assert client.patch(f"/api/kitchen/items/{a}", headers=k, json={"status": "preparing"}).status_code == 200
    assert client.post(f"/api/dining/items/{a}/cancel", headers=g).status_code == 409
    assert client.post(f"/api/dining/items/{b}/cancel", headers=g).status_code == 200

    assert client.patch(f"/api/kitchen/items/{a}", headers=k, json={"status": "ready"}).status_code == 200
    ready = client.get("/api/floor/ready", headers=w).json()
    assert [x["table_code"] for x in ready if x["id"] == a] == [code]
    assert client.patch(f"/api/kitchen/items/{a}", headers=w, json={"status": "ready"}).status_code == 403
    assert client.post(f"/api/floor/items/{a}/served", headers=k).status_code == 403
    assert client.post(f"/api/floor/items/{a}/served", headers=w).status_code == 200
    assert client.post(f"/api/floor/items/{a}/served", headers=w).status_code == 409

    st = client.get("/api/dining/state", headers=g2).json()
    assert {i["status"] for i in st["items"]} == {"served", "cancelled"} and st["ordered_total"] == 2 * 75000
    fl = next(t for t in client.get("/api/floor", headers=w).json() if t["id"] == tid)
    assert fl["state"] == "occupied" and fl["session"]["guests"] == 2
    d = client.get(f"/api/floor/sessions/{sid}", headers=w).json()
    assert d["total"] == 150000 and len(d["items"]) == 2

    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + j["token"]}).status_code == 401  # token khách không dùng làm token nhân viên
    assert client.post(f"/api/floor/sessions/{sid}/close", headers=w).status_code == 200
    assert client.get("/api/dining/state", headers=g).status_code == 401  # bàn đóng, token vô hiệu
    assert client.post(f"/api/floor/sessions/{sid}/close", headers=w).status_code == 404


def test_cart_rejects_out_of_stock_and_bad_requests():
    w, m = H("phucvu@demo.vn"), H("quanly@demo.vn")
    tid, code = make_table()
    qr = client.get(f"/api/tables/{tid}/qr", headers=w).json()["path"].replace("/ban/", "")
    sid = client.post("/api/floor/sessions", headers=w, json={"table_id": tid}).json()["session_id"]
    g = {"X-Guest-Token": client.post(f"/api/dining/table/{qr}/join", json={}).json()["token"]}
    chè = dish_id("Chè ba màu")
    client.patch(f"/api/menu/dishes/{chè}/availability", headers=m, json={"is_available": False})
    try:
        assert client.put("/api/dining/cart", headers=g, json={"dish_id": chè, "quantity": 1}).status_code == 409
    finally:
        client.patch(f"/api/menu/dishes/{chè}/availability", headers=m, json={"is_available": True})
    assert client.put("/api/dining/cart", headers=g, json={"dish_id": str(uuid.uuid4()), "quantity": 1}).status_code == 404
    assert client.put("/api/dining/cart", headers=g, json={"dish_id": chè, "quantity": 100}).status_code == 422
    assert client.get("/api/dining/state").status_code == 401
    assert client.get("/api/dining/state", headers={"X-Guest-Token": "abc"}).status_code == 401
    # món vào giỏ rồi hết hàng: gửi bị chặn
    client.put("/api/dining/cart", headers=g, json={"dish_id": chè, "quantity": 1})
    client.patch(f"/api/menu/dishes/{chè}/availability", headers=m, json={"is_available": False})
    try:
        assert client.post("/api/dining/orders", headers=g).status_code == 409
    finally:
        client.patch(f"/api/menu/dishes/{chè}/availability", headers=m, json={"is_available": True})
    client.post(f"/api/floor/sessions/{sid}/close", headers=w)


def test_session_from_reservation_seats_and_completes():
    w = H("phucvu@demo.vn")
    h = new_customer()
    r = book(h, "19:00", party=2).json()
    tid, _ = make_table()
    sid = client.post("/api/floor/sessions", headers=w, json={"table_id": tid, "reservation_id": r["id"]}).json()["session_id"]
    mine = lambda: next(x for x in client.get("/api/reservations/mine", headers=h).json() if x["id"] == r["id"])["status"]
    assert mine() == "seated"
    assert client.post("/api/floor/sessions", headers=w, json={"table_id": make_table()[0], "reservation_id": r["id"]}).status_code == 409
    client.post(f"/api/floor/sessions/{sid}/close", headers=w)
    assert mine() == "completed"


def test_walk_in_session_blocks_availability_today_and_pending_cannot_be_seated():
    w = H("phucvu@demo.vn")
    tid, _ = make_table()
    r = book_food(new_customer(), "20:00").json()
    assert r["status"] == "pending_deposit"
    assert client.post("/api/floor/sessions", headers=w, json={"table_id": tid, "reservation_id": r["id"]}).status_code == 409


def test_overview_and_home():
    o = client.get("/api/overview", headers=H("quanly@demo.vn")).json()
    assert o["tables"] >= 8 and o["dishes"] >= 12 and isinstance(o["upcoming"], list) and "today_shifts" in o
    assert client.get("/api/overview", headers=H("phucvu@demo.vn")).status_code == 403
    h = client.get("/api/public/home").json()
    assert h["restaurant"]["name"] and len(h["hours"]) == 7 and len(h["featured"]) >= 1
    assert h["restaurant"]["facebook_url"] and h["restaurant"]["about"] and len(h["services"]) >= 3


def test_dish_image_upload_rules():
    m = H("quanly@demo.vn")
    did = dish_id("Chè ba màu")
    assert client.post(f"/api/menu/dishes/{did}/image", headers=H("bep@demo.vn"), files={"file": ("a.png", PNG, "image/png")}).status_code == 403
    assert client.post(f"/api/menu/dishes/{did}/image", headers=m, files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 422
    assert client.post(f"/api/menu/dishes/{did}/image", headers=m, files={"file": ("a.png", PNG + b"0" * 3_200_000, "image/png")}).status_code == 413
    r = client.post(f"/api/menu/dishes/{did}/image", headers=m, files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["image_url"].startswith("/api/uploads/dishes/")
    assert client.get(r.json()["image_url"]).status_code == 200
    assert client.delete(f"/api/menu/dishes/{did}/image", headers=m).json()["image_url"] is None
    assert client.get(r.json()["image_url"]).status_code == 404
