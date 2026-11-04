"""Tổng quan cho quản lý và dữ liệu trang chủ công khai."""
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import require_roles
from ..booking.router import TZ, default_restaurant, expire_holds

router = APIRouter(tags=["overview"])


def hours_by_day(db: Session, rid):
    rows = db.execute(
        text("SELECT weekday, to_char(open_time, 'HH24:MI') AS o, to_char(close_time, 'HH24:MI') AS c "
             "FROM service_windows WHERE restaurant_id = :r ORDER BY weekday, open_time"), {"r": rid}).all()
    days: dict[int, list[str]] = {}
    for w, o, c in rows:
        days.setdefault(w, []).append(f"{o} – {c}")
    return [{"weekday": d, "shifts": days.get(d, [])} for d in range(1, 8)]


@router.get("/overview")
def overview(user: dict = Depends(require_roles("manager")), db: Session = Depends(get_db)):
    expire_holds(db)
    rid = user["restaurant_id"]
    one = lambda q, **p: db.execute(text(q), {"r": rid, **p}).scalar() or 0
    today = datetime.now(TZ).date()
    lo = datetime.combine(today, time(0), TZ)
    hi = lo + timedelta(days=1)
    up = db.execute(
        text("SELECT r.id, r.party_size, r.starts_at, r.status, u.full_name, "
             "(SELECT string_agg(t.code, ', ') FROM reservation_tables rt JOIN dining_tables t ON t.id = rt.table_id WHERE rt.reservation_id = r.id) AS tables "
             "FROM reservations r LEFT JOIN users u ON u.id = r.user_id "
             "WHERE r.restaurant_id = :r AND r.starts_at >= :a AND r.starts_at < :b AND r.status IN ('confirmed','pending_deposit','seated') "
             "ORDER BY r.starts_at LIMIT 8"), {"r": rid, "a": lo, "b": hi}).mappings().all()
    return {
        "tables": one("SELECT count(*) FROM dining_tables WHERE restaurant_id = :r AND is_active"),
        "seats": one("SELECT COALESCE(sum(capacity), 0) FROM dining_tables WHERE restaurant_id = :r AND is_active"),
        "dishes": one("SELECT count(*) FROM dishes WHERE restaurant_id = :r AND is_active"),
        "dishes_out": one("SELECT count(*) FROM dishes WHERE restaurant_id = :r AND is_active AND NOT is_available"),
        "reservations_today": one("SELECT count(*) FROM reservations WHERE restaurant_id = :r AND starts_at >= :a AND starts_at < :b "
                                  "AND status IN ('confirmed','pending_deposit','seated','completed')", a=lo, b=hi),
        "guests_today": one("SELECT COALESCE(sum(party_size), 0) FROM reservations WHERE restaurant_id = :r AND starts_at >= :a AND starts_at < :b "
                            "AND status IN ('confirmed','pending_deposit','seated','completed')", a=lo, b=hi),
        "sessions_open": one("SELECT count(*) FROM dining_sessions WHERE restaurant_id = :r AND status = 'open'"),
        "kitchen_queue": one("SELECT count(*) FROM order_items i JOIN orders o ON o.id = i.order_id JOIN dining_sessions s ON s.id = o.session_id "
                             "WHERE s.restaurant_id = :r AND s.status = 'open' AND i.status IN ('new','preparing')"),
        "today_shifts": next(h["shifts"] for h in hours_by_day(db, rid) if h["weekday"] == today.isoweekday()),
        "upcoming": [{"id": str(r["id"]), "party_size": r["party_size"], "starts_at": r["starts_at"].astimezone(TZ).isoformat(),
                      "status": r["status"], "name": r["full_name"], "tables": r["tables"]} for r in up],
    }


@router.get("/public/home")
def home(db: Session = Depends(get_db)):
    rid = default_restaurant(db, None)
    r = db.execute(text("SELECT name, tagline, about, address, phone, email, facebook_url, tiktok_url, instagram_url, youtube_url, "
                        "zalo_url, map_url, deposit_amount, deposit_percent, free_cancel_hours FROM restaurants WHERE id = :i"), {"i": rid}).mappings().first()
    services = db.execute(text("SELECT title, description, icon FROM restaurant_services WHERE restaurant_id = :r ORDER BY sort_order"),
                          {"r": rid}).mappings().all()
    dishes = db.execute(
        text("SELECT d.id, d.name, d.description, d.price_vnd, d.image_url, d.spiciness, d.is_vegetarian, c.name AS category "
             "FROM dishes d LEFT JOIN menu_categories c ON c.id = d.category_id "
             "WHERE d.restaurant_id = :r AND d.is_active AND d.is_available "
             "ORDER BY (d.image_url IS NULL), c.sort_order NULLS LAST, d.name LIMIT 6"), {"r": rid}).mappings().all()
    return {"restaurant": dict(r), "services": [dict(x) for x in services], "hours": hours_by_day(db, rid),
            "featured": [{**dict(d), "id": str(d["id"])} for d in dishes]}
