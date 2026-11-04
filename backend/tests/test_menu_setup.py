import uuid

import pytest
from fastapi.testclient import TestClient

from app import seed
from app.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed.run()


def H(email):
    t = client.post("/api/auth/login", json={"email": email, "password": "demo1234"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def test_public_menu_has_sections_and_allergen_names():
    r = client.get("/api/public/menu")
    assert r.status_code == 200
    body = r.json()
    assert len(body["sections"]) >= 4
    dish = next(d for s in body["sections"] for d in s["dishes"] if d["name"] == "Gỏi cuốn tôm thịt")
    assert {"code": "peanut", "name": "Đậu phộng (lạc)"} in dish["allergens"]
    assert "is_active" not in dish


def test_setup_endpoints_role_rules():
    for role in ("khach@demo.vn",):
        assert client.get("/api/tables", headers=H(role)).status_code == 403
    assert client.get("/api/tables", headers=H("phucvu@demo.vn")).status_code == 200
    assert client.post("/api/tables", headers=H("phucvu@demo.vn"), json={"code": "Z1", "capacity": 2}).status_code == 403
    assert client.get("/api/tables").status_code == 401


def test_table_crud_and_rules():
    h = H("quanly@demo.vn")
    code = "T" + uuid.uuid4().hex[:5]
    r = client.post("/api/tables", headers=h, json={"code": code, "capacity": 4, "min_party": 2})
    assert r.status_code == 201
    tid = r.json()["id"]
    assert client.post("/api/tables", headers=h, json={"code": code, "capacity": 4}).status_code == 409
    assert client.post("/api/tables", headers=h, json={"code": code + "x", "capacity": 2, "min_party": 3}).status_code == 422
    r = client.put(f"/api/tables/{tid}", headers=h, json={"code": code, "capacity": 6, "min_party": 1, "is_active": False})
    assert r.json()["capacity"] == 6 and r.json()["is_active"] is False
    assert client.delete(f"/api/tables/{tid}", headers=h).status_code == 204
    assert client.delete(f"/api/tables/{tid}", headers=h).status_code == 404


def test_area_must_belong_to_restaurant():
    h = H("quanly@demo.vn")
    r = client.post("/api/tables", headers=h, json={"code": "Q" + uuid.uuid4().hex[:4], "capacity": 2, "area_id": str(uuid.uuid4())})
    assert r.status_code == 422


def test_service_windows_overlap_rejected_and_replace():
    h = H("quanly@demo.vn")
    before = client.get("/api/service-windows", headers=h).json()
    bad = [{"weekday": 1, "open_time": "10:00", "close_time": "14:00"}, {"weekday": 1, "open_time": "13:00", "close_time": "15:00"}]
    assert client.put("/api/service-windows", headers=h, json=bad).status_code == 422
    assert client.put("/api/service-windows", headers=h, json=[{"weekday": 1, "open_time": "15:00", "close_time": "14:00"}]).status_code == 422
    assert client.get("/api/service-windows", headers=h).json() == before  # lỗi không làm mất dữ liệu cũ
    ok = [{"weekday": 2, "open_time": "09:00", "close_time": "12:00"}]
    assert client.put("/api/service-windows", headers=h, json=ok).json() == [{"weekday": 2, "open_time": "09:00", "close_time": "12:00"}]
    client.put("/api/service-windows", headers=h, json=before)


def test_settings_update():
    h = H("quanly@demo.vn")
    s = client.get("/api/restaurant/settings", headers=h).json()
    s2 = {k: v for k, v in s.items() if k != "id"}
    s2["deposit_amount"] = 100000
    assert client.put("/api/restaurant/settings", headers=h, json=s2).json()["deposit_amount"] == 100000
    s2["slot_minutes"] = 0
    assert client.put("/api/restaurant/settings", headers=h, json=s2).status_code == 422
    s2.update(slot_minutes=s["slot_minutes"], deposit_amount=s["deposit_amount"])
    client.put("/api/restaurant/settings", headers=h, json=s2)


def test_dish_crud_allergens_and_availability():
    h = H("quanly@demo.vn")
    name = "Món thử " + uuid.uuid4().hex[:6]
    r = client.post("/api/menu/dishes", headers=h, json={"name": name, "price_vnd": 55000, "allergens": ["egg", "milk"], "spiciness": 2})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["allergens"] == ["egg", "milk"]
    assert client.post("/api/menu/dishes", headers=h, json={"name": name, "price_vnd": 1}).status_code == 409
    assert client.post("/api/menu/dishes", headers=h, json={"name": name + "2", "price_vnd": 1, "allergens": ["xyz"]}).status_code == 422
    assert client.post("/api/menu/dishes", headers=h, json={"name": name + "3", "price_vnd": 1, "meal_periods": ["brunch"]}).status_code == 422
    assert client.post("/api/menu/dishes", headers=h, json={"name": name + "4", "price_vnd": -5}).status_code == 422
    r = client.put(f"/api/menu/dishes/{d['id']}", headers=h, json={"name": name, "price_vnd": 60000, "allergens": ["fish"]})
    assert r.json()["price_vnd"] == 60000 and r.json()["allergens"] == ["fish"]
    # bếp đánh dấu hết món, nhưng không sửa được món
    kb = H("bep@demo.vn")
    r = client.patch(f"/api/menu/dishes/{d['id']}/availability", headers=kb, json={"is_available": False})
    assert r.status_code == 200 and r.json()["is_available"] is False
    assert client.put(f"/api/menu/dishes/{d['id']}", headers=kb, json={"name": "x", "price_vnd": 1}).status_code == 403
    assert client.patch(f"/api/menu/dishes/{d['id']}/availability", headers=H("phucvu@demo.vn"), json={"is_available": True}).status_code == 403
    # món ẩn không xuất hiện cho khách
    client.put(f"/api/menu/dishes/{d['id']}", headers=h, json={"name": name, "price_vnd": 60000, "is_active": False})
    names = [x["name"] for s in client.get("/api/public/menu").json()["sections"] for x in s["dishes"]]
    assert name not in names
    assert client.delete(f"/api/menu/dishes/{d['id']}", headers=h).status_code == 204


def test_category_delete_keeps_dishes():
    h = H("quanly@demo.vn")
    c = client.post("/api/menu/categories", headers=h, json={"name": "Thử " + uuid.uuid4().hex[:5]}).json()
    d = client.post("/api/menu/dishes", headers=h, json={"name": "Món " + uuid.uuid4().hex[:6], "price_vnd": 1, "category_id": c["id"]}).json()
    assert client.delete(f"/api/menu/categories/{c['id']}", headers=h).status_code == 204
    after = next(x for x in client.get("/api/menu/dishes", headers=h).json() if x["id"] == d["id"])
    assert after["category_id"] is None
    client.delete(f"/api/menu/dishes/{d['id']}", headers=h)
