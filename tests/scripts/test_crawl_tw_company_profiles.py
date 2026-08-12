from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from backend.market_data.services import company_crawlers
from backend.market_data.services import company_profiles


def _save_outcomes(payloads, save):
    outcomes = []
    for payload in payloads:
        try:
            outcomes.append(
                company_profiles.CompanyProfileSaveOutcome(
                    payload=payload,
                    saved=save(payload),
                    error=None,
                )
            )
        except Exception as exc:
            outcomes.append(
                company_profiles.CompanyProfileSaveOutcome(
                    payload=payload,
                    saved=None,
                    error=exc,
                )
            )
    return outcomes


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


def test_company_source_descriptors_bind_trusted_source_metadata():
    assert company_crawlers.TWSE_COMPANY_SOURCE.url == (
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    )
    assert (
        company_crawlers.TWSE_COMPANY_SOURCE.source_name,
        company_crawlers.TWSE_COMPANY_SOURCE.exchange,
        company_crawlers.TWSE_COMPANY_SOURCE.board,
    ) == ("twse_company_profile", "TWSE", "listed")
    assert (
        company_crawlers.TPEX_COMPANY_SOURCE.source_name,
        company_crawlers.TPEX_COMPANY_SOURCE.exchange,
        company_crawlers.TPEX_COMPANY_SOURCE.board,
    ) == ("tpex_company_profile", "TPEX", "otc")


def test_company_feed_request_disables_redirects(monkeypatch):
    calls = []
    monkeypatch.setattr(
        company_crawlers,
        "request_with_tls_fallback",
        lambda **kwargs: calls.append(kwargs) or object(),
    )

    company_crawlers._request_company_feed_with_tls_fallback(
        url=company_crawlers.TWSE_COMPANY_SOURCE.url,
        timeout_seconds=30,
    )

    assert calls[0]["allow_redirects"] is False


def test_company_feed_rejects_non_official_url(monkeypatch):
    monkeypatch.setattr(
        company_crawlers,
        "_request_company_feed_with_tls_fallback",
        lambda **kwargs: pytest.fail("untrusted URL must not be requested"),
    )
    untrusted_source = company_profiles.CompanyProfileSource(
        url="https://example.test/company-feed",
        source_name="twse_company_profile",
        exchange="TWSE",
        board="listed",
    )

    with pytest.raises(
        company_crawlers.UnsupportedConfigurationError,
        match="source descriptor is not trusted",
    ):
        company_crawlers._fetch_company_feed(source=untrusted_source)


