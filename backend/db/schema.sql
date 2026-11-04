-- =====================================================================
-- Nền tảng đặt bàn nhà hàng + gợi ý món: schema PostgreSQL 14+
-- Chạy: psql -v ON_ERROR_STOP=1 -f schema.sql <tên_db>
-- Tiền tệ: VND, kiểu bigint (không có phần thập phân).
-- Thời gian: timestamptz (lưu UTC, hiển thị theo Asia/Ho_Chi_Minh).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;   -- cho EXCLUDE trên (uuid, tstzrange)

-- ---------------------------------------------------------------------
-- Kiểu liệt kê
-- ---------------------------------------------------------------------
CREATE TYPE user_role          AS ENUM ('customer', 'manager', 'waiter', 'kitchen');
CREATE TYPE reservation_status AS ENUM ('pending_deposit', 'confirmed', 'seated',
                                        'completed', 'cancelled', 'expired', 'no_show');
CREATE TYPE payment_purpose    AS ENUM ('deposit', 'bill');
CREATE TYPE payment_status     AS ENUM ('pending', 'paid', 'expired', 'cancelled');
CREATE TYPE tx_match_status    AS ENUM ('matched', 'unmatched', 'underpaid', 'overpaid', 'late');
CREATE TYPE refund_status      AS ENUM ('pending', 'done');
CREATE TYPE session_status     AS ENUM ('open', 'closed');
CREATE TYPE order_item_status  AS ENUM ('new', 'preparing', 'ready', 'served', 'cancelled');
CREATE TYPE interaction_type   AS ENUM ('view', 'add_to_cart', 'order', 'reorder', 'rating');
CREATE TYPE rec_algo           AS ENUM ('popularity', 'content');
CREATE TYPE consent_purpose    AS ENUM ('personalization');

