from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.research.services.tradability as p3_screening_service
from backend.database import Base, DailyOHLCV, ImportantEvent, SymbolLifecycleRecord
from backend.research.contracts.runs import ResearchRunCreateRequest
from backend.shared.analytics.strategy import ResearchStrategyConfig


def _testing_session():
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            DailyOHLCV.__table__,
            SymbolLifecycleRecord.__table__,
            ImportantEvent.__table__,
        ],
    )
    return testing_session_local


def _seed_daily_rows(
    session_local, *, start: date, days: int, symbols: list[str]
) -> list[date]:
    trading_dates: list[date] = []
    with session_local() as session:
        for offset in range(days):
            trading_date = start + timedelta(days=offset)
            trading_dates.append(trading_date)
            for symbol in symbols:
                session.add(
                    DailyOHLCV(
                        date=trading_date,
                        symbol=symbol,
                        source="fixture",
                        market="TW",
                        open=100.0,
                        high=101.0,
                        low=99.0,
                        close=100.0,
                        volume=1_000_000,
                    )
                )
        session.commit()
    return trading_dates


def _make_request(**overrides) -> ResearchRunCreateRequest:
    payload = {
        "runtime_mode": "runtime_compatibility_mode",
        "market": "TW",
        "symbols": ["2330", "2317"],
        "date_range": {"start": "2024-01-01", "end": "2024-05-31"},
        "return_target": "open_to_open",
        "horizon_days": 1,
        "features": [{"name": "ma", "window": 5, "source": "close", "shift": 1}],
        "model": {"type": "xgboost", "params": {}},
        "strategy": {
            "type": "research_v1",
            "threshold": 0.003,
            "top_n": 2,
            "allow_proactive_sells": True,
        },
        "execution": {"slippage": 0.001, "fees": 0.002},
        "baselines": [],
    }
    payload.update(overrides)
    return ResearchRunCreateRequest(**payload)


def test_build_p3_summary_marks_unresolved_event_and_persists_monitor_observations(
    monkeypatch,
):
    testing_session_local = _testing_session()
    monkeypatch.setattr(p3_screening_service, "SessionLocal", testing_session_local)
    trading_dates = _seed_daily_rows(
        testing_session_local,
        start=date(2024, 1, 1),
        days=150,
        symbols=["2330", "2317"],
    )
    with testing_session_local() as session:
        session.add(
            ImportantEvent(
                symbol="2317",
                market="TW",
                event_type="merger",
                effective_date=trading_dates[-1],
                event_publication_ts=pd.Timestamp(trading_dates[-1]).to_pydatetime(),
                timestamp_source_class="official_exchange",
                source_name="fixture",
            )
        )
        session.commit()

    weights = pd.DataFrame(
        {
            "2330": [0.5, 0.5, 0.5],
            "2317": [0.5, 0.5, 0.5],
        },
        index=pd.to_datetime(trading_dates[-3:]),
    )
    volume_df = pd.DataFrame(
        {
            "2330": [1_000_000, 1_000_000, 1_000_000],
            "2317": [1_000_000, 1_000_000, 1_000_000],
        },
        index=weights.index,
    )

    result = p3_screening_service.build_p3_summary(
        request=_make_request(
            portfolio_aum=100_000,
            monitor_profile_id="p3_monitor_default_v1",
        ),
        strategy=ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=2,
            allow_proactive_sells=True,
        ),
        weights=weights,
        volume_df=volume_df,
    )

    assert result["corporate_event_state"] == "unresolved_corporate_event"
    assert result["tradability_state"] == "unresolved_corporate_event"
    assert result["tradability_contract_version"] == "p3_tradability_monitoring_v1"
    assert result["capacity_screening_active"] is True
    assert result["execution_universe_count"] == 1
    assert result["monitor_observation_status"] == "persisted"
    assert len(result["microstructure_observations"]) == 3


def test_build_p3_summary_marks_core_gaps_and_stale_risk(monkeypatch):
    testing_session_local = _testing_session()
    monkeypatch.setattr(p3_screening_service, "SessionLocal", testing_session_local)
    trading_dates = _seed_daily_rows(
        testing_session_local,
        start=date(2024, 1, 1),
        days=150,
        symbols=["2330", "2317"],
    )
    with testing_session_local() as session:
        for trading_date in trading_dates[-2:]:
            row = session.get(DailyOHLCV, (trading_date, "2317"))
            assert row is not None
            session.delete(row)
        session.commit()

    weights = pd.DataFrame(
        {
            "2330": [1.0, 1.0, 1.0],
            "2317": [0.0, 0.0, 1.0],
        },
        index=pd.to_datetime(trading_dates[-3:]),
    )
    volume_df = pd.DataFrame(
        {
            "2330": [1_000_000, 1_000_000, 1_000_000],
            "2317": [1_000_000, 1_000_000, 0],
        },
        index=weights.index,
    )

    result = p3_screening_service.build_p3_summary(
        request=_make_request(),
        strategy=ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=2,
            allow_proactive_sells=True,
        ),
        weights=weights,
        volume_df=volume_df,
    )

    assert result["missing_feature_policy_state"] == "core_data_gaps_filtered"
    assert result["tradability_state"] == "stale_risk"
    assert result["stale_mark_days_with_open_positions"] == 1
    assert result["stale_risk_share"] == pytest.approx(1 / 3)
    assert result["capacity_screening_active"] is False


