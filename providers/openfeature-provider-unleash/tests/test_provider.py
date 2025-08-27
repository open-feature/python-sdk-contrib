import pytest

from openfeature.contrib.provider.unleash import UnleashProvider


def test_unleash_provider_import():
    """Test that UnleashProvider can be imported."""
    assert UnleashProvider is not None


def test_unleash_provider_instantiation():
    """Test that UnleashProvider can be instantiated."""
    provider = UnleashProvider()
    assert provider is not None


def test_unleash_provider_get_metadata():
    """Test that UnleashProvider returns correct metadata."""
    provider = UnleashProvider()
    metadata = provider.get_metadata()
    assert metadata.name == "Unleash Provider"


def test_unleash_provider_methods_not_implemented():
    """Test that UnleashProvider methods raise NotImplementedError."""
    provider = UnleashProvider()

    with pytest.raises(NotImplementedError):
        provider.resolve_boolean_details("test_flag", True)

    with pytest.raises(NotImplementedError):
        provider.resolve_string_details("test_flag", "default")

    with pytest.raises(NotImplementedError):
        provider.resolve_integer_details("test_flag", 1)

    with pytest.raises(NotImplementedError):
        provider.resolve_float_details("test_flag", 1.0)

    with pytest.raises(NotImplementedError):
        provider.resolve_object_details("test_flag", {"key": "value"})


def test_unleash_provider_hooks():
    """Test that UnleashProvider returns empty hooks list."""
    provider = UnleashProvider()
    hooks = provider.get_provider_hooks()
    assert hooks == []
