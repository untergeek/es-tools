"""Docker-backed integration fixtures."""

from __future__ import annotations

import shutil
import subprocess
import time

import pytest

from es_tools.docker import ElasticsearchDocker


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _docker_available():
        return
    skip = pytest.mark.skip(reason="docker daemon not available")
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def es_client():
    """Start Elasticsearch in Docker and wait until it answers health."""
    docker = ElasticsearchDocker(name="es-tools-itest", port=19200)
    docker.start()
    try:
        client = docker.get_client()
        deadline = time.time() + 120
        last = None
        while time.time() < deadline:
            try:
                last = client.cluster.health()
                if last.get("status") in {"green", "yellow"}:
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            raise RuntimeError(f"Elasticsearch did not become ready: {last}")
        yield client
    finally:
        try:
            docker.stop()
        except Exception:
            pass
        try:
            docker.remove()
        except Exception:
            pass
