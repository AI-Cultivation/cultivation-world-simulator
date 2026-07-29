import re
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_copy_sources(dockerfile: Path) -> list[str]:
    sources: list[str] = []
    for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith("COPY "):
            continue

        parts = line.split()
        if len(parts) >= 3:
            sources.extend(parts[1:-1])
    return sources


def get_service_block(compose_text: str, service_name: str) -> str:
    lines = compose_text.splitlines()
    in_services = False
    in_target = False
    service_indent = ""
    block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_target:
                block.append(line)
            continue

        if not in_services:
            if stripped == "services:":
                in_services = True
            continue

        if not in_target:
            service_match = re.match(r"^(\s{2})([a-zA-Z0-9_-]+):\s*$", line)
            if service_match and service_match.group(2) == service_name:
                in_target = True
                service_indent = service_match.group(1)
                block.append(line)
            continue

        next_service_match = re.match(rf"^{service_indent}([a-zA-Z0-9_-]+):\s*$", line)
        if next_service_match and next_service_match.group(1) != service_name:
            break
        block.append(line)

    return "\n".join(block)


def get_compose_text() -> str:
    compose_file = get_project_root() / "docker-compose.yml"
    return compose_file.read_text(encoding="utf-8")


def get_workflow_text(name: str) -> str:
    workflow_file = get_project_root() / ".github" / "workflows" / name
    return workflow_file.read_text(encoding="utf-8")


def test_frontend_registry_import_targets_static_registry():
    project_root = get_project_root()
    registry_ts = project_root / "web" / "src" / "locales" / "registry.ts"
    content = registry_ts.read_text(encoding="utf-8")

    match = re.search(r"import\s+localeRegistryData\s+from\s+'([^']+)'", content)
    assert match, "Expected locale registry import in web/src/locales/registry.ts"

    imported_path = (registry_ts.parent / match.group(1)).resolve()
    expected_path = (project_root / "static" / "locales" / "registry.json").resolve()

    assert imported_path == expected_path
    assert imported_path.exists()


def test_frontend_dockerfile_copies_shared_locale_registry():
    dockerfile = get_project_root() / "deploy" / "Dockerfile.frontend"
    copy_sources = parse_copy_sources(dockerfile)

    assert "web/" in copy_sources
    assert "static/locales/registry.json" in copy_sources, (
        "Frontend Docker build must copy the shared locale registry because "
        "web/src/locales/registry.ts imports it from outside web/."
    )


def test_frontend_world_info_import_targets_static_game_config():
    project_root = get_project_root()
    world_info_ts = project_root / "web" / "src" / "utils" / "worldInfo.ts"
    content = world_info_ts.read_text(encoding="utf-8")

    match = re.search(r"import\s+worldInfoCsvText\s+from\s+'([^']+)'", content)
    assert match, "Expected world info csv import in web/src/utils/worldInfo.ts"

    imported_path = (world_info_ts.parent / match.group(1).replace("?raw", "")).resolve()
    expected_path = (project_root / "static" / "game_configs" / "world_info.csv").resolve()

    assert imported_path == expected_path
    assert imported_path.exists()


def test_frontend_dockerfile_copies_shared_world_info_csv():
    dockerfile = get_project_root() / "deploy" / "Dockerfile.frontend"
    copy_sources = parse_copy_sources(dockerfile)

    assert "static/game_configs/world_info.csv" in copy_sources, (
        "Frontend Docker build must copy the shared world info csv because "
        "web/src/utils/worldInfo.ts imports it from outside web/."
    )


def test_frontend_vite_config_does_not_force_split_vue_and_ui_vendor_chunks():
    vite_config = (get_project_root() / "web" / "vite.config.ts").read_text(encoding="utf-8")

    assert "vendor-vue" not in vite_config
    assert "vendor-ui" not in vite_config


def test_main_ci_runs_frontend_production_build_and_smoke():
    workflow = get_workflow_text("test.yml")

    assert "npm run build" in workflow
    assert "npm run smoke:production" in workflow
    assert "CWS_SMOKE_MOCK_API" in workflow
    assert "npx playwright install --with-deps chromium" in workflow


def test_docker_smoke_ci_builds_and_browser_tests_compose_frontend():
    workflow = get_workflow_text("docker-smoke.yml")

    assert "docker compose build" in workflow
    assert "docker compose up -d --build" in workflow
    assert "http://localhost:8123/api/v1/query/runtime/status" in workflow
    assert "CWS_SMOKE_BASE_URL" in workflow
    assert "CWS_SMOKE_SKIP_WEBSERVER" in workflow
    assert "npm run smoke:production" in workflow


