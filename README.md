# Nền tảng đặt bàn nhà hàng + gợi ý món

React/TypeScript (web) + FastAPI + PostgreSQL. Thiết kế chi tiết: xem tài liệu "Thiết kế hệ thống và cơ sở dữ liệu".

## Chạy nhanh (Docker)
```bash
docker compose up --build
```
- PostgreSQL trong Docker dùng cổng máy 5433 (tránh trùng PostgreSQL cài sẵn trên máy)
- Web: http://localhost:8080 · API docs: http://localhost:8000/docs
- Container backend tự chạy `alembic upgrade head` rồi seed dữ liệu mẫu. Ảnh món lưu trong volume `uploads`.

## Chạy dev không Docker
```bash
# 1. PostgreSQL: docker compose up db -d (cổng 5433)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
alembic upgrade head          # chạy migration 0001 (25 bảng) và 0002 (loại đặt bàn, mã check-in, dịch vụ...)
python -m app.seed            # dữ liệu mẫu
uvicorn app.main:app --reload
pytest                        # cần DB đang chạy; 33 test

# 2. Frontend (terminal khác)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Tài khoản mẫu (mật khẩu `demo1234`)
| Vai trò | Email | Trang sau đăng nhập |
|---|---|---|
| Quản lý | quanly@demo.vn | /quan-ly/tong-quan |
| Phục vụ | phucvu@demo.vn | /phuc-vu |
| Bếp | bep@demo.vn | /bep |
| Khách | khach@demo.vn | / |

Khách cũng có thể tự đăng ký tại trang Đăng nhập. Chạy lại `python -m app.seed` để đặt lại mật khẩu mẫu và bổ sung dữ liệu còn thiếu.

## Luồng hoạt động
1. **Chưa đăng nhập** chỉ có 4 trang: Trang chủ `/`, Món ăn `/mon-an`, Dịch vụ `/dich-vu`, Liên hệ `/lien-he`.
2. **Đặt bàn** `/dat-ban` (phải đăng nhập): xem bàn còn trống theo khung giờ, chọn một trong hai loại:
   - *Đặt bàn, đến rồi chọn món*: không cọc, giữ chỗ ngay.
   - *Đặt bàn kèm món và dịch vụ*: chọn món, ghi yêu cầu (sinh nhật, sự kiện), **đặt cọc 30% giá trị món (tối thiểu 100.000đ)**, giữ chỗ 15 phút.
3. Quản lý bấm **Đã nhận cọc** (trang Đặt bàn) khi thấy tiền về. Khách nhận **mã QR check-in** ở `/dat-ban/:id`. Webhook SePay sẽ thay bước bấm tay này ở bước thanh toán.
4. Khách đến quán: phục vụ vào **Check-in**, quét QR hoặc nhập mã. Hệ thống mở đúng bàn đã giữ và **gửi món đặt trước xuống bếp**. Điện thoại khách tự chuyển sang `/goi-mon` để chọn thêm món.
5. **Khách chưa đặt trước**: phục vụ vào **Khách vãng lai**, nhập số khách, hệ thống gợi ý bàn trống rồi xếp bàn. Khách quét QR dán ở bàn (`/ban/<mã>`) để gọi món.
6. Món gửi xuống **bếp** (`/bep`), bếp bấm *Bắt đầu / Xong*. Món xong hiện ngay ở **Món chờ ra** của phục vụ kèm số bàn, phục vụ bấm *Đã mang ra*.
7. Đóng bàn: hóa đơn tự trừ tiền cọc.

Quy tắc cọc (đổi trong Quản lý > Cài đặt): hủy trước giờ hẹn 2 giờ thì hoàn cọc, hủy muộn hoặc vắng mặt thì mất cọc; sau giờ hẹn 15 phút nhân viên được ghi vắng mặt.

## Cấu trúc
```
backend/app/modules/   auth, restaurant (cài đặt, bàn, dịch vụ, tổng quan), menu, booking, dining
backend/alembic/       0001 nạp db/schema.sql, 0002 loại đặt bàn + thông tin công khai
frontend/src/pages/    public/ (4 trang), customer/ (đặt bàn, mã QR, gọi món), staff/ (phục vụ, bếp), manager/
```

## Chưa làm / lưu ý
- Thanh toán tự động VietQR + SePay webhook (hiện quản lý xác nhận cọc bằng tay), gợi ý món cá nhân hóa.
- Bếp và phục vụ cập nhật bằng polling 3 giây (chưa dùng WebSocket).
- Quét QR bằng camera trên trang Check-in cần HTTPS (localhost thì được) và trình duyệt Chrome; trình duyệt khác dùng ô nhập mã.
- Đổi `JWT_SECRET` và mật khẩu DB khi triển khai; xóa tài khoản seed.
- Mọi thay đổi schema sau này: thêm migration Alembic mới, không sửa 0001/0002.

<!-- thu CI -->

- Dat ban: ho tro 2 loai (chi ban, ban + mon).

<!-- Nam thu nhanh booking -->

## CD: tá»± Ä‘á»™ng deploy khi merge vÃ o main

Sau khi Pull Request Ä‘Æ°á»£c merge vÃ  nhÃ¡nh `main` xanh, stage **6. Deploy** trong `Jenkinsfile` cháº¡y `scripts/deploy.py`:

1. Giá»¯ image Ä‘ang cháº¡y lÃ m báº£n dá»± phÃ²ng (`:previous`).
2. Dá»±ng image má»›i vÃ  cháº¡y `docker-compose.deploy.yml` (project `rbprod`, tÃ¡ch khá»i mÃ´i trÆ°á»ng dev).
3. Kiá»ƒm tra sá»‘ng qua cá»•ng web: trang chá»§, `/api/health`, `/api/public/home` (Ä‘á»c database).
4. Há»ng thÃ¬ tá»± quay vá» báº£n trÆ°á»›c vÃ  bÃ¡o build FAILURE.

Truy cáº­p báº£n Ä‘ang cháº¡y: http://localhost:8090. Máº­t kháº©u ngáº«u nhiÃªn náº±m á»Ÿ file `rb-deploy.env` trong thÆ° má»¥c `JENKINS_HOME` (khÃ´ng náº±m trong Git). Cháº¡y tay: `python scripts/deploy.py`.
Äáº·t `SEED_DEMO=0` trong file Ä‘Ã³ Ä‘á»ƒ khÃ´ng náº¡p tÃ i khoáº£n demo. LÆ°u Ã½: quay vá» báº£n cÅ© khÃ´ng hoÃ n tÃ¡c migration database.

