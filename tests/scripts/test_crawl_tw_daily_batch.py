from __future__ import annotations

import sys
from datetime import datetime


def test_crawl_tw_daily_batch_main_returns_zero(capsys, monkeypatch, load_script):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script",
    )
    monkeypatch.setattr(
        module,
        "ingest_tw_market_batch",
        lambda **kwargs: {
            "market": "TW",
            "trading_date": "2026-03-20",
            "upserted_rows": 2,
            "errors": [],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["crawl_tw_daily_batch.py", "2026-03-20", "--refresh-universe"],
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"upserted_rows": 2' in captured.out


def test_crawl_tw_daily_batch_main_returns_one_on_error(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script_error",
    )
    monkeypatch.setattr(
        module,
        "ingest_tw_market_batch",
        lambda **kwargs: {
            "market": "TW",
            "trading_date": "2026-03-20",
            "upserted_rows": 0,
            "errors": [{"source_name": "twse_mi_index", "message": "timeout"}],
        },
    )
    monkeypatch.setattr(sys, "argv", ["crawl_tw_daily_batch.py", "20260320"])

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"source_name": "twse_mi_index"' in captured.out


def test_parse_trading_date_defaults_to_taipei_timezone(load_script, monkeypatch):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script_timezone",
    )
    captured: dict = {}

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            captured["tz"] = tz
            return cls(2026, 3, 24, 0, 30, tzinfo=tz)

    monkeypatch.setattr(module, "datetime", FakeDateTime)

    trading_date = module._parse_trading_date(None)

    assert str(captured["tz"]) == "Asia/Taipei"
    assert trading_date.isoformat() == "2026-03-24"
