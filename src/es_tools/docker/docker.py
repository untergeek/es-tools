"""ElasticsearchDocker class for es_tools.docker.

Manages Elasticsearch Docker containers for testing.
"""

import logging
import os
import subprocess
from typing import Any

from es_tools.debug import begin_end, debug
from es_tools.exceptions import ESToolContainerError

logger = logging.getLogger(__name__)

DEFAULT_DOCKER_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:9.5.2"
DOCKER_IMAGE_ENV_VAR = "ES_TOOLS_DOCKER_IMAGE"


class ElasticsearchDocker:
    """Manage Elasticsearch Docker containers for testing.

    Provides methods to start, stop, and manage Elasticsearch containers.

    Args:
        image: Docker image name. Defaults to the value of ES_TOOLS_DOCKER_IMAGE
            when set, otherwise
            'docker.elastic.co/elasticsearch/elasticsearch:9.5.2'.
        port: Host port to map (default: 9200).
        name: Container name (default: 'es-test').
        env_vars: Environment variables for the container.

    Example:
        >>> docker = ElasticsearchDocker()
        >>> docker.start()
        >>> client = docker.get_client()
    """

    def __init__(
        self,
        image: str | None = None,
        port: int = 9200,
        name: str = "es-test",
        env_vars: dict[str, str] | None = None,
    ):
        env_image = os.getenv(DOCKER_IMAGE_ENV_VAR)
        self.image = image or env_image or DEFAULT_DOCKER_IMAGE
        self.port = port
        self.name = name
        self.env_vars = env_vars or {}
        self._container_id: str | None = None
        debug.lv2("Initializing ElasticsearchDocker")

    @begin_end()
    def start(self) -> str:
        """Start the Elasticsearch container.

        Returns:
            Container ID.

        Raises:
            ESToolContainerError: If container fails to start.

        Example:
            >>> container_id = docker.start()
        """
        debug.lv2(f"Starting container: {self.name}")

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.name,
            "-p",
            f"{self.port}:9200",
            "-e",
            "discovery.type=single-node",
            "-e",
            "xpack.security.enabled=false",
            "-e",
            "ES_JAVA_OPTS=-Xms512m -Xmx512m",
        ]

        # Add environment variables
        for key, value in self.env_vars.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.append(self.image)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            self._container_id = result.stdout.strip()
            debug.lv3(f"Container started: {self._container_id}")
            return self._container_id
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to start container: {exc.stderr}")
            raise ESToolContainerError(
                f"Failed to start container: {exc.stderr}"
            ) from exc

    @begin_end()
    def stop(self) -> bool:
        """Stop the Elasticsearch container.

        Returns:
            True if stopped successfully.

        Raises:
            ESToolContainerError: If container fails to stop.
        """
        debug.lv2(f"Stopping container: {self.name}")

        cmd = ["docker", "stop", self.name]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            self._container_id = None
            debug.lv3(f"Container stopped: {self.name}")
            return True
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to stop container: {exc.stderr}")
            raise ESToolContainerError(
                f"Failed to stop container: {exc.stderr}"
            ) from exc

    @begin_end()
    def remove(self) -> bool:
        """Remove the Elasticsearch container.

        Returns:
            True if removed successfully.

        Raises:
            ESToolContainerError: If container fails to remove.
        """
        debug.lv2(f"Removing container: {self.name}")

        # Stop first if running
        if self._container_id:
            try:
                self.stop()
            except Exception:
                pass

        cmd = ["docker", "rm", self.name]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            self._container_id = None
            debug.lv3(f"Container removed: {self.name}")
            return True
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to remove container: {exc.stderr}")
            raise ESToolContainerError(
                f"Failed to remove container: {exc.stderr}"
            ) from exc

    @begin_end()
    def get_client(self) -> Any:
        """Get an Elasticsearch client connected to the container.

        Returns:
            Elasticsearch client instance.

        Raises:
            ESToolContainerError: If container is not running.
        """
        if not self._container_id:
            raise ESToolContainerError("Container is not running")

        from elasticsearch9 import Elasticsearch

        return Elasticsearch(
            hosts=[f"http://localhost:{self.port}"],
            verify_certs=False,
        )

    @property
    def is_running(self) -> bool:
        """Check if the container is running.

        Returns:
            True if container is running.
        """
        if not self._container_id:
            return False

        cmd = ["docker", "inspect", "-f", "{{.State.Running}}", self.name]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() == "true"
        except subprocess.CalledProcessError:
            return False

    def __repr__(self) -> str:
        """Return string representation."""
        status = "running" if self.is_running else "stopped"
        return f"ElasticsearchDocker(name={self.name!r}, status={status})"