def test_build_p3_summary_treats_deterministic_event_as_non_blocking(monkeypatch):
    testing_session_local = _testing_session()
    monkeypatch.setattr(p3_screening_service, "SessionLocal", testing_session_local)
    trading_dates = _seed_daily_rows(
        testing_session_local,
        start=date(2024, 1, 1),
        days=150,
        symbols=["2330"],
    )
    with testing_session_local() as session:
        session.add(
            ImportantEvent(
                symbol="2330",
                market="TW",
                event_type="cash_dividend",
                effective_date=trading_dates[-1],
                event_publication_ts=pd.Timestamp(trading_dates[-1]).to_pydatetime(),
                timestamp_source_class="official_exchange",
                source_name="fixture",
            )
        )
        session.commit()

    weights = pd.DataFrame(
        {"2330": [1.0, 1.0, 1.0]}, index=pd.to_datetime(trading_dates[-3:])
    )
    volume_df = pd.DataFrame(
        {"2330": [1_000_000, 1_000_000, 1_000_000]},
        index=weights.index,
    )

    result = p3_screening_service.build_p3_summary(
        request=_make_request(symbols=["2330"]),
        strategy=ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=1,
            allow_proactive_sells=True,
        ),
        weights=weights,
        volume_df=volume_df,
    )

    assert result["corporate_event_state"] == "clear"
    assert result["tradability_state"] == "execution_ready"
    assert result["execution_universe_count"] == 1


def test_build_p3_summary_marks_listing_status_change_without_lifecycle_as_unresolved(
    monkeypatch,
):
    testing_session_local = _testing_session()
    monkeypatch.setattr(p3_screening_service, "SessionLocal", testing_session_local)
    trading_dates = _seed_daily_rows(
        testing_session_local,
        start=date(2024, 1, 1),
        days=150,
        symbols=["2330"],
    )
    with testing_session_local() as session:
        session.add(
            ImportantEvent(
                symbol="2330",
                market="TW",
                event_type="listing_status_change",
                effective_date=trading_dates[-1],
                event_publication_ts=pd.Timestamp(trading_dates[-1]).to_pydatetime(),
                timestamp_source_class="official_exchange",
                source_name="fixture",
            )
        )
        session.commit()

    weights = pd.DataFrame(
        {"2330": [1.0, 1.0, 1.0]}, index=pd.to_datetime(trading_dates[-3:])
    )
    volume_df = pd.DataFrame(
        {"2330": [1_000_000, 1_000_000, 1_000_000]},
        index=weights.index,
    )

    result = p3_screening_service.build_p3_summary(
        request=_make_request(symbols=["2330"]),
        strategy=ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=1,
            allow_proactive_sells=True,
        ),
        weights=weights,
        volume_df=volume_df,
    )

    assert result["corporate_event_state"] == "unresolved_corporate_event"
    assert result["tradability_state"] == "unresolved_corporate_event"


def test_build_p3_summary_resolves_ticker_change_to_successor_symbol(monkeypatch):
    testing_session_local = _testing_session()
    monkeypatch.setattr(p3_screening_service, "SessionLocal", testing_session_local)
    trading_dates = _seed_daily_rows(
        testing_session_local,
        start=date(2024, 1, 1),
        days=150,
        symbols=["2330", "2330A"],
    )
    with testing_session_local() as session:
        session.add(
            SymbolLifecycleRecord(
                symbol="2330",
                market="TW",
                event_type="ticker_change",
                effective_date=trading_dates[-1],
                reference_symbol="2330A",
                source_name="fixture",
            )
        )
        session.add(
            ImportantEvent(
                symbol="2330",
                market="TW",
                event_type="ticker_change",
                effective_date=trading_dates[-1],
                event_publication_ts=pd.Timestamp(trading_dates[-1]).to_pydatetime(),
                timestamp_source_class="official_exchange",
                source_name="fixture",
            )
        )
        session.commit()

    weights = pd.DataFrame(
        {"2330": [1.0, 1.0, 1.0]}, index=pd.to_datetime(trading_dates[-3:])
    )
    volume_df = pd.DataFrame(
        {"2330": [1_000_000, 1_000_000, 1_000_000]},
        index=weights.index,
    )

    result = p3_screening_service.build_p3_summary(
        request=_make_request(symbols=["2330"]),
        strategy=ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=1,
            allow_proactive_sells=True,
        ),
        weights=weights,
        volume_df=volume_df,
    )

    assert result["corporate_event_state"] == "clear"
    assert result["tradability_state"] == "execution_ready"
    assert result["execution_universe_count"] == 1
    assert result["liquidity_bucket_coverages"][2]["execution_universe_count"] == 1


