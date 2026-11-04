"""Đặt bàn: xem còn bàn theo khung giờ, đặt, hủy; nhân viên xem danh sách theo ngày.

Chống đặt trùng do ràng buộc EXCLUDE ở reservation_tables; ở đây chỉ chọn bàn và thử lại khi bị tranh.
"""
import math
import secrets
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import settings as cfg
from ...db import get_db
from ...deps import current_user, require_roles

router = APIRouter(tags=["booking"])
TZ = ZoneInfo(cfg.timezone)
customer_only = require_roles("customer")
front_staff = require_roles("manager", "waiter")
LIVE = ("pending_deposit", "confirmed", "seated")


def expire_holds(db: Session) -> None:
    """Hết hạn giữ chỗ: trigger trong DB tự nhả bàn khi trạng thái thành expired."""
    db.execute(text("UPDATE reservations SET status = 'expired' WHERE status = 'pending_deposit' AND expires_at < now()"))
    db.execute(text("UPDATE payments p SET status = 'expired' FROM reservations r "
                    "WHERE p.reservation_id = r.id AND p.status = 'pending' AND r.status = 'expired'"))
    db.commit()


CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ I, O, 0, 1 cho dễ đọc


def new_code(prefix: str, n: int) -> str:
    return prefix + "".join(secrets.choice(CODE_CHARS) for _ in range(n))


def default_restaurant(db: Session, rid: uuid.UUID | None):
    if rid:
        return rid
    r = db.execute(text("SELECT id FROM restaurants ORDER BY created_at LIMIT 1")).scalar()
    if not r:
        raise HTTPException(404, "Chưa có nhà hàng")
    return r


def compute_slots(db: Session, rid, day: date, party: int) -> list[dict]:
    s = db.execute(
        text("SELECT slot_minutes, dining_minutes, turn_buffer_minutes FROM restaurants WHERE id = :r"), {"r": rid}
    ).mappings().first()
    windows = db.execute(
        text("SELECT open_time, close_time FROM service_windows WHERE restaurant_id = :r AND weekday = :d ORDER BY open_time"),
        {"r": rid, "d": day.isoweekday()},
    ).all()
    tables = db.execute(
        text("SELECT id, code, capacity FROM dining_tables WHERE restaurant_id = :r AND is_active "
             "AND capacity >= :p AND min_party <= :p ORDER BY capacity, code"),
        {"r": rid, "p": party},
    ).mappings().all()
    day_lo = datetime.combine(day, time(0), TZ)
    day_hi = day_lo + timedelta(days=1, hours=4)
    busy = db.execute(
        text("SELECT rt.table_id, lower(rt.during) AS lo, upper(rt.during) AS hi FROM reservation_tables rt "
             "JOIN dining_tables t ON t.id = rt.table_id "
             "WHERE t.restaurant_id = :r AND rt.is_active AND rt.during && tstzrange(:a, :b)"),
        {"r": rid, "a": day_lo, "b": day_hi},
    ).all()
    # khách vãng lai đang ngồi (phiên mở, không gắn đặt bàn) cũng chiếm bàn
    hold = timedelta(minutes=s["dining_minutes"] + s["turn_buffer_minutes"])
    busy += [(r[0], r[1], r[1] + hold) for r in db.execute(
        text("SELECT table_id, opened_at FROM dining_sessions WHERE restaurant_id = :r AND status = 'open' "
             "AND reservation_id IS NULL"), {"r": rid})]
    now = datetime.now(TZ)
    out = []
    for w in windows:
        t = datetime.combine(day, w.open_time, TZ)
        limit = datetime.combine(day, w.close_time, TZ)
        while t + timedelta(minutes=s["dining_minutes"]) <= limit:
            if t > now:
                end = t + hold
                free = [x for x in tables if not any(b[0] == x["id"] and b[1] < end and b[2] > t for b in busy)]
                out.append({"time": t.strftime("%H:%M"), "starts_at": t, "free": free, "total": len(tables)})
            t += timedelta(minutes=s["slot_minutes"])
    return out