-- Hàm cập nhật updated_at
CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------------
-- 1. Nhà hàng, người dùng
-- ---------------------------------------------------------------------
CREATE TABLE restaurants (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                  text    NOT NULL,
    address               text,
    phone                 text,
    slot_minutes          integer NOT NULL DEFAULT 30  CHECK (slot_minutes > 0),
    dining_minutes        integer NOT NULL DEFAULT 90  CHECK (dining_minutes > 0),  -- độ dài một bữa
    turn_buffer_minutes   integer NOT NULL DEFAULT 15  CHECK (turn_buffer_minutes >= 0), -- đệm dọn bàn
    deposit_amount        bigint  NOT NULL DEFAULT 0   CHECK (deposit_amount >= 0),
    deposit_hold_minutes  integer NOT NULL DEFAULT 15  CHECK (deposit_hold_minutes > 0),
    free_cancel_hours     integer NOT NULL DEFAULT 24  CHECK (free_cancel_hours >= 0),
    bank_code             text,            -- tài khoản nhận tiền (không phải khóa bí mật)
    bank_account_number   text,
    bank_account_name     text,
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid REFERENCES restaurants(id),      -- chỉ nhân sự có giá trị
    role           user_role NOT NULL DEFAULT 'customer',
    email          text,
    phone          text,
    password_hash  text NOT NULL,
    full_name      text NOT NULL,
    is_active      boolean NOT NULL DEFAULT true,
    created_at     timestamptz NOT NULL DEFAULT now(),
    last_login_at  timestamptz,
    CONSTRAINT users_contact_chk CHECK (email IS NOT NULL OR phone IS NOT NULL),
    CONSTRAINT users_staff_restaurant_chk CHECK (role = 'customer' OR restaurant_id IS NOT NULL)
);
CREATE UNIQUE INDEX users_email_uq ON users (lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX users_phone_uq ON users (phone)        WHERE phone IS NOT NULL;
CREATE INDEX users_restaurant_role_idx ON users (restaurant_id, role);

CREATE TABLE restaurant_certificates (         -- chứng nhận an toàn thực phẩm (FR-11)
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name           text NOT NULL,
    number         text,
    issued_by      text,
    expires_on     date,
    file_url       text
);

-- ---------------------------------------------------------------------
-- 2. Khu vực, bàn, giờ mở cửa
-- ---------------------------------------------------------------------
CREATE TABLE areas (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name           text NOT NULL,
    UNIQUE (restaurant_id, name)
);

CREATE TABLE dining_tables (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    area_id        uuid REFERENCES areas(id) ON DELETE SET NULL,
    code           text    NOT NULL,                       -- ví dụ "A01", in trên mã QR
    capacity       integer NOT NULL CHECK (capacity > 0),
    min_party      integer NOT NULL DEFAULT 1,
    is_active      boolean NOT NULL DEFAULT true,
    UNIQUE (restaurant_id, code),
    CONSTRAINT dining_tables_party_chk CHECK (min_party >= 1 AND min_party <= capacity)
);

CREATE TABLE service_windows (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    weekday        smallint NOT NULL CHECK (weekday BETWEEN 1 AND 7),   -- ISO: 1 = thứ hai
    open_time      time NOT NULL,
    close_time     time NOT NULL,
    CHECK (close_time > open_time),
    UNIQUE (restaurant_id, weekday, open_time)
);

-- ---------------------------------------------------------------------
-- 3. Thực đơn
-- ---------------------------------------------------------------------
CREATE TABLE menu_categories (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    name           text NOT NULL,
    sort_order     integer NOT NULL DEFAULT 0,
    UNIQUE (restaurant_id, name)
);

CREATE TABLE allergens (
    code  text PRIMARY KEY,
    name  text NOT NULL
);

CREATE TABLE dishes (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
    category_id    uuid REFERENCES menu_categories(id) ON DELETE SET NULL,
    name           text    NOT NULL,
    description    text,
    price_vnd      bigint  NOT NULL CHECK (price_vnd >= 0),
    image_url      text,
    spiciness      smallint NOT NULL DEFAULT 0 CHECK (spiciness BETWEEN 0 AND 3),
    is_vegetarian  boolean NOT NULL DEFAULT false,
    cuisine        text,
    tags           text[]  NOT NULL DEFAULT '{}',
    ingredients    text[]  NOT NULL DEFAULT '{}',
    meal_periods   text[]  NOT NULL DEFAULT '{breakfast,lunch,dinner}',
    is_available   boolean NOT NULL DEFAULT true,    -- false = hết món (bếp đánh dấu)
    is_active      boolean NOT NULL DEFAULT true,    -- false = ẩn khỏi thực đơn
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (restaurant_id, name),
    CONSTRAINT dishes_meal_periods_chk CHECK (meal_periods <@ ARRAY['breakfast','lunch','dinner'])
);
CREATE INDEX dishes_tags_gin ON dishes USING gin (tags);
CREATE INDEX dishes_menu_idx ON dishes (restaurant_id, category_id) WHERE is_active;
CREATE TRIGGER dishes_updated_at BEFORE UPDATE ON dishes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE dish_allergens (
    dish_id        uuid NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    allergen_code  text NOT NULL REFERENCES allergens(code),
    PRIMARY KEY (dish_id, allergen_code)
);

-- ---------------------------------------------------------------------
-- 4. Khẩu vị và đồng ý cá nhân hóa
-- ---------------------------------------------------------------------
CREATE TABLE taste_profiles (
    user_id           uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    spice_level       smallint CHECK (spice_level BETWEEN 0 AND 3),
    diet              text,                       -- ví dụ: none, vegetarian, vegan
    favorite_cuisines text[] NOT NULL DEFAULT '{}',
    budget_min        bigint CHECK (budget_min >= 0),
    budget_max        bigint CHECK (budget_max >= budget_min),
    allergens_enc     bytea,                      -- danh sách dị ứng, MÃ HÓA ở tầng ứng dụng
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER taste_profiles_updated_at BEFORE UPDATE ON taste_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE consents (                           -- nhật ký chỉ thêm, không sửa
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose         consent_purpose NOT NULL,
    granted         boolean NOT NULL,
    policy_version  text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX consents_latest_idx ON consents (user_id, purpose, created_at DESC);

-- Trạng thái đồng ý hiện tại = bản ghi mới nhất của mỗi (user, purpose)
CREATE VIEW current_consents AS
SELECT DISTINCT ON (user_id, purpose) user_id, purpose, granted, policy_version, created_at
FROM consents
ORDER BY user_id, purpose, created_at DESC, id DESC;

-- ---------------------------------------------------------------------
-- 5. Đặt bàn
-- ---------------------------------------------------------------------
CREATE TABLE reservations (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id  uuid NOT NULL REFERENCES restaurants(id),
    user_id        uuid REFERENCES users(id),
    guest_name     text,
    guest_phone    text,
    party_size     integer NOT NULL CHECK (party_size > 0),
    starts_at      timestamptz NOT NULL,
    ends_at        timestamptz NOT NULL,
    status         reservation_status NOT NULL DEFAULT 'pending_deposit',
    expires_at     timestamptz,                    -- hạn giữ chỗ khi chờ cọc
    note           text,
    created_by     uuid REFERENCES users(id),      -- nhân viên tạo hộ khách (nếu có)
    checked_in_at  timestamptz,
    cancelled_at   timestamptz,
    cancel_reason  text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at),
    CONSTRAINT reservations_who_chk CHECK (user_id IS NOT NULL OR (guest_name IS NOT NULL AND guest_phone IS NOT NULL)),
    CONSTRAINT reservations_hold_chk CHECK (status <> 'pending_deposit' OR expires_at IS NOT NULL)
);
CREATE INDEX reservations_day_idx  ON reservations (restaurant_id, starts_at);
CREATE INDEX reservations_user_idx ON reservations (user_id, starts_at DESC);
CREATE INDEX reservations_hold_idx ON reservations (expires_at) WHERE status = 'pending_deposit';
CREATE TRIGGER reservations_updated_at BEFORE UPDATE ON reservations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Một đặt bàn giữ 1..n bàn. Ràng buộc loại trừ là chốt chặn chống đặt trùng.
-- "during" = [starts_at, ends_at + turn_buffer), do tầng ứng dụng tính khi tạo.
CREATE TABLE reservation_tables (
    reservation_id  uuid NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
    table_id        uuid NOT NULL REFERENCES dining_tables(id),
    during          tstzrange NOT NULL,
    is_active       boolean NOT NULL DEFAULT true,   -- false khi hủy, hết hạn, no-show, hoàn tất
    PRIMARY KEY (reservation_id, table_id),
    CHECK (NOT isempty(during) AND lower_inf(during) = false AND upper_inf(during) = false),
    CONSTRAINT reservation_tables_no_overlap
        EXCLUDE USING gist (table_id WITH =, during WITH &&) WHERE (is_active)
);
CREATE INDEX reservation_tables_table_idx ON reservation_tables (table_id);

-- Tự nhả bàn khi đặt bàn chuyển sang trạng thái kết thúc
CREATE FUNCTION release_tables_on_final_status() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IN ('cancelled', 'expired', 'no_show', 'completed')
       AND OLD.status IS DISTINCT FROM NEW.status THEN
        UPDATE reservation_tables SET is_active = false WHERE reservation_id = NEW.id;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER reservations_release_tables AFTER UPDATE OF status ON reservations
    FOR EACH ROW EXECUTE FUNCTION release_tables_on_final_status();

-- ---------------------------------------------------------------------
-- 6. Phiên bàn (QR), giỏ chung, order
-- ---------------------------------------------------------------------
CREATE TABLE dining_sessions (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id     uuid NOT NULL REFERENCES restaurants(id),
    table_id          uuid NOT NULL REFERENCES dining_tables(id),
    reservation_id    uuid REFERENCES reservations(id),
    status            session_status NOT NULL DEFAULT 'open',
    opened_by         uuid NOT NULL REFERENCES users(id),
    token_hash        text NOT NULL,                  -- SHA-256 của token phiên, không lưu token
    token_expires_at  timestamptz NOT NULL,
    opened_at         timestamptz NOT NULL DEFAULT now(),
    closed_at         timestamptz,
    closed_by         uuid REFERENCES users(id),
    CONSTRAINT dining_sessions_closed_chk CHECK ((status = 'open') = (closed_at IS NULL))
);
CREATE UNIQUE INDEX dining_sessions_one_open_per_table ON dining_sessions (table_id) WHERE status = 'open';
CREATE UNIQUE INDEX dining_sessions_one_per_reservation ON dining_sessions (reservation_id) WHERE reservation_id IS NOT NULL;
CREATE INDEX dining_sessions_token_idx ON dining_sessions (token_hash);

CREATE TABLE session_guests (                       -- "ai gọi món nào" để chia bill
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    uuid NOT NULL REFERENCES dining_sessions(id) ON DELETE CASCADE,
    user_id       uuid REFERENCES users(id),        -- null = khách ẩn danh
    display_name  text NOT NULL,
    joined_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX session_guests_session_idx ON session_guests (session_id);

-- ---------------------------------------------------------------------
-- 7. Thanh toán VietQR (cọc và hóa đơn)
-- ---------------------------------------------------------------------
CREATE TABLE payments (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id    uuid NOT NULL REFERENCES restaurants(id),
    purpose          payment_purpose NOT NULL,
    reservation_id   uuid REFERENCES reservations(id),
    session_id       uuid REFERENCES dining_sessions(id),
    code             text NOT NULL UNIQUE,            -- mã ngẫu nhiên đặt vào nội dung chuyển khoản
    expected_amount  bigint NOT NULL CHECK (expected_amount > 0),
    paid_amount      bigint CHECK (paid_amount >= 0),
    status           payment_status NOT NULL DEFAULT 'pending',
    expires_at       timestamptz NOT NULL,
    paid_at          timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT payments_target_chk CHECK (
        (purpose = 'deposit' AND reservation_id IS NOT NULL AND session_id IS NULL) OR
        (purpose = 'bill'    AND session_id IS NOT NULL    AND reservation_id IS NULL))
);
CREATE UNIQUE INDEX payments_one_live_deposit ON payments (reservation_id)
    WHERE purpose = 'deposit' AND status IN ('pending', 'paid');
CREATE INDEX payments_pending_idx ON payments (expires_at) WHERE status = 'pending';

-- Mọi giao dịch ngân hàng nhận từ webhook. UNIQUE chống xử lý trùng khi nhà cung cấp gửi lại.
CREATE TABLE bank_transactions (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider         text   NOT NULL DEFAULT 'sepay',
    provider_tx_id   text   NOT NULL,
    account_number   text,
    transfer_type    text   NOT NULL CHECK (transfer_type IN ('in', 'out')),
    amount           bigint NOT NULL CHECK (amount >= 0),
    content          text,
    extracted_code   text,                           -- mã thanh toán tách từ nội dung
    occurred_at      timestamptz,
    raw              jsonb  NOT NULL,
    payment_id       uuid REFERENCES payments(id),
    match_status     tx_match_status NOT NULL DEFAULT 'unmatched',
    handled_by       uuid REFERENCES users(id),
    handled_note     text,
    received_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_tx_id)
);
CREATE INDEX bank_transactions_unresolved_idx ON bank_transactions (received_at)
    WHERE match_status <> 'matched';
CREATE INDEX bank_transactions_payment_idx ON bank_transactions (payment_id);

CREATE TABLE refunds (                               -- hoàn thủ công, hệ thống chỉ ghi vết
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id    uuid NOT NULL REFERENCES payments(id),
    amount        bigint NOT NULL CHECK (amount > 0),
    reason        text,
    status        refund_status NOT NULL DEFAULT 'pending',
    requested_by  uuid NOT NULL REFERENCES users(id),
    done_by       uuid REFERENCES users(id),
    done_at       timestamptz,
    bank_ref      text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'done') = (done_at IS NOT NULL))
);

