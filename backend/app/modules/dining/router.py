"""Phiên bàn, gọi món qua QR, màn hình bếp, sơ đồ tầng cho phục vụ.

Luồng: khách đến -> phục vụ mở phiên bàn -> khách quét QR cố định ở bàn, vào phiên (token ký) ->
chọn món vào giỏ chung -> gửi món -> bếp nhận phiếu, làm xong bấm "xong" -> phục vụ thấy món ở bàn nào -> "đã phục vụ".
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...config import settings as cfg
from ...db import get_db
from ...deps import require_roles

guest_router = APIRouter(prefix="/dining", tags=["dining-guest"])
floor_router = APIRouter(prefix="/floor", tags=["floor"])
kitchen_router = APIRouter(prefix="/kitchen", tags=["kitchen"])
qr_router = APIRouter(tags=["qr"])

front = require_roles("manager", "waiter")
kitchen_roles = require_roles("manager", "kitchen")
ACTIVE_ITEM = ("new", "preparing", "ready")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ------------------------------------------------------------------ mã QR của bàn
def sign_table(table_id: uuid.UUID | str) -> str:
    sig = hmac.new(cfg.jwt_secret.encode(), str(table_id).encode(), hashlib.sha256).hexdigest()[:16]
    return f"{table_id}.{sig}"


def parse_table_code(code: str) -> uuid.UUID:
    tid, _, sig = code.partition(".")
    try:
        u = uuid.UUID(tid)
    except ValueError:
        raise HTTPException(404, "Mã QR không hợp lệ")
    if not hmac.compare_digest(sign_table(u), f"{tid}.{sig}"):
        raise HTTPException(404, "Mã QR không hợp lệ")
    return u


@qr_router.get("/tables/{table_id}/qr")
def table_qr(table_id: uuid.UUID, user: dict = Depends(front), db: Session = Depends(get_db)):
    ok = db.execute(text("SELECT code FROM dining_tables WHERE id = :i AND restaurant_id = :r"),
                    {"i": table_id, "r": user["restaurant_id"]}).scalar()
    if not ok:
        raise HTTPException(404, "Không tìm thấy bàn")
    return {"table_code": ok, "path": f"/ban/{sign_table(table_id)}"}


# ------------------------------------------------------------------ khách tại bàn
def _open_session_for_table(db: Session, table_id):
    return db.execute(
        text("SELECT s.id, s.token_hash, s.restaurant_id FROM dining_sessions s WHERE s.table_id = :t AND s.status = 'open'"),
        {"t": table_id},
    ).mappings().first()


@guest_router.get("/table/{code}")
def table_info(code: str, db: Session = Depends(get_db)):
    tid = parse_table_code(code)
    t = db.execute(
        text("SELECT t.code, a.name AS area, r.name AS restaurant FROM dining_tables t "
             "JOIN restaurants r ON r.id = t.restaurant_id LEFT JOIN areas a ON a.id = t.area_id WHERE t.id = :i"),
        {"i": tid},
    ).mappings().first()
    if not t:
        raise HTTPException(404, "Mã QR không hợp lệ")
    return {**dict(t), "session_open": _open_session_for_table(db, tid) is not None}


class JoinIn(BaseModel):
    name: str | None = Field(default=None, max_length=40)


@guest_router.post("/table/{code}/join")
def join(code: str, body: JoinIn, db: Session = Depends(get_db)):
    tid = parse_table_code(code)
    ses = _open_session_for_table(db, tid)
    if not ses:
        raise HTTPException(409, "Bàn chưa được mở. Vui lòng báo nhân viên phục vụ.")
    n = db.execute(text("SELECT count(*) FROM session_guests WHERE session_id = :s"), {"s": ses["id"]}).scalar()
    name = (body.name or "").strip() or f"Khách {n + 1}"
    gid = db.execute(
        text("INSERT INTO session_guests (session_id, display_name) VALUES (:s, :n) RETURNING id"),
        {"s": ses["id"], "n": name},
    ).scalar_one()
    db.commit()
    # sk: bí mật của phiên; đối chiếu với token_hash nên token cũ của phiên khác không dùng được
    sk = _sha_secret(ses["id"])
    token = jwt.encode(
        {"typ": "guest", "sid": str(ses["id"]), "gid": str(gid), "sk": sk,
         "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
        cfg.jwt_secret, "HS256",
    )
    return {"token": token, "guest_id": str(gid), "name": name}


def _sha_secret(session_id) -> str:
    # bí mật của phiên suy ra từ khóa máy chủ + id phiên; DB chỉ lưu băm
    return hmac.new(cfg.jwt_secret.encode(), f"session:{session_id}".encode(), hashlib.sha256).hexdigest()


def guest_ctx(x_guest_token: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    if not x_guest_token:
        raise HTTPException(401, "Chưa vào bàn")
    try:
        c = jwt.decode(x_guest_token, cfg.jwt_secret, algorithms=["HS256"])
        if c.get("typ") != "guest":
            raise ValueError
        sid, gid = uuid.UUID(c["sid"]), uuid.UUID(c["gid"])
    except Exception:
        raise HTTPException(401, "Phiên gọi món không hợp lệ, hãy quét lại mã QR")
    s = db.execute(
        text("SELECT s.id, s.restaurant_id, s.table_id, s.status, s.token_hash, t.code AS table_code "
             "FROM dining_sessions s JOIN dining_tables t ON t.id = s.table_id WHERE s.id = :i"), {"i": sid},
    ).mappings().first()
    if (not s or s["status"] != "open" or not hmac.compare_digest(s["token_hash"], _sha(c["sk"]))
            or c["sk"] != _sha_secret(sid)):
        raise HTTPException(401, "Bàn đã đóng hoặc phiên hết hạn, hãy quét lại mã QR")
    g = db.execute(text("SELECT id, display_name FROM session_guests WHERE id = :g AND session_id = :s"),
                   {"g": gid, "s": sid}).mappings().first()
    if not g:
        raise HTTPException(401, "Phiên gọi món không hợp lệ, hãy quét lại mã QR")
    return {**dict(s), "guest_id": g["id"], "guest_name": g["display_name"]}


@guest_router.get("/state")
def state(ctx: dict = Depends(guest_ctx), db: Session = Depends(get_db)):
    sid = ctx["id"]
    guests = db.execute(text("SELECT id, display_name FROM session_guests WHERE session_id = :s ORDER BY joined_at"), {"s": sid}).mappings().all()
    cart = db.execute(
        text("SELECT c.id, c.guest_id, g.display_name AS guest_name, c.dish_id, d.name, d.price_vnd, d.is_available, "
             "c.quantity, c.note FROM cart_items c JOIN dishes d ON d.id = c.dish_id "
             "JOIN session_guests g ON g.id = c.guest_id WHERE c.session_id = :s ORDER BY c.created_at"), {"s": sid},
    ).mappings().all()
    items = db.execute(
        text("SELECT i.id, i.dish_name AS name, i.unit_price_vnd AS price_vnd, i.quantity, i.note, i.status, "
             "i.cancel_reason, g.display_name AS guest_name, i.created_at FROM order_items i "
             "JOIN orders o ON o.id = i.order_id LEFT JOIN session_guests g ON g.id = i.guest_id "
             "WHERE o.session_id = :s ORDER BY i.created_at"), {"s": sid},
    ).mappings().all()
    cj = lambda r: {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in dict(r).items()}
    return {
        "table_code": ctx["table_code"], "me": str(ctx["guest_id"]), "my_name": ctx["guest_name"],
        "guests": [{"id": str(g["id"]), "name": g["display_name"]} for g in guests],
        "cart": [cj(r) for r in cart],
        "cart_total": sum(r["price_vnd"] * r["quantity"] for r in cart),
        "items": [{**cj(r), "created_at": r["created_at"].isoformat()} for r in items],
        "ordered_total": sum(r["price_vnd"] * r["quantity"] for r in items if r["status"] != "cancelled"),
    }


class CartIn(BaseModel):
    dish_id: uuid.UUID
    quantity: int = Field(ge=0, le=99)
    note: str | None = Field(default=None, max_length=200)


@guest_router.put("/cart")
def set_cart(body: CartIn, ctx: dict = Depends(guest_ctx), db: Session = Depends(get_db)):
    if body.quantity == 0:
        db.execute(text("DELETE FROM cart_items WHERE guest_id = :g AND dish_id = :d"), {"g": ctx["guest_id"], "d": body.dish_id})
        db.commit()
        return {"ok": True}
    d = db.execute(text("SELECT is_active, is_available, name FROM dishes WHERE id = :d AND restaurant_id = :r"),
                   {"d": body.dish_id, "r": ctx["restaurant_id"]}).mappings().first()
    if not d or not d["is_active"]:
        raise HTTPException(404, "Không tìm thấy món")
    if not d["is_available"]:
        raise HTTPException(409, f"{d['name']} đã hết món")
    db.execute(
        text("INSERT INTO cart_items (session_id, guest_id, dish_id, quantity, note) VALUES (:s, :g, :d, :q, :n) "
             "ON CONFLICT (guest_id, dish_id) DO UPDATE SET quantity = EXCLUDED.quantity, note = EXCLUDED.note"),
        {"s": ctx["id"], "g": ctx["guest_id"], "d": body.dish_id, "q": body.quantity, "n": body.note or None},
    )
    db.commit()
    return {"ok": True}


@guest_router.post("/orders", status_code=201)
def send_order(ctx: dict = Depends(guest_ctx), db: Session = Depends(get_db)):
    """Gửi toàn bộ giỏ chung của bàn sang bếp."""
    cart = db.execute(
        text("SELECT c.id, c.guest_id, c.dish_id, c.quantity, c.note, d.name, d.price_vnd, d.is_available, d.is_active "
             "FROM cart_items c JOIN dishes d ON d.id = c.dish_id WHERE c.session_id = :s FOR UPDATE OF c"),
        {"s": ctx["id"]},
    ).mappings().all()
    if not cart:
        raise HTTPException(422, "Giỏ đang trống")
    out = [c["name"] for c in cart if not c["is_available"] or not c["is_active"]]
    if out:
        raise HTTPException(409, "Các món sau đã hết, hãy bỏ khỏi giỏ: " + ", ".join(out))
    oid = db.execute(text("INSERT INTO orders (session_id, sent_by) VALUES (:s, :g) RETURNING id"),
                     {"s": ctx["id"], "g": ctx["guest_id"]}).scalar_one()
    for c in cart:
        db.execute(
            text("INSERT INTO order_items (order_id, dish_id, guest_id, dish_name, unit_price_vnd, quantity, note) "
                 "VALUES (:o, :d, :g, :n, :p, :q, :note)"),
            {"o": oid, "d": c["dish_id"], "g": c["guest_id"], "n": c["name"], "p": c["price_vnd"], "q": c["quantity"], "note": c["note"]},
        )
    db.execute(text("DELETE FROM cart_items WHERE session_id = :s"), {"s": ctx["id"]})
    db.commit()
    return {"order_id": str(oid), "items": len(cart)}


@guest_router.post("/items/{item_id}/cancel")
def guest_cancel_item(item_id: uuid.UUID, ctx: dict = Depends(guest_ctx), db: Session = Depends(get_db)):
    n = db.execute(
        text("UPDATE order_items i SET status = 'cancelled', cancel_reason = 'Khách hủy', status_changed_at = now() "
             "FROM orders o WHERE i.id = :i AND i.order_id = o.id AND o.session_id = :s AND i.status = 'new'"),
        {"i": item_id, "s": ctx["id"]},
    ).rowcount
    db.commit()
    if n == 0:
        raise HTTPException(409, "Món đã được bếp nhận làm nên không hủy được, hãy báo nhân viên")
    return {"ok": True}


# ------------------------------------------------------------------ phục vụ: sơ đồ tầng
@floor_router.get("")
def floor(user: dict = Depends(front), db: Session = Depends(get_db)):
    rid = user["restaurant_id"]
    tables = db.execute(
        text("SELECT t.id, t.code, t.capacity, a.name AS area FROM dining_tables t LEFT JOIN areas a ON a.id = t.area_id "
             "WHERE t.restaurant_id = :r AND t.is_active ORDER BY a.name NULLS LAST, t.code"), {"r": rid}).mappings().all()
    sess = {r["table_id"]: r for r in db.execute(
        text("SELECT s.id, s.table_id, s.opened_at, s.reservation_id, "
             "(SELECT count(*) FROM session_guests g WHERE g.session_id = s.id) AS guests, "
             "COALESCE((SELECT count(*) FILTER (WHERE i.status = 'new') FROM order_items i JOIN orders o ON o.id = i.order_id WHERE o.session_id = s.id), 0) AS n_new, "
             "COALESCE((SELECT count(*) FILTER (WHERE i.status = 'preparing') FROM order_items i JOIN orders o ON o.id = i.order_id WHERE o.session_id = s.id), 0) AS n_prep, "
             "COALESCE((SELECT count(*) FILTER (WHERE i.status = 'ready') FROM order_items i JOIN orders o ON o.id = i.order_id WHERE o.session_id = s.id), 0) AS n_ready "
             "FROM dining_sessions s WHERE s.restaurant_id = :r AND s.status = 'open'"), {"r": rid}).mappings()}
    nxt = {r["table_id"]: r for r in db.execute(
        text("SELECT DISTINCT ON (rt.table_id) rt.table_id, r.id, r.starts_at, r.party_size, r.status, u.full_name "
             "FROM reservation_tables rt JOIN reservations r ON r.id = rt.reservation_id LEFT JOIN users u ON u.id = r.user_id "
             "JOIN dining_tables t ON t.id = rt.table_id "
             "WHERE t.restaurant_id = :r AND rt.is_active AND r.status IN ('confirmed', 'pending_deposit') "
             "AND upper(rt.during) > now() AND lower(rt.during) < now() + interval '3 hours' "
             "ORDER BY rt.table_id, lower(rt.during)"), {"r": rid}).mappings()}
    out = []
    for t in tables:
        s, n = sess.get(t["id"]), nxt.get(t["id"])
        item = {"id": str(t["id"]), "code": t["code"], "capacity": t["capacity"], "area": t["area"],
                "state": "occupied" if s else ("reserved" if n else "free"), "session": None, "reservation": None}
        if s:
            item["session"] = {"id": str(s["id"]), "opened_at": s["opened_at"].isoformat(), "guests": s["guests"],
                               "new": s["n_new"], "preparing": s["n_prep"], "ready": s["n_ready"]}
        if n:
            item["reservation"] = {"id": str(n["id"]), "starts_at": n["starts_at"].isoformat(), "party_size": n["party_size"],
                                   "status": n["status"], "name": n["full_name"]}
        out.append(item)
    return out


class OpenIn(BaseModel):
    table_id: uuid.UUID
    reservation_id: uuid.UUID | None = None


def _start_session(db: Session, user: dict, table_id, reservation_id) -> uuid.UUID:
    """Mở phiên bàn; nếu theo lượt đặt thì chuyển lượt đặt sang 'seated' và gửi món đặt trước xuống bếp."""
    rid = user["restaurant_id"]
    sid = uuid.uuid4()
    db.execute(
        text("INSERT INTO dining_sessions (id, restaurant_id, table_id, reservation_id, opened_by, token_hash, token_expires_at) "
             "VALUES (:i, :r, :t, :res, :u, :h, now() + interval '12 hours')"),
        {"i": sid, "r": rid, "t": table_id, "res": reservation_id, "u": user["id"], "h": _sha(_sha_secret(sid))},
    )
    if reservation_id:
        db.execute(text("UPDATE reservations SET status = 'seated', checked_in_at = now() WHERE id = :i"), {"i": reservation_id})
        pre = db.execute(text("SELECT dish_id, dish_name, unit_price_vnd, quantity, note FROM reservation_items WHERE reservation_id = :i"),
                         {"i": reservation_id}).mappings().all()
        if pre:
            oid = db.execute(text("INSERT INTO orders (session_id) VALUES (:s) RETURNING id"), {"s": sid}).scalar_one()
            for it in pre:
                db.execute(
                    text("INSERT INTO order_items (order_id, dish_id, dish_name, unit_price_vnd, quantity, note) "
                         "VALUES (:o, :d, :n, :p, :q, :note)"),
                    {"o": oid, "d": it["dish_id"], "n": it["dish_name"], "p": it["unit_price_vnd"], "q": it["quantity"],
                     "note": ("Đặt trước. " + it["note"]) if it["note"] else "Đặt trước"})
    return sid


@floor_router.post("/sessions", status_code=201)
def open_session(body: OpenIn, user: dict = Depends(front), db: Session = Depends(get_db)):
    rid = user["restaurant_id"]
    if not db.execute(text("SELECT 1 FROM dining_tables WHERE id = :t AND restaurant_id = :r AND is_active"),
                      {"t": body.table_id, "r": rid}).first():
        raise HTTPException(404, "Không tìm thấy bàn")
    if body.reservation_id:
        r = db.execute(text("SELECT status FROM reservations WHERE id = :i AND restaurant_id = :r FOR UPDATE"),
                       {"i": body.reservation_id, "r": rid}).mappings().first()
        if not r:
            raise HTTPException(404, "Không tìm thấy lượt đặt")
        if r["status"] == "pending_deposit":
            raise HTTPException(409, "Khách chưa hoàn tất đặt cọc")
        if r["status"] != "confirmed":
            raise HTTPException(409, "Lượt đặt này không còn hiệu lực để nhận khách")
    try:
        sid = _start_session(db, user, body.table_id, body.reservation_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bàn đang có khách hoặc lượt đặt này đã được nhận")
    return {"session_id": str(sid)}


class CheckinIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)


@floor_router.post("/checkin")
def checkin(body: CheckinIn, user: dict = Depends(front), db: Session = Depends(get_db)):
    """Quét/nhập mã QR đặt bàn của khách: mở phiên bàn đúng bàn đã giữ, gửi món đặt trước xuống bếp."""
    code = body.code.strip().upper()
    r = db.execute(
        text("SELECT r.id, r.status, r.starts_at, r.ends_at, r.party_size, r.kind, r.service_request, u.full_name, "
             "(SELECT rt.table_id FROM reservation_tables rt WHERE rt.reservation_id = r.id AND rt.is_active LIMIT 1) AS table_id "
             "FROM reservations r LEFT JOIN users u ON u.id = r.user_id "
             "WHERE r.checkin_code = :c AND r.restaurant_id = :rid FOR UPDATE OF r"), {"c": code, "rid": user["restaurant_id"]}).mappings().first()
    if not r:
        raise HTTPException(404, "Không tìm thấy lượt đặt với mã này")
    msgs = {"pending_deposit": "Khách chưa hoàn tất đặt cọc", "seated": "Lượt đặt này đã check-in rồi",
            "completed": "Lượt đặt này đã hoàn tất", "cancelled": "Lượt đặt này đã bị hủy",
            "expired": "Lượt đặt này đã hết hạn giữ chỗ", "no_show": "Lượt đặt này đã bị ghi vắng mặt"}
    if r["status"] != "confirmed":
        raise HTTPException(409, msgs.get(r["status"], "Lượt đặt không hợp lệ"))
    now = datetime.now(timezone.utc)
    if now < r["starts_at"] - timedelta(minutes=60):
        raise HTTPException(409, "Chưa đến giờ check-in (mở trước giờ hẹn 60 phút)")
    if now > r["ends_at"]:
        raise HTTPException(409, "Đã quá giờ của lượt đặt này")
    if not r["table_id"]:
        raise HTTPException(409, "Lượt đặt chưa được gán bàn")
    pre = db.execute(text("SELECT count(*) FROM reservation_items WHERE reservation_id = :i"), {"i": r["id"]}).scalar()
    code_t = db.execute(text("SELECT code FROM dining_tables WHERE id = :t"), {"t": r["table_id"]}).scalar()
    try:
        sid = _start_session(db, user, r["table_id"], r["id"])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Bàn {code_t} vẫn đang có khách của lượt trước, hãy xếp bàn khác hoặc chờ")
    return {"session_id": str(sid), "table_code": code_t, "customer": r["full_name"], "party_size": r["party_size"],
            "pre_ordered_items": pre, "service_request": r["service_request"]}


@floor_router.get("/walk-in")
def walk_in_options(party: int, user: dict = Depends(front), db: Session = Depends(get_db)):
    """Bàn trống ngay bây giờ cho khách chưa đặt trước: đủ chỗ, không có khách, không vướng lượt đặt sắp tới."""
    s = db.execute(text("SELECT dining_minutes, turn_buffer_minutes FROM restaurants WHERE id = :r"), {"r": user["restaurant_id"]}).mappings().first()
    horizon = timedelta(minutes=s["dining_minutes"] + s["turn_buffer_minutes"])
    now = datetime.now(timezone.utc)
    rows = db.execute(
        text("SELECT t.id, t.code, t.capacity, a.name AS area FROM dining_tables t LEFT JOIN areas a ON a.id = t.area_id "
             "WHERE t.restaurant_id = :r AND t.is_active AND t.capacity >= :p AND t.min_party <= :p "
             "AND NOT EXISTS (SELECT 1 FROM dining_sessions s WHERE s.table_id = t.id AND s.status = 'open') "
             "AND NOT EXISTS (SELECT 1 FROM reservation_tables rt WHERE rt.table_id = t.id AND rt.is_active "
             "                AND rt.during && tstzrange(:a, :b)) "
             "ORDER BY t.capacity, t.code"),
        {"r": user["restaurant_id"], "p": party, "a": now, "b": now + horizon}).mappings().all()
    return [{**dict(r), "id": str(r["id"])} for r in rows]


# ------------------------------------------------------------------ khách đã check-in: vào bàn bằng tài khoản
@guest_router.get("/mine")
def my_active_session(user: dict = Depends(require_roles("customer")), db: Session = Depends(get_db)):
    """Khách đã được nhân viên check-in chưa? Nếu rồi trả về bàn để chuyển thẳng sang trang chọn món."""
    r = db.execute(
        text("SELECT s.id, t.id AS table_id, t.code FROM dining_sessions s JOIN reservations r ON r.id = s.reservation_id "
             "JOIN dining_tables t ON t.id = s.table_id WHERE r.user_id = :u AND s.status = 'open' ORDER BY s.opened_at DESC LIMIT 1"),
        {"u": user["id"]}).mappings().first()
    if not r:
        return {"active": False}
    return {"active": True, "table_label": r["code"], "table_code": sign_table(r["table_id"])}


@guest_router.post("/mine/join")
def my_join(user: dict = Depends(require_roles("customer")), db: Session = Depends(get_db)):
    r = db.execute(
        text("SELECT s.id, t.code FROM dining_sessions s JOIN reservations r ON r.id = s.reservation_id "
             "JOIN dining_tables t ON t.id = s.table_id WHERE r.user_id = :u AND s.status = 'open' ORDER BY s.opened_at DESC LIMIT 1"),
        {"u": user["id"]}).mappings().first()
    if not r:
        raise HTTPException(409, "Bạn chưa được nhân viên check-in")
    g = db.execute(text("SELECT id, display_name FROM session_guests WHERE session_id = :s AND user_id = :u"),
                   {"s": r["id"], "u": user["id"]}).mappings().first()
    if not g:
        g = db.execute(text("INSERT INTO session_guests (session_id, user_id, display_name) VALUES (:s, :u, :n) RETURNING id, display_name"),
                       {"s": r["id"], "u": user["id"], "n": user["full_name"]}).mappings().first()
        db.commit()
    token = jwt.encode(
        {"typ": "guest", "sid": str(r["id"]), "gid": str(g["id"]), "sk": _sha_secret(r["id"]),
         "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, cfg.jwt_secret, "HS256")
    return {"token": token, "guest_id": str(g["id"]), "name": g["display_name"], "table_label": r["code"]}


@floor_router.get("/sessions/{sid}")
def session_detail(sid: uuid.UUID, user: dict = Depends(front), db: Session = Depends(get_db)):
    s = db.execute(
        text("SELECT s.id, s.status, s.opened_at, t.code, "
             "COALESCE((SELECT p.paid_amount FROM payments p WHERE p.reservation_id = s.reservation_id AND p.purpose = 'deposit' AND p.status = 'paid'), 0) AS deposit_paid "
             "FROM dining_sessions s JOIN dining_tables t ON t.id = s.table_id "
             "WHERE s.id = :i AND s.restaurant_id = :r"), {"i": sid, "r": user["restaurant_id"]}).mappings().first()
    if not s:
        raise HTTPException(404, "Không tìm thấy phiên bàn")
    items = db.execute(
        text("SELECT i.id, i.dish_name AS name, i.unit_price_vnd AS price_vnd, i.quantity, i.note, i.status, i.cancel_reason, "
             "g.display_name AS guest_name FROM order_items i JOIN orders o ON o.id = i.order_id "
             "LEFT JOIN session_guests g ON g.id = i.guest_id WHERE o.session_id = :s ORDER BY i.created_at"), {"s": sid}).mappings().all()
    return {"id": str(s["id"]), "table_code": s["code"], "status": s["status"], "opened_at": s["opened_at"].isoformat(),
            "items": [{**dict(i), "id": str(i["id"])} for i in items],
            "total": (tot := sum(i["price_vnd"] * i["quantity"] for i in items if i["status"] != "cancelled")),
            "deposit_paid": s["deposit_paid"], "amount_due": max(tot - s["deposit_paid"], 0)}


@floor_router.post("/sessions/{sid}/close")
def close_session(sid: uuid.UUID, user: dict = Depends(front), db: Session = Depends(get_db)):
    row = db.execute(
        text("UPDATE dining_sessions SET status = 'closed', closed_at = now(), closed_by = :u "
             "WHERE id = :i AND restaurant_id = :r AND status = 'open' RETURNING reservation_id"),
        {"i": sid, "r": user["restaurant_id"], "u": user["id"]}).first()
    if not row:
        raise HTTPException(404, "Phiên bàn không tồn tại hoặc đã đóng")
    if row[0]:
        db.execute(text("UPDATE reservations SET status = 'completed' WHERE id = :i"), {"i": row[0]})
    db.commit()
    return {"ok": True}


@floor_router.get("/ready")
def ready_items(user: dict = Depends(front), db: Session = Depends(get_db)):
    """Món bếp đã làm xong, chờ phục vụ mang ra bàn."""
    rows = db.execute(
        text("SELECT i.id, i.dish_name AS name, i.quantity, i.note, i.status_changed_at, t.code AS table_code "
             "FROM order_items i JOIN orders o ON o.id = i.order_id JOIN dining_sessions s ON s.id = o.session_id "
             "JOIN dining_tables t ON t.id = s.table_id WHERE s.restaurant_id = :r AND s.status = 'open' AND i.status = 'ready' "
             "ORDER BY i.status_changed_at"), {"r": user["restaurant_id"]}).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "status_changed_at": r["status_changed_at"].isoformat()} for r in rows]


@floor_router.post("/items/{item_id}/served")
def mark_served(item_id: uuid.UUID, user: dict = Depends(front), db: Session = Depends(get_db)):
    n = db.execute(
        text("UPDATE order_items i SET status = 'served', status_changed_at = now(), status_changed_by = :u "
             "FROM orders o JOIN dining_sessions s ON s.id = o.session_id "
             "WHERE i.id = :i AND i.order_id = o.id AND s.restaurant_id = :r AND i.status = 'ready'"),
        {"i": item_id, "u": user["id"], "r": user["restaurant_id"]}).rowcount
    db.commit()
    if n == 0:
        raise HTTPException(409, "Món chưa xong hoặc đã được phục vụ")
    return {"ok": True}


# ------------------------------------------------------------------ bếp
@kitchen_router.get("/items")
def kitchen_items(user: dict = Depends(kitchen_roles), db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT i.id, i.dish_name AS name, i.quantity, i.note, i.status, i.created_at, i.status_changed_at, "
             "t.code AS table_code, g.display_name AS guest_name FROM order_items i "
             "JOIN orders o ON o.id = i.order_id JOIN dining_sessions s ON s.id = o.session_id "
             "JOIN dining_tables t ON t.id = s.table_id LEFT JOIN session_guests g ON g.id = i.guest_id "
             "WHERE s.restaurant_id = :r AND s.status = 'open' AND i.status IN ('new', 'preparing', 'ready') "
             "ORDER BY i.created_at"), {"r": user["restaurant_id"]}).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "created_at": r["created_at"].isoformat(),
             "status_changed_at": r["status_changed_at"].isoformat()} for r in rows]


class KitchenStatusIn(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=120)


ALLOWED = {"new": {"preparing", "ready", "cancelled"}, "preparing": {"ready", "cancelled"}, "ready": {"preparing"}}


@kitchen_router.patch("/items/{item_id}")
def kitchen_set_status(item_id: uuid.UUID, body: KitchenStatusIn, user: dict = Depends(kitchen_roles), db: Session = Depends(get_db)):
    if body.status not in ("preparing", "ready", "cancelled"):
        raise HTTPException(422, "Trạng thái không hợp lệ")
    if body.status == "cancelled" and not (body.reason or "").strip():
        raise HTTPException(422, "Cần ghi lý do khi hủy món")
    cur = db.execute(
        text("SELECT i.status FROM order_items i JOIN orders o ON o.id = i.order_id JOIN dining_sessions s ON s.id = o.session_id "
             "WHERE i.id = :i AND s.restaurant_id = :r FOR UPDATE OF i"), {"i": item_id, "r": user["restaurant_id"]}).scalar()
    if cur is None:
        raise HTTPException(404, "Không tìm thấy món")
    if body.status not in ALLOWED.get(cur, set()):
        raise HTTPException(409, "Món đã ở trạng thái khác, hãy tải lại màn hình")
    db.execute(
        text("UPDATE order_items SET status = CAST(:s AS order_item_status), status_changed_at = now(), status_changed_by = :u, "
             "cancel_reason = :why WHERE id = :i"),
        {"s": body.status, "u": user["id"], "i": item_id, "why": (body.reason or None) if body.status == "cancelled" else None})
    db.commit()
    return {"ok": True}
