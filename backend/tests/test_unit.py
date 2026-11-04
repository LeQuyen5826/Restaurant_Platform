"""Unit test: không cần database, chạy trong vài giây."""
import uuid

import pytest
from fastapi import HTTPException

from app.modules.booking.router import deposit_for, new_code
from app.modules.dining.router import parse_table_code, sign_table
from app.security import create_token, decode_token, hash_password, verify_password

pytestmark = pytest.mark.unit
RULE = {"deposit_percent": 30, "deposit_amount": 100_000}


def test_deposit_is_30_percent_rounded_up_to_thousand():
    assert deposit_for(500_000, RULE) == 150_000
    assert deposit_for(333_333, RULE) == 100_000  # 30% = 100.000 (làm tròn lên nghìn)
    assert deposit_for(1_000_001, RULE) == 301_000


def test_deposit_has_minimum_but_never_exceeds_food_total():
    assert deposit_for(200_000, RULE) == 100_000  # 30% = 60.000 < mức tối thiểu
    assert deposit_for(60_000, RULE) == 60_000    # không cọc quá tổng tiền món


def test_checkin_code_shape_and_uniqueness():
    codes = {new_code("BK", 6) for _ in range(200)}
    assert len(codes) == 200
    assert all(c.startswith("BK") and len(c) == 8 and c.isalnum() and c.upper() == c for c in codes)
    assert not any(ch in c[2:] for c in codes for ch in "IO01")


def test_table_qr_signature_roundtrip_and_tamper():
    tid = uuid.uuid4()
    assert parse_table_code(sign_table(tid)) == tid
    for bad in (f"{tid}.0000000000000000", "khong-phai-uuid.abc", f"{uuid.uuid4()}.{sign_table(tid).split('.')[1]}"):
        with pytest.raises(HTTPException) as e:
            parse_table_code(bad)
        assert e.value.status_code == 404


def test_password_hash_and_token():
    h = hash_password("demo1234")
    assert h != "demo1234" and verify_password("demo1234", h) and not verify_password("sai", h)
    claims = decode_token(create_token("u-1", "waiter"))
    assert claims["sub"] == "u-1" and claims["role"] == "waiter"
