import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import require_roles
from ...security import hash_password

router = APIRouter(prefix="/staff", tags=["staff"])


class StaffIn(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str  # waiter | kitchen | manager


@router.post("", status_code=201)
def create_staff(body: StaffIn, manager: dict = Depends(require_roles("manager")), db: Session = Depends(get_db)):
    if body.role not in ("waiter", "kitchen", "manager"):
        raise HTTPException(422, "role phải là waiter, kitchen hoặc manager")
    if len(body.password) < 8:
        raise HTTPException(422, "Mật khẩu tối thiểu 8 ký tự")
    uid = uuid.uuid4()
    try:
        db.execute(
            text(
                "INSERT INTO users (id, restaurant_id, role, email, password_hash, full_name) "
                "VALUES (:id, :r, CAST(:role AS user_role), :email, :pw, :name)"
            ),
            {"id": uid, "r": manager["restaurant_id"], "role": body.role, "email": body.email,
             "pw": hash_password(body.password), "name": body.full_name},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã tồn tại")
    return {"id": str(uid)}


@router.get("")
def list_staff(manager: dict = Depends(require_roles("manager")), db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT id, full_name, email, role, is_active FROM users WHERE restaurant_id = :r ORDER BY role, full_name"),
        {"r": manager["restaurant_id"]},
    ).mappings().all()
    return [{**dict(r), "id": str(r["id"])} for r in rows]
