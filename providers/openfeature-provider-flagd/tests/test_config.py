from openfeature.contrib.provider.flagd.config import Config


def test_return_default_values():
    config = Config()
    assert config.host == "localhost"
    assert config.port == 8013
    assert config.tls is False
    assert config.timeout == 5


def test_overrides_defaults_with_environment(monkeypatch):
    monkeypatch.setenv("FLAGD_HOST", "flagd")
    monkeypatch.setenv("FLAGD_PORT", "1234")
    monkeypatch.setenv("FLAGD_TLS", "true")

    config = Config()
    assert config.host == "flagd"
    assert config.port == 1234
    assert config.tls is True


def test_uses_arguments_over_environments_and_defaults(monkeypatch):
    monkeypatch.setenv("FLAGD_HOST", "flagd")

    config = Config(host="flagd2", port=12345, tls=True)
    assert config.host == "flagd2"
    assert config.port == 12345
    assert config.tls is True
