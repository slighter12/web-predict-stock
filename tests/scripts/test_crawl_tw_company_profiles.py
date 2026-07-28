from __future__ import annotations

import pytest

from backend.market_data.services import company_crawlers


def test_crawl_tw_company_profiles_main_returns_zero(capsys, monkeypatch, load_script):
    module = load_script(
        "crawl_tw_company_profiles.py",
        "crawl_tw_company_profiles_script",
    )
    monkeypatch.setattr(
        module,
        "crawl_tw_company_profiles",
        lambda: {
            "source_name": "tw_company_profiles",
            "raw_payload_id": 1,
            "processed_count": 2,
            "upserted_count": 2,
            "errors": [],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"upserted_count": 2' in captured.out


def test_crawl_tw_company_profiles_main_returns_one_on_error(
    capsys, monkeypatch, load_script
):
    module = load_script(
        "crawl_tw_company_profiles.py",
        "crawl_tw_company_profiles_script",
    )
    monkeypatch.setattr(
        module,
        "crawl_tw_company_profiles",
        lambda: {
            "source_name": "tw_company_profiles",
            "raw_payload_id": 2,
            "processed_count": 1,
            "upserted_count": 0,
            "errors": ["bad payload"],
        },
    )

    exit_code = module.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"errors": ["bad payload"]' in captured.out


def test_crawl_tw_company_profiles_reconciles_each_exchange(monkeypatch):
    records = {
        company_crawlers.TWSE_COMPANY_SOURCE_NAME: [
            {"CompanyCode": "2330", "CompanyName": "TSMC"},
        ],
        company_crawlers.TPEX_COMPANY_SOURCE_NAME: [
            {"CompanyCode": "8049", "CompanyName": "Amita"},
        ],
    }
    reconciliations = []

    monkeypatch.setattr(
        company_crawlers,
        "_fetch_company_feed",
        lambda **kwargs: (1, records[kwargs["source_name"]]),
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profile",
        lambda payload: {**payload, "write_action": "created"},
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: reconciliations.append(kwargs) or 1,
    )
    monkeypatch.setattr(
        company_crawlers,
        "count_active_tw_company_profiles",
        lambda **kwargs: 1 if kwargs else 2,
    )

    summary = company_crawlers.crawl_tw_company_profiles()

    assert reconciliations == [
        {"exchange": "TWSE", "active_symbols": {"2330"}},
        {"exchange": "TPEX", "active_symbols": {"8049"}},
    ]
    assert summary["inactivated_count"] == 2
    assert summary["active_symbol_count"] == 2
    assert summary["errors"] == []


def test_crawl_single_source_skips_reconciliation_when_feed_coverage_is_low(
    monkeypatch, caplog
):
    records = [
        {"CompanyCode": str(1000 + index), "CompanyName": "Test Company"}
        for index in range(94)
    ]
    monkeypatch.setattr(
        company_crawlers,
        "_fetch_company_feed",
        lambda **kwargs: (1, records),
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profile",
        lambda payload: {**payload, "write_action": "created"},
    )
    monkeypatch.setattr(
        company_crawlers, "count_active_tw_company_profiles", lambda **kwargs: 100
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: pytest.fail("truncated feed must not inactivate profiles"),
    )

    summary = company_crawlers._crawl_single_source(
        url_env="TEST_URL",
        default_url="https://example.test",
        source_name="test_company_profile",
        exchange="TWSE",
        board="listed",
    )

    assert summary["inactivated_count"] == 0
    assert "Skipped TW company profile reconciliation due to low coverage" in (
        caplog.text
    )


def test_crawl_single_source_reconciles_at_minimum_feed_coverage(monkeypatch):
    records = [
        {"CompanyCode": str(1000 + index), "CompanyName": "Test Company"}
        for index in range(95)
    ]
    reconciliations = []
    monkeypatch.setattr(
        company_crawlers, "_fetch_company_feed", lambda **kwargs: (1, records)
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profile",
        lambda payload: {**payload, "write_action": "created"},
    )
    monkeypatch.setattr(
        company_crawlers, "count_active_tw_company_profiles", lambda **kwargs: 100
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: reconciliations.append(kwargs) or 1,
    )

    summary = company_crawlers._crawl_single_source(
        url_env="TEST_URL",
        default_url="https://example.test",
        source_name="test_company_profile",
        exchange="TWSE",
        board="listed",
    )

    assert len(reconciliations) == 1
    assert len(reconciliations[0]["active_symbols"]) == 95
    assert summary["inactivated_count"] == 1


def test_crawl_single_source_does_not_reconcile_empty_feed(monkeypatch):
    monkeypatch.setattr(
        company_crawlers, "_fetch_company_feed", lambda **kwargs: (1, [])
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: pytest.fail("empty feed must not inactivate profiles"),
    )

    summary = company_crawlers._crawl_single_source(
        url_env="TEST_URL",
        default_url="https://example.test",
        source_name="test_company_profile",
        exchange="TWSE",
        board="listed",
    )

    assert summary["inactivated_count"] == 0
    assert summary["errors"] == []


def test_crawl_single_source_does_not_reconcile_after_write_error(monkeypatch):
    monkeypatch.setattr(
        company_crawlers,
        "_fetch_company_feed",
        lambda **kwargs: (
            1,
            [{"CompanyCode": "2330", "CompanyName": "TSMC"}],
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profile",
        lambda payload: (_ for _ in ()).throw(RuntimeError("write failed")),
    )
    monkeypatch.setattr(
        company_crawlers, "count_active_tw_company_profiles", lambda **kwargs: 1
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: pytest.fail("failed crawl must not inactivate profiles"),
    )

    summary = company_crawlers._crawl_single_source(
        url_env="TEST_URL",
        default_url="https://example.test",
        source_name="test_company_profile",
        exchange="TWSE",
        board="listed",
    )

    assert summary["inactivated_count"] == 0
    assert summary["errors"] == ["exchange=TWSE symbol=2330: write failed"]
