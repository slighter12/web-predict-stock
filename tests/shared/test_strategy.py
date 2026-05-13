from backend.shared.analytics.strategy import build_comparison_eligibility


def test_build_comparison_eligibility_returns_research_comparable_for_complete_metadata():
    assert (
        build_comparison_eligibility(
            corporate_event_state="clear",
            price_basis_version="label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
            threshold_policy_version="static_absolute_gross_label_v1",
            execution_cost_model_version="fees_slippage_only_v1",
        )
        == "research_only_comparable"
    )


def test_build_comparison_eligibility_keeps_metadata_only_when_core_metadata_missing():
    assert (
        build_comparison_eligibility(
            corporate_event_state="clear",
            price_basis_version=None,
            threshold_policy_version="static_absolute_gross_label_v1",
            execution_cost_model_version="fees_slippage_only_v1",
        )
        == "comparison_metadata_only"
    )


def test_build_comparison_eligibility_prioritizes_event_quarantine():
    assert (
        build_comparison_eligibility(
            corporate_event_state="unresolved_corporate_event",
            price_basis_version="label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
            threshold_policy_version="static_absolute_gross_label_v1",
            execution_cost_model_version="fees_slippage_only_v1",
        )
        == "unresolved_event_quarantine"
    )


def test_build_comparison_eligibility_reports_sample_window_pending():
    assert (
        build_comparison_eligibility(
            corporate_event_state="clear",
            price_basis_version="label_open_to_open__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1",
            threshold_policy_version="static_absolute_gross_label_v1",
            execution_cost_model_version="fees_slippage_only_v1",
            sample_window_pending=True,
        )
        == "sample_window_pending"
    )