def test_backend_dockerfile_does_not_copy_tools_directory():
    dockerfile = get_project_root() / "deploy" / "Dockerfile.backend"
    copy_sources = parse_copy_sources(dockerfile)

    assert "requirements-runtime.txt" in copy_sources
    assert "src/" in copy_sources
    assert "static/" in copy_sources
    assert "assets/" in copy_sources
    assert "tools/" not in copy_sources, (
        "Backend runtime should not depend on the tools directory after the "
        "locale registry migration to static/locales/registry.json."
    )


def test_backend_dockerfile_installs_runtime_requirements_only():
    dockerfile = (get_project_root() / "deploy" / "Dockerfile.backend").read_text(encoding="utf-8")

    assert "-r requirements-runtime.txt" in dockerfile, (
        "Backend Docker image should install runtime-only dependencies to keep "
        "the production image smaller and less fragile."
    )
    assert "-r requirements.txt" not in dockerfile, (
        "Backend Docker image should not install test-only dependencies."
    )


def test_backend_dockerfile_pins_debian_release_tag():
    dockerfile = (get_project_root() / "deploy" / "Dockerfile.backend").read_text(encoding="utf-8")

    assert "FROM python:3.12-bookworm" in dockerfile, (
        "Backend Docker image should pin the Debian release instead of using "
        "the floating python:3.12-slim tag, which can move between Debian "
        "releases and make apt installs fragile during mirror syncs."
    )
    assert "FROM python:3.12-slim" not in dockerfile


def test_runtime_requirements_exclude_test_packages():
    runtime_requirements = (get_project_root() / "requirements-runtime.txt").read_text(encoding="utf-8")

    assert "pytest" not in runtime_requirements
    assert "pytest-cov" not in runtime_requirements
    assert "pytest-asyncio" not in runtime_requirements


def test_backend_dockerfile_does_not_create_legacy_runtime_dirs():
    dockerfile = (get_project_root() / "deploy" / "Dockerfile.backend").read_text(encoding="utf-8")

    assert "/app/assets/saves" not in dockerfile
    assert "/app/logs" not in dockerfile


def test_backend_compose_uses_persistent_data_root():
    compose_text = get_compose_text()
    backend_block = get_service_block(compose_text, "backend")

    assert backend_block, "Expected backend service in docker-compose.yml"
    assert "CWS_DATA_DIR=/data" in backend_block, (
        "Backend service must define CWS_DATA_DIR so settings/secrets/saves/logs "
        "persist outside container writable layers."
    )
    assert "CWS_DISABLE_AUTO_SHUTDOWN=1" in backend_block, (
        "Backend Docker service must disable the desktop-style auto shutdown "
        "trigger when no websocket clients remain connected."
    )
    assert "./docker-data:/data" in backend_block, (
        "Backend service must mount host docker-data to /data to persist "
        "settings/secrets/saves/logs."
    )
    assert "./assets/saves:/app/assets/saves" not in backend_block, (
        "Backend service should not keep legacy assets/saves volume, because "
        "runtime saves now use CWS_DATA_DIR."
    )
    assert "./logs:/app/logs" not in backend_block, (
        "Backend service should not keep legacy /app/logs volume, because "
        "runtime logs now use CWS_DATA_DIR."
    )


def test_backend_compose_contract_exposes_port_and_healthcheck():
    compose_text = get_compose_text()
    backend_block = get_service_block(compose_text, "backend")

    assert backend_block, "Expected backend service in docker-compose.yml"
    assert '"8002:8002"' in backend_block
    assert "healthcheck:" in backend_block
    assert "test:" in backend_block
    assert "http://127.0.0.1:8002/api/v1/query/runtime/status" in backend_block
    assert "http://localhost:8002/api/v1/query/runtime/status" not in backend_block
    assert "interval:" in backend_block
    assert "timeout:" in backend_block
    assert "retries:" in backend_block


def test_frontend_compose_contract_depends_on_backend_and_exposes_port():
    compose_text = get_compose_text()
    frontend_block = get_service_block(compose_text, "frontend")

    assert frontend_block, "Expected frontend service in docker-compose.yml"
    assert 'depends_on:' in frontend_block
    assert 'backend:' in frontend_block
    assert 'condition: service_healthy' in frontend_block
    assert '"8123:80"' in frontend_block
    assert "healthcheck:" in frontend_block
    assert "test:" in frontend_block
    assert "http://127.0.0.1:80/api/v1/query/runtime/status" in frontend_block
    assert "http://localhost:80/api/v1/query/runtime/status" not in frontend_block
    assert "interval:" in frontend_block
    assert "timeout:" in frontend_block
    assert "retries:" in frontend_block
