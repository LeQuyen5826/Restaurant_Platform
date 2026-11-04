"""Thực đơn: danh mục, món ăn, chất gây dị ứng; API công khai cho khách."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import require_roles

router = APIRouter(tags=["menu"])
manager_only = require_roles("manager")
kitchen_or_manager = require_roles("manager", "kitchen")
staff_roles = require_roles("manager", "waiter", "kitchen")
PERIODS = {"breakfast", "lunch", "dinner"}


def _clean(d: dict) -> dict:
    return {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in d.items()}


# ---------------------------------------------------------------- dị ứng
@router.get("/allergens")
def allergens(db: Session = Depends(get_db)):
    return [dict(r) for r in db.execute(text("SELECT code, name FROM allergens ORDER BY name")).mappings()]


# ---------------------------------------------------------------- danh mục
class CategoryIn(BaseModel):
    name: str = Field(min_length=1)
    sort_order: int = 0


@router.get("/menu/categories")
def list_categories(user: dict = Depends(staff_roles), db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT id, name, sort_order FROM menu_categories WHERE restaurant_id = :r ORDER BY sort_order, name"),
        {"r": user["restaurant_id"]},
    ).mappings()
    return [_clean(dict(r)) for r in rows]


@router.post("/menu/categories", status_code=201)
def create_category(body: CategoryIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("INSERT INTO menu_categories (restaurant_id, name, sort_order) VALUES (:r, :n, :s) RETURNING id, name, sort_order"),
            {"r": user["restaurant_id"], "n": body.name.strip(), "s": body.sort_order},
        ).mappings().first()
        db.commit()
        return _clean(dict(row))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tên danh mục đã tồn tại")


@router.put("/menu/categories/{cid}")
def update_category(cid: uuid.UUID, body: CategoryIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("UPDATE menu_categories SET name = :n, sort_order = :s WHERE id = :i AND restaurant_id = :r "
                 "RETURNING id, name, sort_order"),
            {"n": body.name.strip(), "s": body.sort_order, "i": cid, "r": user["restaurant_id"]},
        ).mappings().first()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tên danh mục đã tồn tại")
    if not row:
        raise HTTPException(404, "Không tìm thấy danh mục")
    return _clean(dict(row))


@router.delete("/menu/categories/{cid}", status_code=204)
def delete_category(cid: uuid.UUID, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    # món thuộc danh mục sẽ chuyển về "chưa phân loại" (ON DELETE SET NULL)
    res = db.execute(text("DELETE FROM menu_categories WHERE id = :i AND restaurant_id = :r"),
                     {"i": cid, "r": user["restaurant_id"]})
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Không tìm thấy danh mục")


# ---------------------------------------------------------------- món ăn
class DishIn(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    price_vnd: int = Field(ge=0)
    category_id: uuid.UUID | None = None
    image_url: str | None = None
    spiciness: int = Field(default=0, ge=0, le=3)
    is_vegetarian: bool = False
    cuisine: str | None = None
    tags: list[str] = []
    ingredients: list[str] = []
    meal_periods: list[str] = ["breakfast", "lunch", "dinner"]
    allergens: list[str] = []
    is_available: bool = True
    is_active: bool = True


DISH_SELECT = """
SELECT d.id, d.name, d.description, d.price_vnd, d.category_id, d.image_url, d.spiciness, d.is_vegetarian,
       d.cuisine, d.tags, d.ingredients, d.meal_periods, d.is_available, d.is_active,
       COALESCE(array_agg(da.allergen_code ORDER BY da.allergen_code) FILTER (WHERE da.allergen_code IS NOT NULL), '{}') AS allergens