@router.get("/availability")
def availability(date_: date = Query(alias="date"), party: int = Query(2, ge=1, le=50),
                 restaurant_id: uuid.UUID | None = None, _: dict = Depends(current_user), db: Session = Depends(get_db)):
    """Số bàn còn trống theo từng khung giờ cho nhóm `party` người. Cần đăng nhập."""
    expire_holds(db)
    rid = default_restaurant(db, restaurant_id)
    today = datetime.now(TZ).date()
    if date_ < today or date_ > today + timedelta(days=60):
        raise HTTPException(422, "Chỉ đặt được từ hôm nay đến 60 ngày tới")
    slots = compute_slots(db, rid, date_, party)
    return {"date": date_.isoformat(), "party": party,
            "slots": [{"time": s["time"], "free_tables": len(s["free"]), "total_tables": s["total"]} for s in slots]}


class PreItem(BaseModel):
    dish_id: uuid.UUID
    quantity: int = Field(ge=1, le=99)
    note: str | None = Field(default=None, max_length=200)


class ReservationIn(BaseModel):
    date: date
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    party_size: int = Field(ge=1, le=50)
    note: str | None = Field(default=None, max_length=300)
    kind: str = Field(default="table_only", pattern="^(table_only|with_food)$")
    items: list[PreItem] = Field(default_factory=list, max_length=40)
    service_request: str | None = Field(default=None, max_length=500)


def _row_out(r) -> dict:
    d = dict(r)
    for k in ("id", "user_id"):
        if d.get(k):
            d[k] = str(d[k])
    for k in ("starts_at", "ends_at", "expires_at"):
        if d.get(k):
            d[k] = d[k].astimezone(TZ).isoformat()
    return d


RES_SELECT = """
SELECT r.id, r.party_size, r.starts_at, r.ends_at, r.status, r.expires_at, r.note,
       r.kind, r.service_request, r.checkin_code, r.deposit_amount,
       u.full_name AS customer_name, u.phone AS customer_phone, u.email AS customer_email,
       COALESCE(string_agg(t.code, ', ' ORDER BY t.code), '') AS tables
FROM reservations r
LEFT JOIN users u ON u.id = r.user_id
LEFT JOIN reservation_tables rt ON rt.reservation_id = r.id
LEFT JOIN dining_tables t ON t.id = rt.table_id
"""


def _preorder_lines(db: Session, rid, items: list[PreItem]) -> list[dict]:
    ids = {i.dish_id for i in items}
    if len(ids) != len(items):
        raise HTTPException(422, "Mỗi món chỉ xuất hiện một lần, hãy tăng số lượng")
    rows = {r["id"]: r for r in db.execute(
        text("SELECT id, name, price_vnd, is_available, is_active FROM dishes WHERE restaurant_id = :r AND id = ANY(:ids)"),
        {"r": rid, "ids": list(ids)}).mappings()}
    out, bad = [], []
    for i in items:
        d = rows.get(i.dish_id)
        if not d or not d["is_active"]:
            raise HTTPException(422, "Có món không tồn tại trong thực đơn")
        if not d["is_available"]:
            bad.append(d["name"])
        out.append({"dish_id": d["id"], "name": d["name"], "price": d["price_vnd"], "qty": i.quantity, "note": i.note or None})
    if bad:
        raise HTTPException(409, "Các món sau đang hết, hãy bỏ khỏi đơn: " + ", ".join(bad))
    return out


def deposit_for(total: int, st) -> int:
    """30% (cấu hình) giá trị món đặt trước, tối thiểu `deposit_amount`, không vượt quá tổng tiền món."""
    pct = math.ceil(total * st["deposit_percent"] / 100 / 1000) * 1000  # làm tròn lên nghìn đồng
    return min(max(pct, st["deposit_amount"]), total)


