"""Hai loại đặt bàn, mã check-in, món đặt trước, cọc theo %, thông tin công khai của nhà hàng

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = """
ALTER TABLE restaurants
    ADD COLUMN tagline            text,
    ADD COLUMN about              text,
    ADD COLUMN email              text,
    ADD COLUMN facebook_url       text,
    ADD COLUMN tiktok_url         text,
    ADD COLUMN instagram_url      text,
    ADD COLUMN youtube_url        text,
    ADD COLUMN zalo_url           text,
    ADD COLUMN map_url            text,
    ADD COLUMN deposit_percent    integer NOT NULL DEFAULT 30 CHECK (deposit_percent BETWEEN 0 AND 100),
    ADD COLUMN late_grace_minutes integer NOT NULL DEFAULT 15 CHECK (late_grace_minutes >= 0);
-- từ nay deposit_amount là mức cọc tối thiểu; free_cancel_hours mặc định 2 giờ
ALTER TABLE restaurants ALTER COLUMN free_cancel_hours SET DEFAULT 2;
UPDATE restaurants SET free_cancel_hours = 2 WHERE free_cancel_hours = 24;
UPDATE restaurants SET deposit_amount = 100000 WHERE deposit_amount = 0;

CREATE TABLE restaurant_services (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    title          text NOT NULL,
    description    text,
    icon           text,
    sort_order     integer NOT NULL DEFAULT 0
);
CREATE INDEX restaurant_services_idx ON restaurant_services (restaurant_id, sort_order);

ALTER TABLE reservations
    ADD COLUMN kind            text   NOT NULL DEFAULT 'table_only' CHECK (kind IN ('table_only', 'with_food')),
    ADD COLUMN service_request text,
    ADD COLUMN checkin_code    text,
    ADD COLUMN deposit_amount  bigint NOT NULL DEFAULT 0 CHECK (deposit_amount >= 0);
CREATE UNIQUE INDEX reservations_checkin_code_idx ON reservations (checkin_code) WHERE checkin_code IS NOT NULL;
UPDATE reservations SET checkin_code = upper(substr(md5(id::text), 1, 8)) WHERE checkin_code IS NULL;

CREATE TABLE reservation_items (                       -- món đặt trước (loại with_food)
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id  uuid NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
    dish_id         uuid NOT NULL REFERENCES dishes(id),
    dish_name       text   NOT NULL,
    unit_price_vnd  bigint NOT NULL CHECK (unit_price_vnd >= 0),
    quantity        smallint NOT NULL CHECK (quantity BETWEEN 1 AND 99),
    note            text,
    UNIQUE (reservation_id, dish_id)
);
"""


def upgrade() -> None:
    op.get_bind().connection.cursor().execute(SQL)


def downgrade() -> None:
    op.get_bind().connection.cursor().execute("""
        DROP TABLE reservation_items;
        DROP INDEX reservations_checkin_code_idx;
        ALTER TABLE reservations DROP COLUMN kind, DROP COLUMN service_request, DROP COLUMN checkin_code, DROP COLUMN deposit_amount;
        DROP TABLE restaurant_services;
        ALTER TABLE restaurants DROP COLUMN tagline, DROP COLUMN about, DROP COLUMN email, DROP COLUMN facebook_url,
            DROP COLUMN tiktok_url, DROP COLUMN instagram_url, DROP COLUMN youtube_url, DROP COLUMN zalo_url,
            DROP COLUMN map_url, DROP COLUMN deposit_percent, DROP COLUMN late_grace_minutes;
    """)
