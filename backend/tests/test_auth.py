import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import seed

pytestmark = pytest.mark.integration

client = TestClient(app)
PW = "demo1234"


@pytest.fixture(scope="session", autouse=True)
def _seed():
    seed.run()


def login(email, pw=PW):
    return client.post("/api/auth/login", json={"email": email, "password": pw})


def auth(email):
    return {"Authorization": f"Bearer {login(email).json()['token']}"}


@pytest.mark.parametrize("email,role", [
    ("khach@demo.vn", "customer"), ("quanly@demo.vn", "manager"),
    ("phucvu@demo.vn", "waiter"), ("bep@demo.vn", "kitchen"),
])
def test_login_each_role(email, role):
    r = login(email)
    assert r.status_code == 200
    assert r.json()["user"]["role"] == role


def test_wrong_password():
    assert login("khach@demo.vn", "sai-mat-khau").status_code == 401


def test_me_requires_token():
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth("bep@demo.vn")).json()["role"] == "kitchen"


def test_register_customer_and_duplicate():
    mail = f"{uuid.uuid4().hex[:8]}@test.vn"
    body = {"full_name": "A", "email": mail, "password": "matkhau123"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json={**body, "email": mail.upper()}).status_code == 409


def test_staff_only_manager():
    assert client.get("/api/staff", headers=auth("phucvu@demo.vn")).status_code == 403
    assert client.get("/api/staff", headers=auth("khach@demo.vn")).status_code == 403
    r = client.get("/api/staff", headers=auth("quanly@demo.vn"))
    assert r.status_code == 200 and len(r.json()) >= 3


def test_manager_creates_staff_in_own_restaurant():
    mail = f"{uuid.uuid4().hex[:8]}@staff.vn"
    h = auth("quanly@demo.vn")
    r = client.post("/api/staff", headers=h, json={"full_name": "B", "email": mail, "password": "matkhau123", "role": "waiter"})
    assert r.status_code == 201
    assert login(mail, "matkhau123").json()["user"]["restaurant_id"] is not None
    bad = client.post("/api/staff", headers=h, json={"full_name": "C", "email": "c@x.vn", "password": "matkhau123", "role": "customer"})
    assert bad.status_code == 422
