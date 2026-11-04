"""Cài đặt nhà hàng: thông số đặt bàn, khu vực, bàn, giờ mở cửa."""
import uuid
from datetime import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import require_roles

router = APIRouter(tags=["restaurant-setup"])
manager_only = require_roles("manager")
staff_roles = require_roles("manager", "waiter", "kitchen")


def _rows(res):
    return [{k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in dict(r).items()} for r in res.mappings().all()]


# ---------------------------------------------------------------- thông số
class SettingsIn(BaseModel):
    name: str = Field(min_length=1)
    address: str | None = None
    phone: str | None = None
    slot_minutes: int = Field(gt=0)
    dining_minutes: int = Field(gt=0)
    turn_buffer_minutes: int = Field(ge=0)
    deposit_amount: int = Field(ge=0)
    deposit_hold_minutes: int = Field(gt=0)
    free_cancel_hours: int = Field(ge=0)
    bank_code: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    deposit_percent: int = Field(default=30, ge=0, le=100)
    late_grace_minutes: int = Field(default=15, ge=0)
    tagline: str | None = None
    about: str | None = None
    email: str | None = None
    facebook_url: str | None = None
    tiktok_url: str | None = None
    instagram_url: str | None = None
    youtube_url: str | None = None
    zalo_url: str | None = None
    map_url: str | None = None


SETTINGS_COLS = (
    "id, name, address, phone, slot_minutes, dining_minutes, turn_buffer_minutes, deposit_amount, "
    "deposit_hold_minutes, free_cancel_hours, bank_code, bank_account_number, bank_account_name, deposit_percent, "
    "late_grace_minutes, tagline, about, email, facebook_url, tiktok_url, instagram_url, youtube_url, zalo_url, map_url"
)


@router.get("/restaurant/settings")
def get_settings(user: dict = Depends(staff_roles), db: Session = Depends(get_db)):
    r = db.execute(text(f"SELECT {SETTINGS_COLS} FROM restaurants WHERE id = :r"), {"r": user["restaurant_id"]})
    return _rows(r)[0]


