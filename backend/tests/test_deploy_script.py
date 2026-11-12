"""Unit test cho scripts/deploy.py (không cần Docker, không cần database)."""
import importlib.util
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SPEC = importlib.util.spec_from_file_location("deploy", Path(__file__).resolve().parents[2] / "scripts" / "deploy.py")
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def test_env_file_created_once_with_random_secrets(tmp_path):
    f = tmp_path / "sub" / "rb-deploy.env"
    deploy.ensure_env_file(f)
    first = deploy.read_env(f)
    assert len(first["JWT_SECRET"]) >= 40 and len(first["DB_PASSWORD"]) >= 20
    assert first["WEB_PORT"] == "8090"
    deploy.ensure_env_file(f)  # lần hai không được ghi đè (đổi mật khẩu DB sẽ hỏng volume)
    assert deploy.read_env(f) == first


def test_read_env_ignores_comments_and_blank_lines(tmp_path):
    f = tmp_path / "e.env"
    f.write_text("# ghi chú\n\nA=1\nB = 2 \nBAD\n", encoding="utf-8")
    assert deploy.read_env(f) == {"A": "1", "B": "2"}


class _Handler(BaseHTTPRequestHandler):
    healthy = True

    def do_GET(self):
        ok = type(self).healthy
        body = {"/": '<div id="root"></div>', "/api/health": '{"status":"ok"}', "/api/public/home": "{}"}.get(self.path, "")
        self.send_response(200 if ok and body else 500)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_smoke_test_passes_when_all_endpoints_ok(server):
    _Handler.healthy = True
    assert deploy.smoke_test(server, tries=2, wait=0)


def test_smoke_test_fails_when_server_unhealthy(server):
    _Handler.healthy = False
    assert not deploy.smoke_test(server, tries=2, wait=0)
    _Handler.healthy = True


def _fake(monkeypatch, tmp_path, images, smoke, compose_fail=False):
    calls = []
    monkeypatch.setattr(deploy, "run", lambda cmd, check=True, capture=False: calls.append(("run", cmd)))
    def fake_compose(env, *args, check=True):
        calls.append(("compose", args))
        if compose_fail and args and args[0] == "build":
            raise deploy.subprocess.CalledProcessError(1, "docker")
    monkeypatch.setattr(deploy, "compose", fake_compose)
    monkeypatch.setattr(deploy, "image_exists", lambda name, tag="latest": (name, tag) in images)
    monkeypatch.setattr(deploy, "smoke_test", lambda base, tries=30, wait=2.0: smoke)
    monkeypatch.setattr(deploy.sys, "argv", ["deploy.py", "--env-file", str(tmp_path / "e.env")])
    return calls


def test_deploy_success_keeps_previous_and_prunes(monkeypatch, tmp_path):
    calls = _fake(monkeypatch, tmp_path, {("rbprod-backend", "latest"), ("rbprod-web", "latest")}, smoke=True)
    assert deploy.main() == 0
    tags = [c[1] for c in calls if c[0] == "run" and c[1][:2] == ["docker", "tag"]]
    assert ["docker", "tag", "rbprod-backend:latest", "rbprod-backend:previous"] in tags
    assert any(c[0] == "run" and c[1][:3] == ["docker", "image", "prune"] for c in calls)


def test_deploy_failure_rolls_back_to_previous(monkeypatch, tmp_path):
    imgs = {(i, t) for i in deploy.IMAGES for t in ("latest", "previous")}
    calls = _fake(monkeypatch, tmp_path, imgs, smoke=False)
    assert deploy.main() == 1  # build đỏ để Jenkins báo FAILURE
    tags = [c[1] for c in calls if c[0] == "run" and c[1][:2] == ["docker", "tag"]]
    assert ["docker", "tag", "rbprod-web:previous", "rbprod-web:latest"] in tags
    assert ("compose", ("up", "-d", "--no-build", "--wait")) in calls


def test_first_deploy_failure_has_nothing_to_roll_back(monkeypatch, tmp_path):
    calls = _fake(monkeypatch, tmp_path, set(), smoke=False, compose_fail=True)
    assert deploy.main() == 1
    assert not any(c == ("compose", ("up", "-d", "--no-build", "--wait")) for c in calls)
