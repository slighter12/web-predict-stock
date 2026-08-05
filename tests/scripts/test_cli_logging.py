import logging

from scripts import _logging


def test_configure_cli_logging_uses_log_level_and_existing_format(monkeypatch):
    config = {}
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setattr(
        _logging.logging,
        "basicConfig",
        lambda **kwargs: config.update(kwargs),
    )

    _logging.configure_cli_logging()

    assert config == {
        "level": logging.DEBUG,
        "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
    }


def test_configure_cli_logging_defaults_to_info_for_unknown_level(monkeypatch):
    config = {}
    monkeypatch.setenv("LOG_LEVEL", "not-a-level")
    monkeypatch.setattr(
        _logging.logging,
        "basicConfig",
        lambda **kwargs: config.update(kwargs),
    )

    _logging.configure_cli_logging()

    assert config["level"] == logging.INFO


def test_configure_cli_logging_defaults_to_info_for_non_level_logging_attribute(
    monkeypatch,
):
    config = {}
    monkeypatch.setenv("LOG_LEVEL", "BASIC_FORMAT")
    monkeypatch.setattr(
        _logging.logging,
        "basicConfig",
        lambda **kwargs: config.update(kwargs),
    )

    _logging.configure_cli_logging()

    assert config["level"] == logging.INFO
