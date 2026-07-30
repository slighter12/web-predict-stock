from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import backend.market_data.repositories.company_profiles as company_profile_repository
from backend.database import Base, TwCompanyProfile


def test_reconciliation_updates_lineage_for_inactivated_profiles(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[TwCompanyProfile.__table__])
    monkeypatch.setattr(
        company_profile_repository,
        "SessionLocal",
        testing_session_local,
    )
    with testing_session_local() as session:
        session.add_all(
            [
                TwCompanyProfile(
                    symbol="2330",
                    market="TW",
                    exchange="TWSE",
                    board="listed",
                    company_name="TSMC",
                    trading_status="active",
                    source_name="old_feed",
                ),
                TwCompanyProfile(
                    symbol="2317",
                    market="TW",
                    exchange="TWSE",
                    board="listed",
                    company_name="Hon Hai",
                    trading_status="active",
                    source_name="old_feed",
                ),
                TwCompanyProfile(
                    symbol="US01",
                    market="US",
                    exchange="TWSE",
                    board="listed",
                    company_name="Different Market",
                    trading_status="active",
                    source_name="old_feed",
                ),
            ]
        )
        session.commit()

    updated_count = (
        company_profile_repository.mark_missing_active_tw_company_profiles_inactive(
            exchange="twse",
            active_symbols={"2330"},
            source_name="twse_company_profile",
            raw_payload_id=42,
            archive_object_reference="raw_ingest_audit:42",
        )
    )

    with testing_session_local() as session:
        profiles = {
            (profile.market, profile.symbol): profile
            for profile in session.scalars(select(TwCompanyProfile)).all()
        }

    assert updated_count == 1
    assert profiles[("TW", "2330")].trading_status == "active"
    assert profiles[("US", "US01")].trading_status == "active"
    inactivated = profiles[("TW", "2317")]
    assert inactivated.trading_status == "inactive"
    assert inactivated.source_name == "twse_company_profile"
    assert inactivated.raw_payload_id == 42
    assert inactivated.archive_object_reference == "raw_ingest_audit:42"
