"""Unit tests for es_tools package."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from es_tools.client import (
    ConfigParser,
    create_client,
    validate_config,
    verify_ssl_paths,
)
from es_tools.client.models import ClientConfig, ElasticsearchConfig, OtherSettings
from es_tools.client.validators import ElasticsearchConfigModel
from es_tools.exceptions import (
    ESToolConfigurationError,
    ESToolSchemaValidationError,
)


class TestValidateConfig:
    """Test configuration validation."""

    def test_valid_config(self):
        """Test validation of valid configuration."""
        config = {
            "elasticsearch": {
                "client": {
                    "hosts": ["http://localhost:9200"],
                }
            }
        }
        result = validate_config(config)
        assert result == config

    def test_missing_elasticsearch_key(self):
        """Test validation fails when elasticsearch key is missing."""
        config = {"client": {"hosts": ["http://localhost:9200"]}}
        with pytest.raises(ESToolSchemaValidationError):
            validate_config(config)

    def test_missing_client_key(self):
        """Test validation fails when client key is missing."""
        config = {"elasticsearch": {"other": {}}}
        with pytest.raises(ESToolSchemaValidationError):
            validate_config(config)

    def test_invalid_host_schema(self):
        """Test validation fails with invalid host schema."""
        config = {"elasticsearch": {"client": {"hosts": ["ftp://localhost"]}}}
        with pytest.raises(ESToolSchemaValidationError):
            validate_config(config)

    def test_hosts_and_cloud_id_conflict(self):
        """Test validation fails when both hosts and cloud_id are present."""
        config = {
            "elasticsearch": {
                "client": {
                    "hosts": ["http://localhost:9200"],
                    "cloud_id": "my_cloud_id",
                }
            }
        }
        with pytest.raises(ESToolSchemaValidationError):
            validate_config(config)


class TestConfigParser:
    """Test ConfigParser class."""

    def test_parse_from_dict(self):
        """Test parsing configuration from dictionary."""
        config_dict = {
            "elasticsearch": {
                "client": {
                    "hosts": ["http://localhost:9200"],
                }
            }
        }
        parser = ConfigParser(configdict=config_dict)
        result = parser.parse()
        assert result == config_dict

    def test_parse_empty_config(self):
        """Test parsing empty configuration."""
        parser = ConfigParser()
        result = parser.parse()
        assert isinstance(result, dict)


class TestCreateClient:
    """Test create_client factory function."""

    def test_create_client_with_dict(self):
        """Test creating client from dictionary."""
        config = {
            "elasticsearch": {
                "client": {
                    "hosts": ["http://localhost:9200"],
                }
            }
        }
        client = create_client(config)
        assert client is not None

    def test_create_client_with_configfile(self, tmp_path):
        """Test creating client with a YAML config file."""
        import yaml

        config = {
            "elasticsearch": {
                "client": {
                    "hosts": ["http://localhost:9200"],
                }
            }
        }
        config_file = tmp_path / "config.yml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        client = create_client(configfile=str(config_file))
        assert client is not None

    def test_create_client_with_cloud_id(self):
        """cloud_id-only config constructs a client (no default-hosts conflict)."""
        import base64

        cloud_id = (
            "mycluster:" + base64.b64encode(b"host.cloud.es.io$esid$kibanaid").decode()
        )
        config = {"elasticsearch": {"client": {"cloud_id": cloud_id}}}
        with patch("es_tools.client.builder.elasticsearch9.Elasticsearch") as es:
            es.return_value = object()
            create_client(config)
        assert es.call_args.kwargs["cloud_id"] == cloud_id
        assert not es.call_args.kwargs.get("hosts")

    def test_create_client_with_defaults(self):
        """create_client() with no args uses ES_DEFAULT and returns a client."""
        client = create_client()
        assert client is not None

    def _es_config(self, **client_kw):
        return {
            "elasticsearch": {
                "client": {"hosts": ["https://es.example:9200"], **client_kw}
            }
        }

    def test_create_client_passes_api_key(self):
        """api_key must reach Elasticsearch()."""
        with patch("es_tools.client.builder.elasticsearch9.Elasticsearch") as es:
            es.return_value = object()
            create_client(self._es_config(api_key="id:secret"))
        kwargs = es.call_args.kwargs
        assert kwargs["api_key"] == "id:secret"
        assert kwargs["hosts"] == ["https://es.example:9200"]

    def test_create_client_passes_api_key_tuple(self):
        """ES9 tuple-form api_key=(id, key) must reach Elasticsearch()."""
        with patch("es_tools.client.builder.elasticsearch9.Elasticsearch") as es:
            es.return_value = object()
            create_client(self._es_config(api_key=("id", "secret")))
        assert es.call_args.kwargs["api_key"] == ("id", "secret")

    def test_create_client_coerces_api_key_list(self):
        """YAML two-item lists become (id, key)."""
        with patch("es_tools.client.builder.elasticsearch9.Elasticsearch") as es:
            es.return_value = object()
            create_client(self._es_config(api_key=["id", "secret"]))
        assert es.call_args.kwargs["api_key"] == ("id", "secret")

    def test_create_client_passes_bearer_auth(self):
        """bearer_auth must reach Elasticsearch()."""
        with patch("es_tools.client.builder.elasticsearch9.Elasticsearch") as es:
            es.return_value = object()
            create_client(self._es_config(bearer_auth="tok"))
        assert es.call_args.kwargs["bearer_auth"] == "tok"

    def test_create_client_passes_basic_auth_tuple(self):
        """client.basic_auth must reach Elasticsearch()."""
        with patch("es_tools.client.builder.elasticsearch9.Elasticsearch") as es:
            es.return_value = object()
            create_client(self._es_config(basic_auth=("u", "p")))
        assert es.call_args.kwargs["basic_auth"] == ("u", "p")

    def test_create_client_username_password_become_basic_auth(self):
        """other_settings username/password become basic_auth."""
        cfg = {
            "elasticsearch": {
                "client": {"hosts": ["https://es.example:9200"]},
                "other_settings": {"username": "u", "password": "p"},
            }
        }
        with patch("es_tools.client.builder.elasticsearch9.Elasticsearch") as es:
            es.return_value = object()
            create_client(cfg)
        assert es.call_args.kwargs["basic_auth"] == ("u", "p")

    def test_create_client_missing_ca_certs_raises(self, tmp_path):
        """Missing ca_certs path is a configuration error."""
        config = {
            "elasticsearch": {
                "client": {
                    "hosts": ["https://es.example:9200"],
                    "ca_certs": str(tmp_path / "missing.pem"),
                }
            }
        }
        with pytest.raises(ESToolConfigurationError, match="ca_certs"):
            create_client(config)


def test_api_key_rejects_wrong_arity() -> None:
    """api_key must be a string or a two-item (id, key)."""
    with pytest.raises(ValidationError):
        ElasticsearchConfigModel.model_validate(
            {"client": {"hosts": ["http://localhost:9200"], "api_key": ["only"]}}
        )


def test_api_key_rejects_empty_string() -> None:
    """Empty string api_key is invalid."""
    with pytest.raises(ValidationError):
        ElasticsearchConfigModel.model_validate(
            {"client": {"hosts": ["http://localhost:9200"], "api_key": ""}}
        )


def test_api_key_rejects_empty_parts() -> None:
    """Tuple/list api_key parts must be non-empty strings."""
    with pytest.raises(ValidationError):
        ElasticsearchConfigModel.model_validate(
            {"client": {"hosts": ["http://localhost:9200"], "api_key": ["id", ""]}}
        )


def test_verify_ssl_paths_ok(tmp_path):
    """Existing cert paths pass."""
    p = tmp_path / "ca.pem"
    p.write_text("x")
    verify_ssl_paths({"ca_certs": str(p)})


def test_verify_ssl_paths_missing(tmp_path):
    """Missing cert path raises ESToolConfigurationError."""
    with pytest.raises(ESToolConfigurationError, match="ca_certs"):
        verify_ssl_paths({"ca_certs": str(tmp_path / "nope.pem")})


class TestPydanticModels:
    """Test Pydantic validation models."""

    def test_client_config_model(self):
        """Test ClientConfigModel validation."""
        model = ElasticsearchConfigModel.model_validate(
            {"client": {"hosts": ["http://localhost:9200"]}}
        )
        assert model.client.hosts == ["http://localhost:9200"]
        assert model.client.verify_certs is True

    def test_client_config_model_empty_hosts(self):
        """Test ClientConfigModel rejects empty hosts."""
        with pytest.raises(ValidationError):
            ElasticsearchConfigModel.model_validate({"client": {"hosts": []}})

    def test_client_config_model_hosts_cloud_id_conflict(self):
        """Test ClientConfigModel rejects hosts and cloud_id together."""
        with pytest.raises(ValidationError):
            ElasticsearchConfigModel.model_validate(
                {
                    "client": {
                        "hosts": ["http://localhost:9200"],
                        "cloud_id": "my_cloud_id",
                    }
                }
            )

    def test_client_config_model_cloud_id_only(self):
        """cloud_id-only config does not inject default hosts."""
        model = ElasticsearchConfigModel.model_validate(
            {"client": {"cloud_id": "my_cloud_id"}}
        )
        assert model.client.cloud_id == "my_cloud_id"
        assert not model.client.hosts

    def test_elasticsearch_config_model_master_only_single_host(self):
        """Test ElasticsearchConfigModel validates master_only with single host."""
        model = ElasticsearchConfigModel.model_validate(
            {
                "client": {"hosts": ["http://localhost:9200"]},
                "other_settings": {"master_only": True},
            }
        )
        assert model.other_settings.master_only is True

    def test_elasticsearch_config_model_master_only_multiple_hosts(self):
        """Test ElasticsearchConfigModel rejects master_only with multiple hosts."""
        with pytest.raises(ValidationError):
            ElasticsearchConfigModel.model_validate(
                {
                    "client": {
                        "hosts": ["http://localhost:9200", "http://localhost:9201"]
                    },
                    "other_settings": {"master_only": True},
                }
            )


class TestDataclasses:
    """Test dataclass configuration objects."""

    def test_client_config_dataclass(self):
        """Test ClientConfig dataclass."""
        config = ClientConfig(hosts=["http://localhost:9200"], verify_certs=True)
        assert config.hosts == ["http://localhost:9200"]
        assert config.verify_certs is True

    def test_other_settings_dataclass(self):
        """Test OtherSettings dataclass."""
        settings = OtherSettings(username="user", master_only=False)
        assert settings.username == "user"
        assert settings.master_only is False

    def test_elasticsearch_config_dataclass(self):
        """Test ElasticsearchConfig dataclass."""
        config = ElasticsearchConfig(
            client=ClientConfig(hosts=["http://localhost:9200"]),
            other_settings=OtherSettings(master_only=True),
        )
        assert config.client.hosts == ["http://localhost:9200"]
        assert config.other_settings.master_only is True


def test_secret_store_not_exported() -> None:
    """SecretStore was unused Fernet theater; it is not public API."""
    import es_tools
    import es_tools.client as client_mod

    assert "SecretStore" not in es_tools.__all__
    assert "SecretStore" not in client_mod.__all__
    assert not hasattr(es_tools, "SecretStore")
    assert not hasattr(client_mod, "SecretStore")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