FROM dishes d LEFT JOIN dish_allergens da ON da.dish_id = d.id
"""


def _validate(body: DishIn, db: Session, rid) -> None:
    if not set(body.meal_periods) <= PERIODS or not body.meal_periods:
        raise HTTPException(422, "Bữa ăn chỉ gồm breakfast, lunch, dinner và không được để trống")
    known = {r[0] for r in db.execute(text("SELECT code FROM allergens"))}
    if not set(body.allergens) <= known:
        raise HTTPException(422, "Chất gây dị ứng không hợp lệ")
    if body.category_id and not db.execute(
        text("SELECT 1 FROM menu_categories WHERE id = :c AND restaurant_id = :r"), {"c": body.category_id, "r": rid}
    ).first():
        raise HTTPException(422, "Danh mục không thuộc nhà hàng này")


def _save_allergens(db: Session, dish_id, codes: list[str]) -> None:
    db.execute(text("DELETE FROM dish_allergens WHERE dish_id = :d"), {"d": dish_id})
    for c in set(codes):
        db.execute(text("INSERT INTO dish_allergens (dish_id, allergen_code) VALUES (:d, :c)"), {"d": dish_id, "c": c})


def _get_dish(db: Session, rid, dish_id) -> dict | None:
    row = db.execute(text(DISH_SELECT + " WHERE d.id = :i AND d.restaurant_id = :r GROUP BY d.id"),
                     {"i": dish_id, "r": rid}).mappings().first()
    return _clean(dict(row)) if row else None


_FIELDS = "name, description, price_vnd, category_id, image_url, spiciness, is_vegetarian, cuisine, is_available, is_active"


def _params(body: DishIn) -> dict:
    p = body.model_dump(exclude={"allergens"})
    p["name"] = body.name.strip()
    return p


@router.get("/menu/dishes")
def list_dishes(user: dict = Depends(staff_roles), db: Session = Depends(get_db)):
    rows = db.execute(text(DISH_SELECT + " WHERE d.restaurant_id = :r GROUP BY d.id ORDER BY d.name"),
                      {"r": user["restaurant_id"]}).mappings()
    return [_clean(dict(r)) for r in rows]


@router.post("/menu/dishes", status_code=201)
def create_dish(body: DishIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    _validate(body, db, user["restaurant_id"])
    try:
        did = db.execute(
            text(
                "INSERT INTO dishes (restaurant_id, name, description, price_vnd, category_id, image_url, spiciness, "
                "is_vegetarian, cuisine, tags, ingredients, meal_periods, is_available, is_active) "
                "VALUES (:rid, :name, :description, :price_vnd, :category_id, :image_url, :spiciness, :is_vegetarian, "
                ":cuisine, CAST(:tags AS text[]), CAST(:ingredients AS text[]), CAST(:meal_periods AS text[]), "
                ":is_available, :is_active) RETURNING id"
            ),
            {**_params(body), "rid": user["restaurant_id"]},
        ).scalar_one()
        _save_allergens(db, did, body.allergens)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tên món đã tồn tại")
    return _get_dish(db, user["restaurant_id"], did)


@router.put("/menu/dishes/{did}")
def update_dish(did: uuid.UUID, body: DishIn, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    _validate(body, db, user["restaurant_id"])
    try:
        res = db.execute(
            text(
                "UPDATE dishes SET name = :name, description = :description, price_vnd = :price_vnd, "
                "category_id = :category_id, image_url = :image_url, spiciness = :spiciness, "
                "is_vegetarian = :is_vegetarian, cuisine = :cuisine, tags = CAST(:tags AS text[]), "
                "ingredients = CAST(:ingredients AS text[]), meal_periods = CAST(:meal_periods AS text[]), "
                "is_available = :is_available, is_active = :is_active WHERE id = :did AND restaurant_id = :rid"
            ),
            {**_params(body), "did": did, "rid": user["restaurant_id"]},
        )
        if res.rowcount == 0:
            db.rollback()
            raise HTTPException(404, "Không tìm thấy món")
        _save_allergens(db, did, body.allergens)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tên món đã tồn tại")
    return _get_dish(db, user["restaurant_id"], did)


class AvailabilityIn(BaseModel):
    is_available: bool


@router.patch("/menu/dishes/{did}/availability")
def set_availability(did: uuid.UUID, body: AvailabilityIn, user: dict = Depends(kitchen_or_manager), db: Session = Depends(get_db)):
    """Bếp hoặc quản lý đánh dấu hết món / còn món."""
    res = db.execute(text("UPDATE dishes SET is_available = :a WHERE id = :i AND restaurant_id = :r"),
                     {"a": body.is_available, "i": did, "r": user["restaurant_id"]})
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Không tìm thấy món")
    return _get_dish(db, user["restaurant_id"], did)


@router.delete("/menu/dishes/{did}", status_code=204)
def delete_dish(did: uuid.UUID, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    try:
        res = db.execute(text("DELETE FROM dishes WHERE id = :i AND restaurant_id = :r"),
                         {"i": did, "r": user["restaurant_id"]})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Món đã từng được gọi, hãy ẩn món thay vì xóa")
    if res.rowcount == 0:
        raise HTTPException(404, "Không tìm thấy món")


# ---------------------------------------------------------------- công khai (khách)
@router.get("/public/menu")
def public_menu(restaurant_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    """Thực đơn cho khách. Không truyền restaurant_id thì lấy nhà hàng đầu tiên."""
    if restaurant_id is None:
        restaurant_id = db.execute(text("SELECT id FROM restaurants ORDER BY created_at LIMIT 1")).scalar()
    r = db.execute(text("SELECT id, name, address, phone, deposit_amount FROM restaurants WHERE id = :i"),
                   {"i": restaurant_id}).mappings().first()
    if not r:
        raise HTTPException(404, "Không tìm thấy nhà hàng")
    cats = db.execute(text("SELECT id, name FROM menu_categories WHERE restaurant_id = :r ORDER BY sort_order, name"),
                      {"r": restaurant_id}).mappings().all()
    dishes = db.execute(
        text(DISH_SELECT + " WHERE d.restaurant_id = :r AND d.is_active GROUP BY d.id ORDER BY d.name"),
        {"r": restaurant_id},
    ).mappings().all()
    names = {r_["code"]: r_["name"] for r_ in db.execute(text("SELECT code, name FROM allergens")).mappings()}
    sections = []
    for c in list(cats) + [{"id": None, "name": "Khác"}]:
        items = [
            {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in dict(d).items()
             if k not in ("is_active", "ingredients", "tags", "meal_periods")}
            for d in dishes if d["category_id"] == c["id"]
        ]
        for it in items:
            it["allergens"] = [{"code": a, "name": names[a]} for a in it["allergens"]]
        if items:
            sections.append({"id": str(c["id"]) if c["id"] else None, "name": c["name"], "dishes": items})
    return {"restaurant": _clean(dict(r)), "sections": sections}


# ---------------------------------------------------------------- ảnh món
from pathlib import Path  # noqa: E402

from fastapi import File, UploadFile  # noqa: E402

from ...config import settings as _cfg  # noqa: E402

MAX_IMAGE = 3 * 1024 * 1024
MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png", b"RIFF": ".webp"}


def _ext_of(data: bytes) -> str | None:
    for m, ext in MAGIC.items():
        if data.startswith(m):
            if ext == ".webp" and data[8:12] != b"WEBP":
                return None
            return ext
    return None


@router.post("/menu/dishes/{did}/image")
async def upload_dish_image(did: uuid.UUID, file: UploadFile = File(...), user: dict = Depends(manager_only),
                            db: Session = Depends(get_db)):
    data = await file.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise HTTPException(413, "Ảnh quá lớn, tối đa 3 MB")
    ext = _ext_of(data)
    if not ext:
        raise HTTPException(422, "Chỉ nhận ảnh JPG, PNG hoặc WebP")
    old = db.execute(text("SELECT image_url FROM dishes WHERE id = :i AND restaurant_id = :r"),
                     {"i": did, "r": user["restaurant_id"]})
    row = old.first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy món")
    folder = Path(_cfg.upload_dir) / "dishes"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (folder / name).write_bytes(data)
    db.execute(text("UPDATE dishes SET image_url = :u WHERE id = :i"), {"u": f"/api/uploads/dishes/{name}", "i": did})
    db.commit()
    _remove_file(row[0])
    return _get_dish(db, user["restaurant_id"], did)


@router.delete("/menu/dishes/{did}/image")
def delete_dish_image(did: uuid.UUID, user: dict = Depends(manager_only), db: Session = Depends(get_db)):
    row = db.execute(text("SELECT image_url FROM dishes WHERE id = :i AND restaurant_id = :r"),
                     {"i": did, "r": user["restaurant_id"]}).first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy món")
    db.execute(text("UPDATE dishes SET image_url = NULL WHERE id = :i"), {"i": did})
    db.commit()
    _remove_file(row[0])
    return _get_dish(db, user["restaurant_id"], did)


def _remove_file(url: str | None) -> None:
    if url and url.startswith("/api/uploads/dishes/"):
        p = Path(_cfg.upload_dir) / "dishes" / Path(url).name
        p.unlink(missing_ok=True)