@router.post("/reservations", status_code=201)
def create_reservation(body: ReservationIn, user: dict = Depends(customer_only), db: Session = Depends(get_db)):
    expire_holds(db)
    rid = default_restaurant(db, None)
    st = db.execute(
        text("SELECT dining_minutes, turn_buffer_minutes, deposit_amount, deposit_percent, deposit_hold_minutes "
             "FROM restaurants WHERE id = :r"), {"r": rid},
    ).mappings().first()
    if body.kind == "with_food" and not body.items:
        raise HTTPException(422, "Đặt bàn kèm món cần chọn ít nhất một món")
    if body.kind == "table_only" and (body.items or body.service_request):
        raise HTTPException(422, "Đặt bàn thường không kèm món hay yêu cầu dịch vụ; hãy chọn loại đặt bàn kèm món")
    lines = _preorder_lines(db, rid, body.items) if body.kind == "with_food" else []
    total = sum(l["price"] * l["qty"] for l in lines)
    deposit = deposit_for(total, st) if body.kind == "with_food" else 0
    today = datetime.now(TZ).date()
    if body.date < today or body.date > today + timedelta(days=60):
        raise HTTPException(422, "Chỉ đặt được từ hôm nay đến 60 ngày tới")
    slot = next((s for s in compute_slots(db, rid, body.date, body.party_size) if s["time"] == body.time), None)
    if slot is None:
        raise HTTPException(422, "Khung giờ này không nhận đặt bàn (ngoài giờ mở cửa hoặc đã qua)")
    if not slot["free"]:
        raise HTTPException(409, "Khung giờ này đã hết bàn phù hợp, vui lòng chọn giờ khác")
    starts = slot["starts_at"]
    ends = starts + timedelta(minutes=st["dining_minutes"])
    during_hi = ends + timedelta(minutes=st["turn_buffer_minutes"])
    overlap = db.execute(
        text("SELECT 1 FROM reservations WHERE user_id = :u AND status IN ('pending_deposit','confirmed','seated') "
             "AND tstzrange(starts_at, ends_at) && tstzrange(:a, :b)"),
        {"u": user["id"], "a": starts, "b": ends},
    ).first()
    if overlap:
        raise HTTPException(409, "Bạn đã có một lượt đặt bàn trùng khung giờ này")
    need_deposit = deposit > 0
    status = "pending_deposit" if need_deposit else "confirmed"
    expires = datetime.now(TZ) + timedelta(minutes=st["deposit_hold_minutes"]) if need_deposit else None
    rev_id = None
    for table in slot["free"]:  # bàn nhỏ nhất đủ chỗ trước; bị tranh thì thử bàn kế tiếp
        try:
            with db.begin_nested():
                rev_id = db.execute(
                    text("INSERT INTO reservations (restaurant_id, user_id, party_size, starts_at, ends_at, status, expires_at, note, "
                         "kind, service_request, checkin_code, deposit_amount) "
                         "VALUES (:r, :u, :p, :a, :b, CAST(:st AS reservation_status), :e, :n, :k, :sr, :cc, :dep) RETURNING id"),
                    {"r": rid, "u": user["id"], "p": body.party_size, "a": starts, "b": ends, "st": status,
                     "e": expires, "n": (body.note or None), "k": body.kind, "sr": (body.service_request or "").strip() or None,
                     "cc": new_code("BK", 6), "dep": deposit},
                ).scalar_one()
                db.execute(
                    text("INSERT INTO reservation_tables (reservation_id, table_id, during) "
                         "VALUES (:i, :t, tstzrange(:a, :b))"),
                    {"i": rev_id, "t": table["id"], "a": starts, "b": during_hi},
                )
            break
        except IntegrityError as e:
            if getattr(e.orig, "sqlstate", None) != "23P01":
                db.rollback()
                raise
            rev_id = None
    if rev_id is None:
        db.rollback()
        raise HTTPException(409, "Khung giờ này vừa hết bàn, vui lòng chọn giờ khác")
    for l in lines:
        db.execute(
            text("INSERT INTO reservation_items (reservation_id, dish_id, dish_name, unit_price_vnd, quantity, note) "
                 "VALUES (:i, :d, :n, :p, :q, :note)"),
            {"i": rev_id, "d": l["dish_id"], "n": l["name"], "p": l["price"], "q": l["qty"], "note": l["note"]})
    if need_deposit:
        db.execute(
            text("INSERT INTO payments (restaurant_id, purpose, reservation_id, code, expected_amount, expires_at) "
                 "VALUES (:r, 'deposit', :i, :c, :a, :e)"),
            {"r": rid, "i": rev_id, "c": new_code("COC", 8), "a": deposit, "e": expires})
    db.commit()
    return _detail(db, rev_id)


