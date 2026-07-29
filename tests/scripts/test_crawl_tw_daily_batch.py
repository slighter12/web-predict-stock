from __future__ import annotations

import json
import sys
from datetime import datetime

import pytest


def test_crawl_tw_daily_batch_main_returns_zero(capsys, monkeypatch, load_script):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script",
    )
    calls = []
    monkeypatch.setattr(
        module,
        "ingest_tw_market_batch",
        lambda **kwargs: calls.append(kwargs)
        or {
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
    assert calls == [
        {
            "trading_date": module.date(2026, 3, 20),
            "refresh_universe": True,
        }
    ]
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


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["crawl_tw_daily_batch.py", "--start-date", "2026-03-20"],
            "--start-date and --end-date must be provided together",
        ),
        (
            [
                "crawl_tw_daily_batch.py",
                "2026-03-20",
                "--start-date",
                "2026-03-20",
                "--end-date",
                "2026-03-23",
            ],
            "trading_date cannot be combined with a date range",
        ),
        (
            [
                "crawl_tw_daily_batch.py",
                "--start-date",
                "2026-03-23",
                "--end-date",
                "2026-03-20",
            ],
            "--start-date must not be after --end-date",
        ),
        (
            [
                "crawl_tw_daily_batch.py",
                "--start-date",
                "2026-03-20",
                "--end-date",
                "2026-03-23",
                "--delay-seconds",
                "-1",
            ],
            "--delay-seconds must be nonnegative",
        ),
    ],
)
def test_crawl_tw_daily_batch_rejects_invalid_range_arguments(
    capsys, monkeypatch, load_script, argv, message
):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_invalid_range",
    )
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit, match="2"):
        module.main()

    assert message in capsys.readouterr().err


def test_crawl_tw_daily_batch_range_attempts_weekdays_and_delays(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script_range",
    )
    calls = []
    delays = []
    monkeypatch.setattr(
        module,
        "ingest_tw_market_batch",
        lambda **kwargs: calls.append(kwargs)
        or {"upserted_rows": 2, "errors": [], "status": "succeeded"},
    )
    monkeypatch.setattr(module.time, "sleep", delays.append)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl_tw_daily_batch.py",
            "--start-date",
            "2026-03-20",
            "--end-date",
            "2026-03-23",
            "--delay-seconds",
            "0.25",
        ],
    )

    exit_code = module.main()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert [call["trading_date"].isoformat() for call in calls] == [
        "2026-03-20",
        "2026-03-23",
    ]
    assert summary["attempted_dates"] == ["2026-03-20", "2026-03-23"]
    assert summary["succeeded_dates"] == ["2026-03-20", "2026-03-23"]
    assert summary["upserted_rows"] == 4
    assert delays == [0.25]


def test_crawl_tw_daily_batch_range_aggregates_skip_and_failures(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script_range_failures",
    )
    calls = []
    summaries = iter(
        [
            {
                "upserted_rows": 0,
                "errors": [],
                "status": "skipped_non_trading_day",
            },
            {
                "upserted_rows": 1,
                "errors": [{"source_name": "twse_mi_index", "message": "timeout"}],
                "status": "partial",
            },
            RuntimeError("network unavailable"),
        ]
    )

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        result = next(summaries)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(module, "ingest_tw_market_batch", fake_ingest)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl_tw_daily_batch.py",
            "--start-date",
            "2026-03-20",
            "--end-date",
            "2026-03-24",
            "--refresh-universe",
        ],
    )

    exit_code = module.main()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["skipped_non_trading_dates"] == ["2026-03-20"]
    assert summary["failed_dates"] == ["2026-03-23", "2026-03-24"]
    assert summary["upserted_rows"] == 1
    assert [error["trading_date"] for error in summary["errors"]] == [
        "2026-03-23",
        "2026-03-24",
    ]
    assert [call["refresh_universe"] for call in calls] == [True, False, False]


def test_crawl_tw_daily_batch_range_fails_on_universe_refresh_error(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script_universe_refresh_error",
    )
    monkeypatch.setattr(
        module,
        "ingest_tw_market_batch",
        lambda **kwargs: {
            "upserted_rows": 0,
            "status": "failed",
            "errors": [
                {
                    "source_name": "universe_refresh",
                    "message": "exchange=TWSE reconciliation: write failed",
                }
            ],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl_tw_daily_batch.py",
            "--start-date",
            "2026-03-20",
            "--end-date",
            "2026-03-20",
            "--refresh-universe",
        ],
    )

    exit_code = module.main()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["failed_dates"] == ["2026-03-20"]
    assert summary["errors"] == [
        {
            "trading_date": "2026-03-20",
            "source_name": "universe_refresh",
            "message": "exchange=TWSE reconciliation: write failed",
        }
    ]


def test_crawl_tw_daily_batch_range_retries_universe_refresh_after_error(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script_retries_universe_refresh",
    )
    calls = []
    summaries = iter(
        [
            {
                "upserted_rows": 0,
                "status": "partial",
                "errors": [
                    {
                        "source_name": "universe_refresh",
                        "message": "exchange=TWSE reconciliation: write failed",
                    }
                ],
            },
            {
                "upserted_rows": 1,
                "status": "succeeded",
                "errors": [],
            },
            {
                "upserted_rows": 1,
                "status": "succeeded",
                "errors": [],
            },
        ]
    )

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        return next(summaries)

    monkeypatch.setattr(module, "ingest_tw_market_batch", fake_ingest)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl_tw_daily_batch.py",
            "--start-date",
            "2026-03-20",
            "--end-date",
            "2026-03-24",
            "--refresh-universe",
        ],
    )

    exit_code = module.main()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["failed_dates"] == ["2026-03-20"]
    assert [call["refresh_universe"] for call in calls] == [True, True, False]


def test_crawl_tw_daily_batch_range_limits_refresh_attempts_after_exceptions(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_daily_batch.py",
        "crawl_tw_daily_batch_script_limits_refresh_attempts",
    )
    calls = []
    outcomes = iter(
        [
            RuntimeError("network unavailable"),
            RuntimeError("network unavailable"),
            RuntimeError("network unavailable"),
            {
                "upserted_rows": 1,
                "status": "succeeded",
                "errors": [],
            },
        ]
    )

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(module, "ingest_tw_market_batch", fake_ingest)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl_tw_daily_batch.py",
            "--start-date",
            "2026-03-20",
            "--end-date",
            "2026-03-25",
            "--refresh-universe",
        ],
    )

    exit_code = module.main()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["failed_dates"] == [
        "2026-03-20",
        "2026-03-23",
        "2026-03-24",
    ]
    assert [call["refresh_universe"] for call in calls] == [True, True, True, False]
