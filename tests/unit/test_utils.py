"""Unit tests for es_tools.utils module."""

import pytest

from es_tools.utils import (
    ConfigManager,
    ensure_list,
    pluralize,
    redact,
    to_bool,
    to_int,
    to_str,
)


class TestEnsureList:
    """Test ensure_list function."""

    def test_none(self):
        """Test with None value."""
        assert ensure_list(None) == []

    def test_single_value(self):
        """Test with single value."""
        assert ensure_list("hello") == ["hello"]

    def test_list(self):
        """Test with list."""
        assert ensure_list(["a", "b"]) == ["a", "b"]


class TestPluralize:
    """Test pluralize function."""

    def test_singular(self):
        """Test singular form."""
        assert pluralize("index", 1) == "index"

    def test_plural(self):
        """Test plural form."""
        assert pluralize("index", 2) == "indexes"

    def test_default_plural(self):
        """Test default plural."""
        assert pluralize("index") == "indexes"


class TestRedact:
    """Test redact function."""

    def test_redact_password(self):
        """Test redacting password."""
        data = {"password": "secret", "name": "test"}
        result = redact(data)
        assert result["password"] == "***"
        assert result["name"] == "test"

    def test_redact_nested(self):
        """Test redacting nested data."""
        data = {"client": {"password": "secret"}}
        result = redact(data)
        assert result["client"]["password"] == "***"


class TestToBool:
    """Test to_bool function."""

    def test_string_true(self):
        """Test with 'true' string."""
        assert to_bool("true") is True

    def test_string_false(self):
        """Test with 'false' string."""
        assert to_bool("false") is False

    def test_int(self):
        """Test with integer."""
        assert to_bool(1) is True
        assert to_bool(0) is False


class TestToInt:
    """Test to_int function."""

    def test_valid_string(self):
        """Test with valid string."""
        assert to_int("123") == 123

    def test_invalid_string(self):
        """Test with invalid string."""
        assert to_int("invalid", default=0) == 0


class TestToString:
    """Test to_str function."""

    def test_int(self):
        """Test with integer."""
        assert to_str(123) == "123"

    def test_none(self):
        """Test with None."""
        assert to_str(None) == ""


class TestConfigManager:
    """Test ConfigManager class."""

    def test_save_and_load(self, tmp_path):
        """Test saving and loading configuration."""
        config_file = tmp_path / "test.yml"
        config = {"key": "value", "number": 42}

        manager = ConfigManager(config_file)
        manager.save(config)

        loaded = manager.load()
        assert loaded == config

    def test_load_nonexistent(self):
        """Test loading nonexistent file raises error."""
        manager = ConfigManager("/nonexistent/file.yml")
        with pytest.raises(FileNotFoundError):
            manager.load()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
