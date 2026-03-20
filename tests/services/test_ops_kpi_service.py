from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.services.ops_kpi_service as ops_kpi_service
from backend.database import (
    Base,
    DailyOHLCV,
    ImportantEvent,
    IngestionWatchlist,
    NormalizedReplayRun,
    RecoveryDrill,
    RecoveryDrillSchedule,
    ScheduledIngestionAttempt,
    ScheduledIngestionRun,
    SymbolLifecycleRecord,
)


def test_get_ops_kpi_summary_returns_gate_pass(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            DailyOHLCV.__table__,
            IngestionWatchlist.__table__,
            ScheduledIngestionRun.__table__,
            ScheduledIngestionAttempt.__table__,
            NormalizedReplayRun.__table__,
            RecoveryDrill.__table__,
            RecoveryDrillSchedule.__table__,
            ImportantEvent.__table__,
            SymbolLifecycleRecord.__table__,
        ],
    )
    monkeypatch.setattr(ops_kpi_service, "SessionLocal", testing_session_local)

    reference_time = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
    trading_days = [date(2026, 3, day) for day in range(1, 21)]
    monkeypatch.setattr(
        ops_kpi_service,
        "list_market_trading_days",
        lambda market, **kwargs: (
            [trading_days[-1]]
            if kwargs.get("descending") and kwargs.get("limit") == 1
            else list(reversed(trading_days))
            if kwargs.get("descending")
            else trading_days
        ),
    )

    with testing_session_local() as session:
        watchlist = IngestionWatchlist(
            symbol="2330",
            market="TW",
            years=5,
            is_active=True,
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        session.add(watchlist)
        session.flush()

        session.add(
            SymbolLifecycleRecord(
                symbol="2330",
                market="TW",
                event_type="listing",
                effective_date=date(2000, 1, 1),
                source_name="seed",
                created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            )
        )

        for trading_day in trading_days:
            session.add(
                DailyOHLCV(
                    date=trading_day,
                    symbol="2330",
                    source="twse",
                    market="TW",
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                )
            )
            run = ScheduledIngestionRun(
                watchlist_id=watchlist.id,
                symbol="2330",
                market="TW",
                scheduled_for_date=trading_day,
                status="succeeded",
                attempt_count=1,
                first_attempt_at=datetime.combine(
                    trading_day, time(9, 0), tzinfo=timezone.utc
                ),
                last_attempt_at=datetime.combine(
                    trading_day, time(9, 5), tzinfo=timezone.utc
                ),
                completed_at=datetime.combine(
                    trading_day, time(9, 5), tzinfo=timezone.utc
                ),
                created_at=datetime.combine(
                    trading_day, time(9, 0), tzinfo=timezone.utc
                ),
            )
            session.add(run)
            session.flush()
            session.add(
                ScheduledIngestionAttempt(
                    run_id=run.id,
                    attempt_number=1,
                    status="succeeded",
                    raw_payload_id=run.id,
                    started_at=run.first_attempt_at,
                    completed_at=run.completed_at,
                    created_at=run.created_at,
                )
            )

        session.add(
            NormalizedReplayRun(
                raw_payload_id=1,
                source_name="twse",
                symbol="2330",
                market="TW",
                parser_version="v1",
                benchmark_profile_id="one_week_rebuild_v1",
                notes=None,
                restore_status="succeeded",
                abort_reason=None,
                restored_row_count=5,
                replay_started_at=datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc),
                replay_completed_at=datetime(2026, 3, 20, 1, 0, tzinfo=timezone.utc),
                created_at=reference_time,
            )
        )
        session.add(
            RecoveryDrillSchedule(
                market="TW",
                symbol="2330",
                cadence="monthly",
                day_of_month=20,
                timezone="Asia/Taipei",
                benchmark_profile_id="one_week_rebuild_v1",
                notes=None,
                is_active=True,
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        )
        session.flush()
        schedule_id = session.query(RecoveryDrillSchedule).one().id
        session.add(
            RecoveryDrill(
                raw_payload_id=1,
                replay_run_id=1,
                benchmark_profile_id="one_week_rebuild_v1",
                notes=None,
                status="succeeded",
                trigger_mode="scheduled",
                schedule_id=schedule_id,
                scheduled_for_date=date(2026, 3, 20),
                latest_replayable_day=date(2026, 3, 19),
                completed_trading_day_delta=1,
                abort_reason=None,
                drill_started_at=datetime(2026, 3, 20, 2, 0, tzinfo=timezone.utc),
                drill_completed_at=datetime(2026, 3, 20, 3, 0, tzinfo=timezone.utc),
                created_at=reference_time,
            )
        )
        for offset in range(5):
            publication_ts = datetime(2026, 3, 10 + offset, 0, 0, tzinfo=timezone.utc)
            session.add(
                ImportantEvent(
                    symbol="2330",
                    market="TW",
                    event_type="cash_dividend",
                    effective_date=date(2026, 3, 15 + offset),
                    event_publication_ts=publication_ts,
                    timestamp_source_class="official_exchange",
                    source_name="tw_official_important_event",
                    raw_payload_id=10 + offset,
                    archive_object_reference=f"raw_ingest_audit:{10 + offset}",
                    notes=None,
                    created_at=publication_ts + timedelta(hours=1),
                )
            )
        session.commit()

    summary = ops_kpi_service.get_ops_kpi_summary(reference_time=reference_time)

    assert summary["overall_status"] == "pass"
    assert summary["metrics"]["KPI-DATA-001"]["status"] == "pass"
    assert summary["metrics"]["KPI-DATA-002"]["status"] == "pass"
    assert summary["metrics"]["KPI-DATA-003"]["status"] == "pass"
    assert summary["metrics"]["KPI-DATA-004"]["status"] == "pass"
    assert summary["metrics"]["KPI-DATA-005"]["status"] == "pass"
    assert summary["metrics"]["KPI-DATA-006"]["status"] == "pass"
    assert summary["metrics"]["KPI-DATA-007"]["status"] == "pass"
    assert summary["metrics"]["KPI-DATA-008"]["value"] == 5.0


def test_get_ops_kpi_summary_allows_insufficient_sample_gate(monkeypatch):
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_001_and_002",
        lambda reference_date: (
            ops_kpi_service._metric(value=100, status="pass", window="window"),
            ops_kpi_service._metric(value=100, status="pass", window="window"),
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_003",
        lambda reference_date: ops_kpi_service._metric(
            value=100,
            status="pass",
            window="window",
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_004",
        lambda reference_date: ops_kpi_service._metric(
            value=1,
            status="pass",
            window="window",
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_005",
        lambda reference_date: ops_kpi_service._metric(
            value=1,
            status="pass",
            window="window",
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_006_and_008",
        lambda reference_date: (
            ops_kpi_service._metric(
                value=None,
                status="insufficient_sample",
                window="window",
            ),
            ops_kpi_service._metric(
                value=4,
                status="insufficient_sample",
                window="window",
            ),
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_007",
        lambda reference_date: ops_kpi_service._metric(
            value=100,
            status="pass",
            window="window",
        ),
    )

    summary = ops_kpi_service.get_ops_kpi_summary(
        reference_time=datetime(2026, 3, 20, tzinfo=timezone.utc)
    )

    assert summary["overall_status"] == "pass"
    assert summary["metrics"]["KPI-DATA-006"]["status"] == "insufficient_sample"


def test_get_ops_kpi_summary_fails_when_recovery_gate_metric_fails(monkeypatch):
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_001_and_002",
        lambda reference_date: (
            ops_kpi_service._metric(value=100, status="pass", window="window"),
            ops_kpi_service._metric(value=100, status="pass", window="window"),
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_003",
        lambda reference_date: ops_kpi_service._metric(
            value=100,
            status="pass",
            window="window",
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_004",
        lambda reference_date: ops_kpi_service._metric(
            value=2,
            status="fail",
            window="window",
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_005",
        lambda reference_date: ops_kpi_service._metric(
            value=1,
            status="pass",
            window="window",
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_006_and_008",
        lambda reference_date: (
            ops_kpi_service._metric(
                value=12,
                status="pass",
                window="window",
            ),
            ops_kpi_service._metric(
                value=5,
                status="pass",
                window="window",
            ),
        ),
    )
    monkeypatch.setattr(
        ops_kpi_service,
        "_calculate_kpi_data_007",
        lambda reference_date: ops_kpi_service._metric(
            value=100,
            status="pass",
            window="window",
        ),
    )

    summary = ops_kpi_service.get_ops_kpi_summary(
        reference_time=datetime(2026, 3, 20, tzinfo=timezone.utc)
    )

    assert summary["overall_status"] == "fail"
    assert summary["metrics"]["KPI-DATA-004"]["status"] == "fail"