@router.put("/restaurant/settings")
def put_settings(body: SettingsIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    sets = ", ".join(f"{k} = :{k}" for k in body.model_dump())
    db.execute(text(f"UPDATE restaurants SET {sets} WHERE id = :rid"), {**body.model_dump(), "rid": user["restaurant_id"]})
    db.commit()
    return get_settings(user, db)


# ---------------------------------------------------------------- khu vực
class AreaIn(BaseModel):
    name: str = Field(min_length=1)


@router.get("/areas")
def list_areas(user: dict = Depends(staff_roles), db: Session = Depends(get_db)):
    return _rows(db.execute(text("SELECT id, name FROM areas WHERE restaurant_id = :r ORDER BY name"), {"r": user["restaurant_id"]}))


@router.post("/areas", status_code=201)
def create_area(body: AreaIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("INSERT INTO areas (restaurant_id, name) VALUES (:r, :n) RETURNING id, name"),
            {"r": user["restaurant_id"], "n": body.name.strip()},
        )
        out = _rows(row)[0]
        db.commit()
        return out
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tên khu vực đã tồn tại")


@router.patch("/areas/{area_id}")
def rename_area(area_id: uuid.UUID, body: AreaIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    try:
        res = db.execute(
            text("UPDATE areas SET name = :n WHERE id = :i AND restaurant_id = :r RETURNING id, name"),
            {"n": body.name.strip(), "i": area_id, "r": user["restaurant_id"]},
        )
        rows = _rows(res)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Tên khu vực đã tồn tại")
    if not rows:
        raise HTTPException(404, "Không tìm thấy khu vực")
    return rows[0]


@router.delete("/areas/{area_id}", status_code=204)
def delete_area(area_id: uuid.UUID, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    # bàn thuộc khu vực sẽ được chuyển về "chưa gán khu vực" (ON DELETE SET NULL)
    res = db.execute(text("DELETE FROM areas WHERE id = :i AND restaurant_id = :r"), {"i": area_id, "r": user["restaurant_id"]})
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Không tìm thấy khu vực")


# ---------------------------------------------------------------- bàn
class TableIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    capacity: int = Field(gt=0, le=50)
    min_party: int = Field(default=1, ge=1)
    area_id: uuid.UUID | None = None
    is_active: bool = True


TABLE_SQL = "SELECT id, code, capacity, min_party, area_id, is_active FROM dining_tables WHERE restaurant_id = :r"


def _check_table(body: TableIn, db: Session, rid) -> None:
    if body.min_party > body.capacity:
        raise HTTPException(422, "Số khách tối thiểu không được lớn hơn sức chứa")
    if body.area_id and not db.execute(
        text("SELECT 1 FROM areas WHERE id = :a AND restaurant_id = :r"), {"a": body.area_id, "r": rid}
    ).first():
        raise HTTPException(422, "Khu vực không thuộc nhà hàng này")


@router.get("/tables")
def list_tables(user: dict = Depends(staff_roles), db: Session = Depends(get_db)):
    return _rows(db.execute(text(TABLE_SQL + " ORDER BY code"), {"r": user["restaurant_id"]}))


@router.post("/tables", status_code=201)
def create_table(body: TableIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    _check_table(body, db, user["restaurant_id"])
    try:
        res = db.execute(
            text(
                "INSERT INTO dining_tables (restaurant_id, area_id, code, capacity, min_party, is_active) "
                "VALUES (:r, :a, :c, :cap, :mp, :act) RETURNING id, code, capacity, min_party, area_id, is_active"
            ),
            {"r": user["restaurant_id"], "a": body.area_id, "c": body.code.strip(), "cap": body.capacity,
             "mp": body.min_party, "act": body.is_active},
        )
        out = _rows(res)[0]
        db.commit()
        return out
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Mã bàn đã tồn tại")


@router.put("/tables/{table_id}")
def update_table(table_id: uuid.UUID, body: TableIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    _check_table(body, db, user["restaurant_id"])
    try:
        res = db.execute(
            text(
                "UPDATE dining_tables SET area_id = :a, code = :c, capacity = :cap, min_party = :mp, is_active = :act "
                "WHERE id = :i AND restaurant_id = :r RETURNING id, code, capacity, min_party, area_id, is_active"
            ),
            {"i": table_id, "r": user["restaurant_id"], "a": body.area_id, "c": body.code.strip(),
             "cap": body.capacity, "mp": body.min_party, "act": body.is_active},
        )
        rows = _rows(res)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Mã bàn đã tồn tại")
    if not rows:
        raise HTTPException(404, "Không tìm thấy bàn")
    return rows[0]


@router.delete("/tables/{table_id}", status_code=204)
def delete_table(table_id: uuid.UUID, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    try:
        res = db.execute(text("DELETE FROM dining_tables WHERE id = :i AND restaurant_id = :r"),
                         {"i": table_id, "r": user["restaurant_id"]})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Bàn đã có lịch đặt hoặc phiên bàn, hãy tắt bàn thay vì xóa")
    if res.rowcount == 0:
        raise HTTPException(404, "Không tìm thấy bàn")


# ---------------------------------------------------------------- giờ mở cửa
class WindowIn(BaseModel):
    weekday: int = Field(ge=1, le=7)  # 1 = thứ hai
    open_time: time
    close_time: time


@router.get("/service-windows")
def list_windows(user: dict = Depends(staff_roles), db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT weekday, to_char(open_time, 'HH24:MI') AS open_time, to_char(close_time, 'HH24:MI') AS close_time "
             "FROM service_windows WHERE restaurant_id = :r ORDER BY weekday, open_time"),
        {"r": user["restaurant_id"]},
    )
    return _rows(rows)


@router.put("/service-windows")
def replace_windows(body: list[WindowIn], user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    """Thay toàn bộ giờ mở cửa. Các ca trong cùng một ngày không được chồng nhau."""
    by_day: dict[int, list[WindowIn]] = {}
    for w in body:
        if w.close_time <= w.open_time:
            raise HTTPException(422, "Giờ đóng cửa phải sau giờ mở cửa")
        by_day.setdefault(w.weekday, []).append(w)
    for ws in by_day.values():
        ws.sort(key=lambda x: x.open_time)
        for a, b in zip(ws, ws[1:]):
            if b.open_time < a.close_time:
                raise HTTPException(422, "Các ca trong cùng một ngày không được chồng nhau")
    db.execute(text("DELETE FROM service_windows WHERE restaurant_id = :r"), {"r": user["restaurant_id"]})
    for w in body:
        db.execute(
            text("INSERT INTO service_windows (restaurant_id, weekday, open_time, close_time) VALUES (:r, :d, :o, :c)"),
            {"r": user["restaurant_id"], "d": w.weekday, "o": w.open_time, "c": w.close_time},
        )
    db.commit()
    return list_windows(user, db)


# ---------------------------------------------------------------- dịch vụ giới thiệu trên trang công khai
class ServiceIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=400)
    icon: str | None = Field(default=None, max_length=30)


@router.get("/restaurant/services")
def list_services(user: dict = Depends(staff_roles), db: Session = Depends(get_db)):
    return _rows(db.execute(text("SELECT id, title, description, icon FROM restaurant_services WHERE restaurant_id = :r ORDER BY sort_order"),
                            {"r": user["restaurant_id"]}))


@router.put("/restaurant/services")
def put_services(body: list[ServiceIn], user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM restaurant_services WHERE restaurant_id = :r"), {"r": user["restaurant_id"]})
    for i, x in enumerate(body):
        db.execute(text("INSERT INTO restaurant_services (restaurant_id, title, description, icon, sort_order) VALUES (:r, :t, :d, :c, :o)"),
                   {"r": user["restaurant_id"], "t": x.title, "d": x.description, "c": x.icon, "o": i})
    db.commit()
    return list_services(user, db)
