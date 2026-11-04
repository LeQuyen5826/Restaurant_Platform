import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import current_user
from ...security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _user_out(u: dict) -> dict:
    return {
        "id": str(u["id"]),
        "role": u["role"],
        "full_name": u["full_name"],
        "email": u.get("email"),
        "restaurant_id": str(u["restaurant_id"]) if u.get("restaurant_id") else None,
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Chỉ tạo tài khoản khách. Nhân sự do quản lý tạo (module restaurant)."""
    if len(body.password) < 8:
        raise HTTPException(422, "Mật khẩu tối thiểu 8 ký tự")
    uid = uuid.uuid4()
    try:
        db.execute(
            text(
                "INSERT INTO users (id, role, email, password_hash, full_name) "
                "VALUES (:id, 'customer', :email, :pw, :name)"
            ),
            {"id": uid, "email": body.email, "pw": hash_password(body.password), "name": body.full_name},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký")
    user = {"id": uid, "role": "customer", "restaurant_id": None, "full_name": body.full_name, "email": body.email}
    return {"id": str(uid), "token": create_token(str(uid), "customer"), "user": _user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT id, role, restaurant_id, full_name, email, password_hash, is_active "
            "FROM users WHERE lower(email) = lower(:e)"
        ),
        {"e": body.email},
    ).mappings().first()
    if not row or not row["is_active"] or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai email hoặc mật khẩu")
    db.execute(text("UPDATE users SET last_login_at = now() WHERE id = :id"), {"id": row["id"]})
    db.commit()
    return {"token": create_token(str(row["id"]), row["role"]), "user": _user_out(dict(row))}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _user_out(user)
