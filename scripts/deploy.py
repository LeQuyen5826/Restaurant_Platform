"""CD: dựng và chạy phiên bản mới bằng Docker Compose, kiểm tra sống, tự quay về bản cũ nếu hỏng.

Chạy bởi Jenkins (stage Deploy, chỉ nhánh main) hoặc chạy tay: python scripts/deploy.py
Chỉ dùng thư viện chuẩn của Python.
"""
import argparse
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = ROOT / "docker-compose.deploy.yml"
PROJECT = "rbprod"
IMAGES = ["rbprod-backend", "rbprod-web"]


def default_env_file() -> Path:
    home = os.environ.get("JENKINS_HOME")
    return (Path(home) if home else Path.home()) / "rb-deploy.env"


def ensure_env_file(path: Path) -> None:
    """Tạo file cấu hình với mật khẩu ngẫu nhiên nếu chưa có. Không ghi đè file đã có (đổi mật khẩu DB sẽ hỏng volume)."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"JWT_SECRET={secrets.token_urlsafe(48)}\n"
        f"DB_PASSWORD={secrets.token_urlsafe(24)}\n"
        "WEB_PORT=8090\n"
        "CORS_ORIGINS=http://localhost:8090\n"
        "SEED_DEMO=1\n",
        encoding="utf-8",
    )
    print(f"Đã tạo file cấu hình mới: {path}")


def read_env(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def run(cmd, check=True, capture=False):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture)
    if capture and r.stdout:
        print(r.stdout)
    if check and r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, cmd)
    return r


def compose(env_file: Path, *args, check=True):
    return run(["docker", "compose", "-p", PROJECT, "-f", str(COMPOSE_FILE), "--env-file", str(env_file), *args], check=check)


def image_exists(name: str, tag: str = "latest") -> bool:
    return subprocess.run(["docker", "image", "inspect", f"{name}:{tag}"], capture_output=True).returncode == 0


def http_get(url: str, timeout: float = 5.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception:
        return 0, ""


def smoke_test(base: str, tries: int = 30, wait: float = 2.0) -> bool:
    """Qua nginx của web: trang chủ, health của API, và một API đọc database."""
    checks = [("/", "<div id=\"root\">"), ("/api/health", "ok"), ("/api/public/home", "")]
    for _ in range(tries):
        results = [http_get(base + p) for p, _ in checks]
        if all(code == 200 and key in body for (code, body), (_, key) in zip(results, checks)):
            return True
        time.sleep(wait)
    return False


def rollback(env_file: Path) -> bool:
    if not all(image_exists(i, "previous") for i in IMAGES):
        print("Chưa có bản cũ để quay về (đây là lần deploy đầu).")
        return False
    for i in IMAGES:
        run(["docker", "tag", f"{i}:previous", f"{i}:latest"])
    compose(env_file, "up", "-d", "--no-build", "--wait", check=False)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", type=Path, default=default_env_file())
    ap.add_argument("--tries", type=int, default=30)
    a = ap.parse_args()

    ensure_env_file(a.env_file)
    cfg = read_env(a.env_file)
    base = f"http://localhost:{cfg.get('WEB_PORT', '8090')}"

    for i in IMAGES:  # giữ bản đang chạy làm bản dự phòng
        if image_exists(i):
            run(["docker", "tag", f"{i}:latest", f"{i}:previous"])

    try:
        compose(a.env_file, "build")
        compose(a.env_file, "up", "-d", "--wait")
        ok = smoke_test(base, tries=a.tries)
    except subprocess.CalledProcessError as e:
        print(f"Lệnh Docker lỗi (mã {e.returncode}).")
        ok = False

    if ok:
        run(["docker", "image", "prune", "-f"], check=False)
        print(f"DEPLOY THÀNH CÔNG: {base}")
        return 0

    print("DEPLOY THẤT BẠI: xem log backend bên dưới.")
    compose(a.env_file, "logs", "--tail", "60", "backend", check=False)
    if rollback(a.env_file):
        print("Đã quay về bản trước đó." if smoke_test(base, tries=10) else "Quay về bản cũ nhưng vẫn không sống, cần kiểm tra tay.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
