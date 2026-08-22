import subprocess

import pytest

from scripts import check_feature_registry_consistency


def test_frontend_registry_check_reports_missing_bun(monkeypatch):
    def raise_missing_bun(*args, **kwargs):
        raise FileNotFoundError("bun")

    monkeypatch.setattr(
        check_feature_registry_consistency.subprocess,
        "run",
        raise_missing_bun,
    )

    with pytest.raises(RuntimeError, match="requires 'bun' on PATH"):
        check_feature_registry_consistency._load_frontend_registry()


def test_frontend_registry_check_reports_timeout(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(
        check_feature_registry_consistency.subprocess,
        "run",
        raise_timeout,
    )

    with pytest.raises(RuntimeError, match="timed out"):
        check_feature_registry_consistency._load_frontend_registry()