def test_company_feed_rejects_200_response_from_different_final_url(monkeypatch):
    response = SimpleNamespace(
        url="https://redirected.example.test/company-feed",
        status_code=200,
        text='[{"CompanyCode":"2330","CompanyName":"TSMC"}]',
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr(
        company_crawlers,
        "_request_company_feed_with_tls_fallback",
        lambda **kwargs: response,
    )
    monkeypatch.setattr(
        company_crawlers,
        "persist_raw_ingest_record",
        lambda **kwargs: pytest.fail("redirected payload must not be persisted"),
    )

    with pytest.raises(
        company_crawlers.UnsupportedConfigurationError,
        match="final URL does not match",
    ):
        company_crawlers._fetch_company_feed(
            source=company_crawlers.TWSE_COMPANY_SOURCE
        )


def test_company_feed_rejects_redirect_and_persists_only_failed_audit(monkeypatch):
    persisted = []
    response = SimpleNamespace(
        url=company_crawlers.TWSE_COMPANY_SOURCE.url,
        status_code=302,
        text="",
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr(
        company_crawlers,
        "_request_company_feed_with_tls_fallback",
        lambda **kwargs: response,
    )
    monkeypatch.setattr(
        company_crawlers,
        "persist_raw_ingest_record",
        lambda **kwargs: persisted.append(kwargs) or 1,
    )

    with pytest.raises(company_crawlers.ExternalFetchError):
        company_crawlers._fetch_company_feed(
            source=company_crawlers.TWSE_COMPANY_SOURCE
        )

    assert [item["fetch_status"] for item in persisted] == [
        company_crawlers.FETCH_STATUS_FAILED
    ]


@pytest.mark.parametrize(
    (
        "source",
        "record",
        "expected_symbol",
        "expected_name",
        "expected_listing_date",
        "expected_industry",
    ),
    [
        (
            company_crawlers.TWSE_COMPANY_SOURCE,
            {
                "公司代號": "2330",
                "公司名稱": "台灣積體電路製造股份有限公司",
                "上市日期": "1994/09/05",
                "產業別": "半導體業",
            },
            "2330",
            "台灣積體電路製造股份有限公司",
            date(1994, 9, 5),
            "半導體業",
        ),
        (
            company_crawlers.TPEX_COMPANY_SOURCE,
            {
                "SecuritiesCompanyCode": "6488",
                "CompanyName": "GlobalWafers Co., Ltd.",
                "DateOfListing": "2015/09/25",
                "SecuritiesIndustryCode": "24",
            },
            "6488",
            "GlobalWafers Co., Ltd.",
            date(2015, 9, 25),
            "24",
        ),
    ],
)
def test_statusless_official_schema_record_is_active(
    source,
    record,
    expected_symbol,
    expected_name,
    expected_listing_date,
    expected_industry,
):
    payload = company_crawlers._build_profile_payload(
        item=record,
        exchange=source.exchange,
        board=source.board,
        source_name=source.source_name,
        raw_payload_id=1,
        archive_reference="raw_ingest_audit:1",
    )

    assert payload["symbol"] == expected_symbol
    assert payload["company_name"] == expected_name
    assert payload["exchange"] == source.exchange
    assert payload["board"] == source.board
    assert payload["source_name"] == source.source_name
    assert payload["listing_date"] == expected_listing_date
    assert payload["industry_category"] == expected_industry
    assert payload["trading_status"] == "active"


@pytest.mark.parametrize("status", ["inactive", "unknown", "suspended"])
def test_official_current_listing_record_rejects_non_active_status(status):
    with pytest.raises(ValueError, match="status is not active"):
        company_crawlers._build_profile_payload(
            item={
                "CompanyCode": "2330",
                "CompanyName": "TSMC",
                "TradingStatus": status,
            },
            exchange="TWSE",
            board="listed",
            source_name="twse_company_profile",
            raw_payload_id=1,
            archive_reference="raw_ingest_audit:1",
        )


def _company_profile_payload(**overrides):
    payload = {
        "symbol": "2330",
        "market": "TW",
        "exchange": "TWSE",
        "board": "listed",
        "company_name": "TSMC",
        "isin_code": None,
        "industry_category": None,
        "listing_date": None,
        "trading_status": "active",
        "source_name": "twse_company_profile",
        "raw_payload_id": 1,
        "archive_object_reference": "raw_ingest_audit:1",
    }
    payload.update(overrides)
    return payload


def test_save_company_profile_accepts_trusted_source_pair(monkeypatch):
    saved = []
    monkeypatch.setattr(
        company_profiles,
        "get_raw_ingest_record",
        lambda raw_payload_id: SimpleNamespace(
            source_name="twse_company_profile",
            market="TW",
            symbol="TW_COMPANY_UNIVERSE",
            parser_version="tw_company_profile_v1",
            fetch_status="success",
            expected_symbol_context="source=twse_company_profile;market=TW",
            payload_body='[{"CompanyCode":"2330","CompanyName":"TSMC"}]',
        ),
    )
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: saved.append(payload) or payload,
    )

    company_profiles.save_tw_company_profile(_company_profile_payload())

    assert saved[0]["source_name"] == "twse_company_profile"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"source_name": "untrusted"}, "source_name is not trusted"),
        ({"exchange": "TPEX"}, "source pairing is invalid"),
        ({"board": "otc"}, "source pairing is invalid"),
        ({"trading_status": "inactive"}, "must be active"),
        ({"trading_status": "unknown"}, "must be active"),
    ],
)
def test_save_company_profile_rejects_untrusted_metadata(
    monkeypatch, override, message
):
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: pytest.fail("invalid profile must not be persisted"),
    )

    with pytest.raises(ValueError, match=message):
        company_profiles.save_tw_company_profile(
            _company_profile_payload(**override)
        )


