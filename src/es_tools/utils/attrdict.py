"""Simple attribute-access dictionary wrapper to replace DotMap."""

from typing import Any


class AttrDict(dict[str, Any]):
    """Dictionary subclass that allows attribute access to keys.

    This is a lightweight replacement for DotMap that provides attribute-style
    access to dictionary keys while maintaining full dict compatibility.
    Supports nested attribute access by automatically converting nested dicts
    to AttrDict instances.

    Example:
        >>> d = AttrDict({'foo': 'bar', 'nested': {'key': 'value'}})
        >>> d.foo
        'bar'
        >>> d.nested.key
        'value'
    """

    def __init__(self, *args, **kwargs):
        """Initialize AttrDict with nested dict conversion."""
        super().__init__(*args, **kwargs)
        # Convert nested dicts to AttrDict
        for key, value in self.items():
            if isinstance(value, dict) and not isinstance(value, AttrDict):
                self[key] = AttrDict(value)

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(
                f"'AttrDict' object has no attribute '{name}'"
            ) from exc

    def __setattr__(self, name: str, value):
        self[name] = value

    def __delattr__(self, name: str):
        try:
            del self[name]
        except KeyError as exc:
            raise AttributeError(
                f"'AttrDict' object has no attribute '{name}'"
            ) from exc

    def toDict(self) -> dict[str, Any]:
        """Return a plain dictionary copy."""
        result: dict[str, Any] = {}
        for key, value in self.items():
            if isinstance(value, AttrDict):
                result[key] = value.toDict()
            else:
                result[key] = value
        return result
