"""Unit tests for es_tools.docker module."""

import pytest

from es_tools.docker.docker import (
    DEFAULT_DOCKER_IMAGE,
    DOCKER_IMAGE_ENV_VAR,
    ElasticsearchDocker,
)


class TestElasticsearchDocker:
    """Test Docker image selection."""

    def test_uses_pinned_default_image(self, monkeypatch: pytest.MonkeyPatch):
        """Default image stays pinned when no override is set."""
        monkeypatch.delenv(DOCKER_IMAGE_ENV_VAR, raising=False)
        docker = ElasticsearchDocker()
        assert docker.image == DEFAULT_DOCKER_IMAGE

    def test_uses_environment_override(self, monkeypatch: pytest.MonkeyPatch):
        """Environment override is used when no explicit image is passed."""
        image = "docker.elastic.co/elasticsearch/elasticsearch:9.6.0"
        monkeypatch.setenv(DOCKER_IMAGE_ENV_VAR, image)
        docker = ElasticsearchDocker()
        assert docker.image == image

    def test_ignores_empty_environment_override(self, monkeypatch: pytest.MonkeyPatch):
        """Empty environment overrides fall back to the pinned default."""
        monkeypatch.setenv(DOCKER_IMAGE_ENV_VAR, "")
        docker = ElasticsearchDocker()
        assert docker.image == DEFAULT_DOCKER_IMAGE

    def test_explicit_image_overrides_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Explicit constructor image wins over the environment."""
        monkeypatch.setenv(
            DOCKER_IMAGE_ENV_VAR,
            "docker.elastic.co/elasticsearch/elasticsearch:9.6.0",
        )
        docker = ElasticsearchDocker(image="custom.registry/elasticsearch:1.2.3")
        assert docker.image == "custom.registry/elasticsearch:1.2.3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