def test_save_company_profile_requires_trading_status(monkeypatch):
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: pytest.fail("invalid profile must not be persisted"),
    )
    payload = _company_profile_payload()
    del payload["trading_status"]

    with pytest.raises(KeyError, match="trading_status"):
        company_profiles.save_tw_company_profile(payload)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"raw_payload_id": None}, "raw_payload_id must be a positive int"),
        ({"raw_payload_id": 0}, "raw_payload_id must be a positive int"),
        (
            {"archive_object_reference": "raw_ingest_audit:2"},
            "archive reference is invalid",
        ),
    ],
)
def test_save_company_profile_rejects_missing_or_mismatched_provenance(
    monkeypatch, override, message
):
    monkeypatch.setattr(
        company_profiles,
        "get_raw_ingest_record",
        lambda raw_payload_id: pytest.fail("invalid reference must not be loaded"),
    )
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: pytest.fail("invalid profile must not be persisted"),
    )

    with pytest.raises(ValueError, match=message):
        company_profiles.save_tw_company_profile(
            _company_profile_payload(**override)
        )


def test_save_company_profile_rejects_mismatched_raw_ingest_provenance(
    monkeypatch,
):
    monkeypatch.setattr(
        company_profiles,
        "get_raw_ingest_record",
        lambda raw_payload_id: SimpleNamespace(
            source_name="tpex_company_profile",
            market="TW",
            symbol="TW_COMPANY_UNIVERSE",
            parser_version="tw_company_profile_v1",
            fetch_status="success",
            expected_symbol_context="source=tpex_company_profile;market=TW",
        ),
    )
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: pytest.fail("invalid profile must not be persisted"),
    )

    with pytest.raises(ValueError, match="raw ingest provenance is invalid"):
        company_profiles.save_tw_company_profile(_company_profile_payload())


def test_batch_save_raises_once_when_verification_fails(monkeypatch):
    raw_lookups = []
    monkeypatch.setattr(
        company_profiles,
        "get_raw_ingest_record",
        lambda raw_payload_id: raw_lookups.append(raw_payload_id)
        or SimpleNamespace(
            source_name="tpex_company_profile",
            market="TW",
            symbol="TW_COMPANY_UNIVERSE",
            parser_version="tw_company_profile_v1",
            fetch_status="success",
            expected_symbol_context="source=tpex_company_profile;market=TW",
        ),
    )
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: pytest.fail("unverified batch must not be persisted"),
    )

    with pytest.raises(ValueError, match="raw ingest provenance is invalid"):
        company_profiles.save_tw_company_profiles(
            [
                _company_profile_payload(),
                _company_profile_payload(symbol="2317", company_name="Hon Hai"),
            ]
        )

    assert raw_lookups == [1]


def test_save_company_profile_rejects_forged_symbol_with_valid_raw_audit(
    monkeypatch,
):
    monkeypatch.setattr(
        company_profiles,
        "get_raw_ingest_record",
        lambda raw_payload_id: SimpleNamespace(
            source_name="twse_company_profile",
            market="TW",
            symbol="TW_COMPANY_UNIVERSE",
            parser_version="tw_company_profile_v1",
            fetch_status="success",
            expected_symbol_context="source=twse_company_profile;market=TW",
            payload_body='[{"CompanyCode":"2330","CompanyName":"TSMC"}]',
        ),
    )
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: pytest.fail("forged symbol must not be persisted"),
    )

    with pytest.raises(ValueError, match="not attested by its raw payload"):
        company_profiles.save_tw_company_profile(
            _company_profile_payload(symbol="9999", company_name="Forged")
        )