-- ---------------------------------------------------------------------
-- 8. Giỏ chung, order và món
-- ---------------------------------------------------------------------
CREATE TABLE cart_items (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  uuid NOT NULL REFERENCES dining_sessions(id) ON DELETE CASCADE,
    guest_id    uuid NOT NULL REFERENCES session_guests(id) ON DELETE CASCADE,
    dish_id     uuid NOT NULL REFERENCES dishes(id),
    quantity    smallint NOT NULL CHECK (quantity BETWEEN 1 AND 99),
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (guest_id, dish_id)
);
CREATE INDEX cart_items_session_idx ON cart_items (session_id);

CREATE TABLE orders (                                -- một lần "gửi món" từ giỏ
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  uuid NOT NULL REFERENCES dining_sessions(id),
    sent_by     uuid REFERENCES session_guests(id),
    sent_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX orders_session_idx ON orders (session_id, sent_at);

CREATE TABLE order_items (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id           uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    dish_id            uuid NOT NULL REFERENCES dishes(id),
    guest_id           uuid REFERENCES session_guests(id),
    dish_name          text   NOT NULL,              -- ảnh chụp tại thời điểm gọi
    unit_price_vnd     bigint NOT NULL CHECK (unit_price_vnd >= 0),
    quantity           smallint NOT NULL CHECK (quantity BETWEEN 1 AND 99),
    note               text,                         -- gồm ghi chú dị ứng khách nhập cho bếp
    status             order_item_status NOT NULL DEFAULT 'new',
    status_changed_at  timestamptz NOT NULL DEFAULT now(),
    status_changed_by  uuid REFERENCES users(id),
    cancel_reason      text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT order_items_cancel_chk CHECK (status <> 'cancelled' OR cancel_reason IS NOT NULL)
);
CREATE INDEX order_items_order_idx  ON order_items (order_id);
CREATE INDEX order_items_active_idx ON order_items (status, created_at)
    WHERE status IN ('new', 'preparing', 'ready');
CREATE INDEX order_items_dish_idx   ON order_items (dish_id);

-- ---------------------------------------------------------------------
-- 9. Gợi ý món
-- ---------------------------------------------------------------------
CREATE TABLE interactions (                          -- chỉ ghi khi có đồng ý cá nhân hóa
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     uuid REFERENCES users(id) ON DELETE CASCADE,
    session_id  uuid REFERENCES dining_sessions(id) ON DELETE SET NULL,
    dish_id     uuid NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    event_type  interaction_type NOT NULL,
    weight      real NOT NULL,
    rating      smallint CHECK (rating BETWEEN 1 AND 5),
    context     jsonb NOT NULL DEFAULT '{}',         -- khung giờ, ngày trong tuần, số khách
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK (user_id IS NOT NULL OR session_id IS NOT NULL),
    CHECK ((event_type = 'rating') = (rating IS NOT NULL))
);
CREATE INDEX interactions_user_idx ON interactions (user_id, created_at DESC);
CREATE INDEX interactions_dish_idx ON interactions (dish_id, created_at DESC);

CREATE TABLE recommendations (                       -- mọi lần hiển thị gợi ý, để đánh giá
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id   uuid REFERENCES dining_sessions(id) ON DELETE SET NULL,
    user_id      uuid REFERENCES users(id) ON DELETE CASCADE,
    dish_id      uuid NOT NULL REFERENCES dishes(id) ON DELETE CASCADE,
    algo         rec_algo NOT NULL,
    rank         smallint NOT NULL CHECK (rank > 0),
    score        real,
    reason_code  text NOT NULL,                      -- ví dụ: popular_lunch, taste_match_spice
    reason_params jsonb NOT NULL DEFAULT '{}',
    shown_at     timestamptz NOT NULL DEFAULT now(),
    accepted_at  timestamptz                         -- có giá trị = khách đã gọi món này
);
CREATE INDEX recommendations_eval_idx ON recommendations (algo, shown_at);
CREATE INDEX recommendations_user_idx ON recommendations (user_id, shown_at DESC);

-- Độ phổ biến theo bữa, giảm dần theo thời gian (bán rã 14 ngày). Mức 0 dùng view này.
CREATE MATERIALIZED VIEW mv_dish_popularity AS
SELECT oi.dish_id,
       CASE WHEN extract(hour FROM o.sent_at AT TIME ZONE 'Asia/Ho_Chi_Minh') < 10 THEN 'breakfast'
            WHEN extract(hour FROM o.sent_at AT TIME ZONE 'Asia/Ho_Chi_Minh') < 15 THEN 'lunch'
            ELSE 'dinner' END AS meal_period,
       sum(oi.quantity * exp(-extract(epoch FROM (now() - o.sent_at)) / (14 * 86400.0)))::real AS score
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
WHERE oi.status <> 'cancelled' AND o.sent_at > now() - interval '60 days'
GROUP BY 1, 2;
CREATE UNIQUE INDEX mv_dish_popularity_uq ON mv_dish_popularity (dish_id, meal_period);

-- ---------------------------------------------------------------------
-- 10. Nhật ký thao tác nhạy cảm
-- ---------------------------------------------------------------------
CREATE TABLE audit_logs (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id    uuid REFERENCES users(id) ON DELETE SET NULL,
    action      text NOT NULL,                       -- ví dụ: refund.mark_done, user.export
    entity      text,
    entity_id   text,
    data        jsonb NOT NULL DEFAULT '{}',         -- không ghi dị ứng hay khẩu vị
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_logs_actor_idx  ON audit_logs (actor_id, created_at DESC);
CREATE INDEX audit_logs_entity_idx ON audit_logs (entity, entity_id);

-- ---------------------------------------------------------------------
-- Dữ liệu nền: danh mục chất gây dị ứng
-- ---------------------------------------------------------------------
INSERT INTO allergens (code, name) VALUES
    ('peanut',     'Đậu phộng (lạc)'),
    ('tree_nut',   'Hạt cây (hạnh nhân, điều, óc chó)'),
    ('crustacean', 'Giáp xác (tôm, cua)'),
    ('mollusc',    'Nhuyễn thể (mực, ốc, sò)'),
    ('fish',       'Cá'),
    ('egg',        'Trứng'),
    ('milk',       'Sữa'),
    ('soy',        'Đậu nành'),
    ('gluten',     'Gluten (lúa mì)'),
    ('sesame',     'Mè (vừng)');
