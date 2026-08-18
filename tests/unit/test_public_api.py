"""Public API surface: stubs gone, real names remain."""

import importlib

import pytest


@pytest.mark.parametrize(
    "mod",
    [
        "es_tools.index.field_usage",
        "es_tools.index.time_slicer",
        "es_tools.testbed",
        "es_tools.redact.main",
        "es_tools.redact.redacters",
    ],
)
def test_stub_modules_removed(mod: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_redact_ilm_still_importable() -> None:
    from es_tools.redact import RedactFields, RedactIlm

    assert RedactIlm is not None
    assert RedactFields is not None


def test_root_still_exports_create_client() -> None:
    import es_tools

    assert "create_client" in es_tools.__all__
    assert "RedactTool" not in es_tools.__all__
    assert "RedactFields" not in es_tools.__all__
    assert "FieldUsageAnalyzer" not in es_tools.__all__