def test_save_company_profile_rejects_forged_field_with_valid_identity(
    monkeypatch,
):
    monkeypatch.setattr(
        company_profiles,
        "get_raw_ingest_record",
        lambda raw_payload_id: SimpleNamespace(
            source_name="twse_company_profile",
            market="TW",
            symbol="TW_COMPANY_UNIVERSE",
            parser_version="tw_company_profile_v1",
            fetch_status="success",
            expected_symbol_context="source=twse_company_profile;market=TW",
            payload_body=(
                '[{"CompanyCode":"2330","CompanyName":"TSMC",'
                '"Industry":"Semiconductor"}]'
            ),
        ),
    )
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: pytest.fail("forged field must not be persisted"),
    )

    with pytest.raises(ValueError, match="not attested by its raw payload"):
        company_profiles.save_tw_company_profile(
            _company_profile_payload(industry_category="Forged Industry")
        )


def test_single_save_has_no_caller_supplied_verification_bypass():
    with pytest.raises(TypeError, match="verified_batch"):
        company_profiles.save_tw_company_profile(
            _company_profile_payload(),
            verified_batch=object(),
        )


def test_crawl_verifies_raw_audit_once_for_multiple_profiles(monkeypatch):
    raw_lookups = []
    records = [
        {"CompanyCode": "2330", "CompanyName": "TSMC"},
        {"CompanyCode": "2317", "CompanyName": "Hon Hai"},
    ]
    monkeypatch.setattr(
        company_crawlers,
        "_fetch_company_feed",
        lambda **kwargs: (7, records),
    )
    monkeypatch.setattr(
        company_profiles,
        "get_raw_ingest_record",
        lambda raw_payload_id: raw_lookups.append(raw_payload_id)
        or SimpleNamespace(
            source_name="twse_company_profile",
            market="TW",
            symbol="TW_COMPANY_UNIVERSE",
            parser_version="tw_company_profile_v1",
            fetch_status="success",
            expected_symbol_context="source=twse_company_profile;market=TW",
            payload_body=(
                '[{"CompanyCode":"2330","CompanyName":"TSMC"},'
                '{"CompanyCode":"2317","CompanyName":"Hon Hai"}]'
            ),
        ),
    )
    monkeypatch.setattr(
        company_profiles,
        "upsert_tw_company_profile",
        lambda payload: {**payload, "write_action": "created"},
    )
    monkeypatch.setattr(company_crawlers, "count_active_tw_company_profiles", lambda: 2)

    summary = company_crawlers.crawl_tw_company_profiles(
        include_tpex=False,
        reconcile=False,
    )

    assert raw_lookups == [7]
    assert summary["upserted_count"] == 2
    assert summary["errors"] == []


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
        lambda **kwargs: (1, records[kwargs["source"].source_name]),
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profiles",
        lambda payloads: _save_outcomes(
            payloads, lambda payload: {**payload, "write_action": "created"}
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: reconciliations.append(kwargs) or 1,
    )
    monkeypatch.setattr(
        company_crawlers,
        "list_active_tw_company_profiles",
        lambda **kwargs: [
            {"symbol": "2330", "exchange": "TWSE"},
            {"symbol": "8049", "exchange": "TPEX"},
        ],
    )
    monkeypatch.setattr(company_crawlers, "count_active_tw_company_profiles", lambda: 2)

    summary = company_crawlers.crawl_tw_company_profiles()

    assert reconciliations == [
        {
            "exchange": "TWSE",
            "active_symbols": {"2330"},
            "source_name": company_crawlers.TWSE_COMPANY_SOURCE_NAME,
            "raw_payload_id": 1,
            "archive_object_reference": "raw_ingest_audit:1",
        },
        {
            "exchange": "TPEX",
            "active_symbols": {"8049"},
            "source_name": company_crawlers.TPEX_COMPANY_SOURCE_NAME,
            "raw_payload_id": 1,
            "archive_object_reference": "raw_ingest_audit:1",
        },
    ]
    assert summary["inactivated_count"] == 2
    assert summary["reconciliation_requested"] is True
    assert summary["reconciliation_skipped"] is False
    assert [
        item["exchange"] for item in summary["source_summaries"]
    ] == ["TWSE", "TPEX"]
    assert summary["active_symbol_count"] == 2
    assert summary["errors"] == []


