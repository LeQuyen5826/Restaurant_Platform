"""Schema ban đầu (25 bảng) từ db/schema.sql

Revision ID: 0001
Revises:
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def upgrade() -> None:
    # Không truyền tham số -> psycopg dùng simple query protocol, chạy được nhiều câu lệnh.
    raw = op.get_bind().connection
    with raw.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))


def downgrade() -> None:
    raw = op.get_bind().connection
    with raw.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