def test_build_p3_summary_fails_closed_when_ticker_change_mapping_is_missing(
    monkeypatch,
):
    testing_session_local = _testing_session()
    monkeypatch.setattr(p3_screening_service, "SessionLocal", testing_session_local)
    trading_dates = _seed_daily_rows(
        testing_session_local,
        start=date(2024, 1, 1),
        days=150,
        symbols=["2330"],
    )
    with testing_session_local() as session:
        session.add(
            SymbolLifecycleRecord(
                symbol="2330",
                market="TW",
                event_type="ticker_change",
                effective_date=trading_dates[-1],
                reference_symbol=None,
                source_name="fixture",
            )
        )
        session.add(
            ImportantEvent(
                symbol="2330",
                market="TW",
                event_type="ticker_change",
                effective_date=trading_dates[-1],
                event_publication_ts=pd.Timestamp(trading_dates[-1]).to_pydatetime(),
                timestamp_source_class="official_exchange",
                source_name="fixture",
            )
        )
        session.commit()

    weights = pd.DataFrame(
        {"2330": [1.0, 1.0, 1.0]}, index=pd.to_datetime(trading_dates[-3:])
    )
    volume_df = pd.DataFrame(
        {"2330": [1_000_000, 1_000_000, 1_000_000]},
        index=weights.index,
    )

    result = p3_screening_service.build_p3_summary(
        request=_make_request(symbols=["2330"]),
        strategy=ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=1,
            allow_proactive_sells=True,
        ),
        weights=weights,
        volume_df=volume_df,
    )

    assert result["corporate_event_state"] == "unresolved_corporate_event"
    assert result["tradability_state"] == "unresolved_corporate_event"
    assert result["execution_universe_count"] == 0


def test_build_p3_summary_allows_dividend_with_resolved_ticker_change(monkeypatch):
    testing_session_local = _testing_session()
    monkeypatch.setattr(p3_screening_service, "SessionLocal", testing_session_local)
    trading_dates = _seed_daily_rows(
        testing_session_local,
        start=date(2024, 1, 1),
        days=150,
        symbols=["2330", "2330A"],
    )
    with testing_session_local() as session:
        session.add(
            SymbolLifecycleRecord(
                symbol="2330",
                market="TW",
                event_type="ticker_change",
                effective_date=trading_dates[-2],
                reference_symbol="2330A",
                source_name="fixture",
            )
        )
        session.add(
            ImportantEvent(
                symbol="2330",
                market="TW",
                event_type="ticker_change",
                effective_date=trading_dates[-2],
                event_publication_ts=pd.Timestamp(trading_dates[-2]).to_pydatetime(),
                timestamp_source_class="official_exchange",
                source_name="fixture",
            )
        )
        session.add(
            ImportantEvent(
                symbol="2330A",
                market="TW",
                event_type="cash_dividend",
                effective_date=trading_dates[-1],
                event_publication_ts=pd.Timestamp(trading_dates[-1]).to_pydatetime(),
                timestamp_source_class="official_exchange",
                source_name="fixture",
            )
        )
        session.commit()

    weights = pd.DataFrame(
        {"2330": [1.0, 1.0, 1.0]},
        index=pd.to_datetime(trading_dates[-3:]),
    )
    volume_df = pd.DataFrame(
        {"2330": [1_000_000, 1_000_000, 1_000_000]},
        index=weights.index,
    )

    result = p3_screening_service.build_p3_summary(
        request=_make_request(symbols=["2330"]),
        strategy=ResearchStrategyConfig(
            type="research_v1",
            threshold=0.003,
            top_n=1,
            allow_proactive_sells=True,
        ),
        weights=weights,
        volume_df=volume_df,
    )

    assert result["corporate_event_state"] == "clear"
    assert result["tradability_state"] == "execution_ready"
    assert result["execution_universe_count"] == 1