def test_crawl_reports_one_sanitized_batch_verification_error(monkeypatch):
    secret = "raw payload token=secret"
    monkeypatch.setattr(
        company_crawlers,
        "_fetch_company_feed",
        lambda **kwargs: (
            7,
            [
                {"CompanyCode": "2330", "CompanyName": "TSMC"},
                {"CompanyCode": "2317", "CompanyName": "Hon Hai"},
            ],
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profiles",
        lambda payloads: (_ for _ in ()).throw(ValueError(secret)),
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: pytest.fail("invalid batch must not reconcile"),
    )
    monkeypatch.setattr(
        company_crawlers,
        "list_active_tw_company_profiles",
        lambda **kwargs: [],
    )

    summary = company_crawlers._crawl_single_source(
        source=company_crawlers.TWSE_COMPANY_SOURCE,
    )

    assert summary["upserted_count"] == 0
    assert summary["reconciliation_skipped"] is True
    assert summary["errors"] == [
        "exchange=TWSE raw_payload_id=7 batch_save_error_type=ValueError"
    ]
    assert secret not in str(summary)


def test_crawl_single_source_skips_reconciliation_when_feed_coverage_is_low(
    monkeypatch, caplog
):
    existing_symbols = {str(1000 + index) for index in range(100)}
    records = [
        {"CompanyCode": str(1000 + index), "CompanyName": "Test Company"}
        for index in range(90)
    ] + [
        {"CompanyCode": str(2000 + index), "CompanyName": "New Company"}
        for index in range(5)
    ]
    monkeypatch.setattr(
        company_crawlers,
        "_fetch_company_feed",
        lambda **kwargs: (1, records),
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profiles",
        lambda payloads: _save_outcomes(
            payloads, lambda payload: {**payload, "write_action": "created"}
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "list_active_tw_company_profiles",
        lambda **kwargs: [
            {"symbol": symbol, "exchange": "TWSE"} for symbol in existing_symbols
        ],
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: pytest.fail("truncated feed must not inactivate profiles"),
    )

    summary = company_crawlers._crawl_single_source(
        source=company_crawlers.TWSE_COMPANY_SOURCE,
    )

    assert summary["inactivated_count"] == 0
    assert summary["reconciliation_skipped"] is True
    assert summary["errors"] == [
        "exchange=TWSE raw_payload_id=1 reconciliation skipped: "
        "covered_symbol_count=90 existing_active_symbol_count=100."
    ]
    assert "Skipped TW company profile reconciliation due to low coverage" in (
        caplog.text
    )


def test_crawl_single_source_reconciles_at_minimum_feed_coverage(monkeypatch):
    records = [
        {"CompanyCode": str(1000 + index), "CompanyName": "Test Company"}
        for index in range(95)
    ]
    existing_symbols = {str(1000 + index) for index in range(100)}
    reconciliations = []
    monkeypatch.setattr(
        company_crawlers, "_fetch_company_feed", lambda **kwargs: (1, records)
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profiles",
        lambda payloads: _save_outcomes(
            payloads, lambda payload: {**payload, "write_action": "created"}
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "list_active_tw_company_profiles",
        lambda **kwargs: [
            {"symbol": symbol, "exchange": "TWSE"} for symbol in existing_symbols
        ],
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: reconciliations.append(kwargs) or 1,
    )

    summary = company_crawlers._crawl_single_source(
        source=company_crawlers.TWSE_COMPANY_SOURCE,
    )

    assert len(reconciliations) == 1
    assert len(reconciliations[0]["active_symbols"]) == 95
    assert summary["inactivated_count"] == 1
    assert summary["reconciliation_skipped"] is False


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
        source=company_crawlers.TWSE_COMPANY_SOURCE,
    )

    assert summary["inactivated_count"] == 0
    assert summary["reconciliation_skipped"] is True
    assert summary["errors"] == [
        "exchange=TWSE raw_payload_id=1 reconciliation skipped: "
        "company feed is empty."
    ]


def test_crawl_tw_company_profiles_can_disable_reconciliation(monkeypatch):
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
        "save_tw_company_profiles",
        lambda payloads: _save_outcomes(
            payloads, lambda payload: {**payload, "write_action": "created"}
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "list_active_tw_company_profiles",
        lambda **kwargs: pytest.fail("reconciliation is disabled"),
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: pytest.fail("reconciliation is disabled"),
    )
    monkeypatch.setattr(company_crawlers, "count_active_tw_company_profiles", lambda: 1)

    summary = company_crawlers.crawl_tw_company_profiles(
        include_tpex=False,
        reconcile=False,
    )

    assert summary["reconciliation_requested"] is False
    assert summary["reconciliation_skipped"] is False
    assert summary["inactivated_count"] == 0
    assert summary["errors"] == []


def test_crawl_single_source_does_not_reconcile_after_write_error(
    monkeypatch, caplog
):
    secret = "token=secret"
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
        "save_tw_company_profiles",
        lambda payloads: _save_outcomes(
            payloads,
            lambda payload: (_ for _ in ()).throw(
                RuntimeError(f"write failed {secret}")
            ),
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "list_active_tw_company_profiles",
        lambda **kwargs: [{"symbol": "2330", "exchange": "TWSE"}],
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: pytest.fail("failed crawl must not inactivate profiles"),
    )

    summary = company_crawlers._crawl_single_source(
        source=company_crawlers.TWSE_COMPANY_SOURCE,
    )

    assert summary["inactivated_count"] == 0
    assert summary["reconciliation_skipped"] is True
    assert summary["errors"] == [
        "exchange=TWSE symbol=2330 save_error_type=RuntimeError"
    ]
    assert secret not in str(summary)
    assert secret not in caplog.text


def test_crawl_single_source_reports_failed_reconciliation(monkeypatch, caplog):
    monkeypatch.setattr(
        company_crawlers,
        "_fetch_company_feed",
        lambda **kwargs: (1, [{"CompanyCode": "2330", "CompanyName": "TSMC"}]),
    )
    monkeypatch.setattr(
        company_crawlers,
        "save_tw_company_profiles",
        lambda payloads: _save_outcomes(
            payloads, lambda payload: {**payload, "write_action": "noop"}
        ),
    )
    monkeypatch.setattr(
        company_crawlers,
        "list_active_tw_company_profiles",
        lambda **kwargs: [{"symbol": "2330", "exchange": "TWSE"}],
    )
    monkeypatch.setattr(
        company_crawlers,
        "mark_missing_active_tw_company_profiles_inactive",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("write failed")),
    )

    with caplog.at_level("WARNING"):
        summary = company_crawlers._crawl_single_source(
            source=company_crawlers.TWSE_COMPANY_SOURCE,
        )

    assert summary["inactivated_count"] == 0
    assert summary["reconciliation_skipped"] is True
    assert summary["errors"] == [
        "exchange=TWSE reconciliation error_type=RuntimeError"
    ]
    assert "write failed" not in summary["errors"][0]
    matching_records = [
        record
        for record in caplog.records
        if "reconciliation failed" in record.getMessage()
    ]
    assert len(matching_records) == 1
    assert matching_records[0].exc_info is not None
