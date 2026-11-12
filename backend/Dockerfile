FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# SEED_DEMO=1 (mặc định): nạp dữ liệu mẫu và tài khoản demo. Đặt 0 để tắt khi chạy thật.
CMD ["sh", "-c", "alembic upgrade head && if [ \"${SEED_DEMO:-1}\" = \"1\" ]; then python -m app.seed; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