def _detail(db: Session, rev_id) -> dict:
    row = db.execute(text(RES_SELECT + " WHERE r.id = :i GROUP BY r.id, u.id"), {"i": rev_id}).mappings().first()
    d = _row_out(row)
    items = db.execute(
        text("SELECT dish_id, dish_name AS name, unit_price_vnd AS price_vnd, quantity, note FROM reservation_items "
             "WHERE reservation_id = :i ORDER BY dish_name"), {"i": rev_id}).mappings().all()
    d["items"] = [{**dict(i), "dish_id": str(i["dish_id"])} for i in items]
    d["items_total"] = sum(i["price_vnd"] * i["quantity"] for i in items)
    pay = db.execute(
        text("SELECT p.code, p.expected_amount, p.status, p.expires_at, r.bank_code, r.bank_account_number, r.bank_account_name "
             "FROM payments p JOIN restaurants r ON r.id = p.restaurant_id "
             "WHERE p.reservation_id = :i AND p.purpose = 'deposit' ORDER BY p.created_at DESC LIMIT 1"), {"i": rev_id}).mappings().first()
    d["payment"] = None if not pay else {**dict(pay), "expires_at": pay["expires_at"].astimezone(TZ).isoformat()}
    return d


@router.get("/reservations/mine")
def my_reservations(user: dict = Depends(customer_only), db: Session = Depends(get_db)):
    expire_holds(db)
    rows = db.execute(text(RES_SELECT + " WHERE r.user_id = :u GROUP BY r.id, u.id ORDER BY r.starts_at DESC LIMIT 50"),
                      {"u": user["id"]}).mappings().all()
    return [_row_out(r) for r in rows]


