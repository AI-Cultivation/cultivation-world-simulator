import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def format_process_error(exc: subprocess.CalledProcessError) -> str:
    return (
        f"command: {' '.join(str(part) for part in exc.cmd)}\n"
        f"exit code: {exc.returncode}\n"
        f"stdout:\n{exc.stdout or ''}\n"
        f"stderr:\n{exc.stderr or ''}"
    )


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_compose(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=get_project_root(),
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def http_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_until_backend_ready(timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    last_payload: dict | None = None
    while time.time() < deadline:
        try:
            payload = http_json("http://localhost:8002/api/v1/query/runtime/status")
            last_payload = payload
            if isinstance(payload, dict):
                if payload.get("ok") is True and isinstance(payload.get("data"), dict):
                    return
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            ConnectionResetError,
            ConnectionRefusedError,
            OSError,
        ) as exc:
            last_error = exc
        time.sleep(2)
    raise AssertionError(
        "Backend /api/v1/query/runtime/status did not become ready in time. "
        f"Last payload: {last_payload!r}; last error: {last_error!r}"
    )


def wait_until_frontend_proxy_ready(timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    last_payload: dict | None = None
    while time.time() < deadline:
        try:
            payload = http_json("http://localhost:8123/api/v1/query/runtime/status")
            last_payload = payload
            if isinstance(payload, dict):
                if payload.get("ok") is True and isinstance(payload.get("data"), dict):
                    return
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            ConnectionResetError,
            ConnectionRefusedError,
            OSError,
        ) as exc:
            last_error = exc
        time.sleep(2)
    raise AssertionError(
        "Frontend proxy /api/v1/query/runtime/status did not become ready in time. "
        f"Last payload: {last_payload!r}; last error: {last_error!r}"
    )


def get_compose_service_health(service_name: str) -> str | None:
    service = run_compose("ps", "-q", service_name, timeout=60).stdout.strip()
    if not service:
        return None

    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}",
            service,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout.strip()


def wait_until_compose_service_healthy(
    service_name: str,
    timeout_seconds: int = 120,
) -> None:
    deadline = time.time() + timeout_seconds
    last_health: str | None = None
    while time.time() < deadline:
        last_health = get_compose_service_health(service_name)
        if last_health == "healthy":
            return
        time.sleep(2)
    raise AssertionError(
        f"Compose service {service_name!r} did not become healthy in time. "
        f"Last health status: {last_health!r}"
    )


def wait_until_game_ready(timeout_seconds: int = 300) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    last_payload: dict | None = None
    while time.time() < deadline:
        try:
            payload = http_json("http://localhost:8002/api/v1/query/world/state")
            last_payload = payload
            if isinstance(payload, dict) and payload.get("ok") is True:
                return
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            ConnectionResetError,
            ConnectionRefusedError,
            OSError,
        ) as exc:
            last_error = exc
        time.sleep(2)
    raise AssertionError(
        "Backend world did not become ready in time. "
        f"Last payload: {last_payload!r}; last error: {last_error!r}"
    )


@pytest.mark.docker
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not found in PATH")
def test_docker_compose_services_become_healthy():
    try:
        run_compose("up", "-d", timeout=600)
        wait_until_backend_ready()
        wait_until_frontend_proxy_ready()
        wait_until_compose_service_healthy("backend")
        wait_until_compose_service_healthy("frontend")
    finally:
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=get_project_root(),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )


@pytest.mark.docker
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not found in PATH")
def test_docker_compose_persists_settings_after_recreate():
    try:
        run_compose("up", "-d", "--build", timeout=900)
        wait_until_backend_ready()
        wait_until_frontend_proxy_ready()
        wait_until_compose_service_healthy("backend")
        wait_until_compose_service_healthy("frontend")

        updated = http_json(
            "http://localhost:8002/api/settings",
            method="PATCH",
            payload={"simulation": {"auto_save_enabled": True}},
        )
        assert updated["simulation"]["auto_save_enabled"] is True

        llm_update = http_json(
            "http://localhost:8002/api/settings/llm",
            method="PUT",
            payload={
                "base_url": "https://api.example.com/v1",
                "api_key": "docker-smoke-secret",
                "model_name": "model-a",
                "fast_model_name": "model-b",
                "mode": "default",
                "max_concurrent_requests": 4,
                "clear_api_key": False,
                "api_format": "openai",
            },
        )
        assert llm_update["status"] == "ok"

        llm_status = http_json("http://localhost:8002/api/settings/llm/status")
        assert llm_status["configured"] is True

        start_res = http_json(
            "http://localhost:8002/api/v1/command/game/start",
            method="POST",
            payload={
                "content_locale": "zh-CN",
                "init_npc_num": 4,
                "sect_num": 2,
                "npc_awakening_rate_per_month": 0.01,
                "world_lore": "",
            },
        )
        assert start_res["ok"] is True
        assert start_res["data"]["status"] == "ok"
        wait_until_game_ready(timeout_seconds=600)

        save_res = http_json(
            "http://localhost:8002/api/v1/command/game/save",
            method="POST",
            payload={"custom_name": "docker_smoke"},
        )
        assert save_res["ok"] is True
        assert save_res["data"]["status"] == "ok"
        saved_filename = save_res["data"]["filename"]
        assert saved_filename.endswith(".json")

        saves_before = http_json("http://localhost:8002/api/v1/query/saves")
        assert saves_before["ok"] is True
        assert any(item["filename"] == saved_filename for item in saves_before["data"]["saves"])

        run_compose("down", timeout=180)
        run_compose("up", "-d", timeout=600)
        wait_until_backend_ready()
        wait_until_frontend_proxy_ready()
        wait_until_compose_service_healthy("backend")
        wait_until_compose_service_healthy("frontend")

        after_recreate = http_json("http://localhost:8002/api/settings")
        assert after_recreate["simulation"]["auto_save_enabled"] is True

        llm_status_after_recreate = http_json("http://localhost:8002/api/settings/llm/status")
        assert llm_status_after_recreate["configured"] is True

        saves_after = http_json("http://localhost:8002/api/v1/query/saves")
        assert saves_after["ok"] is True
        assert any(item["filename"] == saved_filename for item in saves_after["data"]["saves"])

        load_res = http_json(
            "http://localhost:8002/api/v1/command/game/load",
            method="POST",
            payload={"filename": saved_filename},
        )
        assert load_res["ok"] is True
        assert load_res["data"]["status"] == "ok"
        wait_until_game_ready(timeout_seconds=300)
    except Exception as exc:
        ps = subprocess.run(
            ["docker", "compose", "ps"],
            cwd=get_project_root(),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        logs = subprocess.run(
            ["docker", "compose", "logs", "--no-color", "backend"],
            cwd=get_project_root(),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        frontend_logs = subprocess.run(
            ["docker", "compose", "logs", "--no-color", "frontend"],
            cwd=get_project_root(),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        raise AssertionError(
            "Docker runtime smoke test failed.\n"
            f"compose ps:\n{ps.stdout}\n"
            f"backend logs:\n{logs.stdout}\n"
            f"frontend logs:\n{frontend_logs.stdout}\n"
            f"original error: {format_process_error(exc) if isinstance(exc, subprocess.CalledProcessError) else repr(exc)}"
        ) from exc
    finally:
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=get_project_root(),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