@router.get("/reservations/{rid}")
def reservation_detail(rid: uuid.UUID, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    expire_holds(db)
    own = db.execute(text("SELECT user_id, restaurant_id FROM reservations WHERE id = :i"), {"i": rid}).mappings().first()
    if not own or (user["role"] == "customer" and own["user_id"] != user["id"]) or \
       (user["role"] != "customer" and own["restaurant_id"] != user["restaurant_id"]):
        raise HTTPException(404, "Không tìm thấy lượt đặt")
    return _detail(db, rid)


@router.post("/reservations/{rid}/cancel")
def cancel_reservation(rid: uuid.UUID, user: dict = Depends(require_roles("customer", "manager", "waiter")),
                       db: Session = Depends(get_db)):
    """Hủy lượt đặt. Với đặt bàn kèm món đã cọc: hủy trước `free_cancel_hours` giờ thì ghi nhận hoàn cọc, muộn hơn thì mất cọc."""
    cur = db.execute(
        text("SELECT r.status, r.starts_at, r.user_id, r.restaurant_id, r.deposit_amount, r.kind, s.free_cancel_hours "
             "FROM reservations r JOIN restaurants s ON s.id = r.restaurant_id WHERE r.id = :i FOR UPDATE OF r"), {"i": rid}).mappings().first()
    if not cur or (user["role"] == "customer" and cur["user_id"] != user["id"]) or \
       (user["role"] != "customer" and cur["restaurant_id"] != user["restaurant_id"]):
        raise HTTPException(404, "Không tìm thấy lượt đặt")
    if cur["status"] not in ("pending_deposit", "confirmed"):
        raise HTTPException(404, "Không tìm thấy lượt đặt hoặc lượt đặt không còn hủy được")
    staff = user["role"] != "customer"
    db.execute(text("UPDATE reservations SET status = 'cancelled', cancelled_at = now(), cancel_reason = :why WHERE id = :i"),
               {"i": rid, "why": "Nhân viên hủy" if staff else "Khách hủy"})
    result: dict = {"ok": True, "refund": 0, "forfeited": 0}
    pay = db.execute(text("SELECT id, status, paid_amount FROM payments WHERE reservation_id = :i AND purpose = 'deposit' "
                          "AND status IN ('pending', 'paid') FOR UPDATE"), {"i": rid}).mappings().first()
    if pay and pay["status"] == "pending":
        db.execute(text("UPDATE payments SET status = 'cancelled' WHERE id = :p"), {"p": pay["id"]})
    elif pay and pay["status"] == "paid":
        amount = pay["paid_amount"] or cur["deposit_amount"]
        early = cur["starts_at"] - datetime.now(TZ) >= timedelta(hours=cur["free_cancel_hours"])
        if early or staff:  # nhân viên hủy hộ thì coi như lỗi của nhà hàng, hoàn đủ
            db.execute(text("INSERT INTO refunds (payment_id, amount, reason, requested_by) VALUES (:p, :a, :why, :u)"),
                       {"p": pay["id"], "a": amount, "u": user["id"],
                        "why": "Hủy đặt bàn trước hạn" if not staff else "Nhà hàng hủy lượt đặt"})
            result["refund"] = amount
        else:
            result["forfeited"] = amount
    db.commit()
    return result


@router.post("/reservations/{rid}/confirm-deposit")
def confirm_deposit(rid: uuid.UUID, user: dict = Depends(require_roles("manager")), db: Session = Depends(get_db)):
    """Quản lý xác nhận đã nhận tiền cọc (dùng khi chưa nối SePay; webhook sau này sẽ gọi cùng hàm mark_deposit_paid)."""
    expire_holds(db)
    ok = mark_deposit_paid(db, rid, user["restaurant_id"])
    if not ok:
        raise HTTPException(409, "Lượt đặt không ở trạng thái chờ cọc (có thể đã hết hạn giữ chỗ)")
    return {"ok": True}


def mark_deposit_paid(db: Session, rid, restaurant_id, amount: int | None = None) -> bool:
    row = db.execute(
        text("UPDATE payments p SET status = 'paid', paid_at = now(), paid_amount = COALESCE(:a, p.expected_amount) "
             "FROM reservations r WHERE p.reservation_id = r.id AND r.id = :i AND r.restaurant_id = :r "
             "AND r.status = 'pending_deposit' AND p.status = 'pending' AND p.purpose = 'deposit' RETURNING p.id"),
        {"i": rid, "r": restaurant_id, "a": amount}).first()
    if not row:
        db.rollback()
        return False
    db.execute(text("UPDATE reservations SET status = 'confirmed', expires_at = NULL WHERE id = :i"), {"i": rid})
    db.commit()
    return True


@router.get("/reservations")
def day_reservations(date_: date = Query(alias="date"), user: dict = Depends(front_staff), db: Session = Depends(get_db)):
    expire_holds(db)
    lo = datetime.combine(date_, time(0), TZ)
    rows = db.execute(
        text(RES_SELECT + " WHERE r.restaurant_id = :r AND r.starts_at >= :a AND r.starts_at < :b "
             "GROUP BY r.id, u.id ORDER BY r.starts_at"),
        {"r": user["restaurant_id"], "a": lo, "b": lo + timedelta(days=1)},
    ).mappings().all()
    return [_row_out(r) for r in rows]


@router.post("/reservations/{rid}/no-show")
def no_show(rid: uuid.UUID, user: dict = Depends(front_staff), db: Session = Depends(get_db)):
    n = db.execute(
        text("UPDATE reservations r SET status = 'no_show' FROM restaurants s WHERE r.id = :i AND r.restaurant_id = :r "
             "AND s.id = r.restaurant_id AND r.status = 'confirmed' "
             "AND r.starts_at + make_interval(mins => s.late_grace_minutes) < now()"),
        {"i": rid, "r": user["restaurant_id"]},
    ).rowcount
    db.commit()
    if n == 0:
        raise HTTPException(409, "Chỉ đánh dấu vắng mặt được khi lượt đã xác nhận và khách trễ quá thời gian giữ bàn")
    return {"ok": True}
