from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from uuid import uuid4

from backend.research.contracts.runs import ResearchRunCreateRequest
from backend.research.services.prospective import (
    COHORT_2330,
    COHORT_ALL_ACTIVE,
    preflight_cohort,
    prospective_run_id,
    strict_request_payload,
    valid_successful_cohort_runs,
)
from backend.research.services.runs import create_research_run

logger = logging.getLogger(__name__)


def _cohort_report(
    *, cohort_id: str, basis_date: date, dry_run: bool
) -> dict:
    context = {
        "cohort_id": cohort_id,
        "basis_date": basis_date.isoformat(),
    }
    try:
        existing = valid_successful_cohort_runs(
            cohort_id=cohort_id,
            basis_date=basis_date,
        )
        if len(existing) == 1:
            return {
                **context,
                "status": "existing",
                "run_id": existing[0]["run_id"],
            }
        if len(existing) > 1:
            return {
                **context,
                "status": "error",
                "failure_kind": "duplicate_valid_runs",
                "reason": "Multiple valid strict runs already exist for this basis date.",
                "run_ids": [record["run_id"] for record in existing],
            }

        preflight = preflight_cohort(cohort_id=cohort_id, basis_date=basis_date)
        context = preflight
        if dry_run or preflight["status"] != "ready":
            return preflight

        payload = strict_request_payload(
            symbols=preflight["execution_symbols"],
            basis_date=basis_date,
            cohort_id=cohort_id,
            full_universe_symbols=preflight["full_universe_symbols"],
        )
        request = ResearchRunCreateRequest.model_validate(payload)
        response = create_research_run(
            request,
            request_id=f"prospective-{uuid4()}",
            run_id=prospective_run_id(
                cohort_id=cohort_id,
                basis_date=basis_date,
            ),
        )
        return {**preflight, "run_id": response.run_id, "status": "created"}
    except Exception as exc:
        logger.exception(
            "Failed to process prospective cohort cohort_id=%s basis_date=%s",
            cohort_id,
            basis_date,
        )
        return {
            **context,
            "status": "error",
            "failure_kind": type(exc).__name__,
            "reason": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create manual, strict TW prospective cohort runs.",
        epilog=(
            "The all-active preflight performs per-symbol model fitting and can "
            "be long-running; progress is logged periodically."
        ),
    )
    parser.add_argument("--basis-date", required=True, type=date.fromisoformat)
    parser.add_argument("--cohort", choices=("2330", "all", "both"), default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cohort_ids = (
        (COHORT_2330, COHORT_ALL_ACTIVE)
        if args.cohort == "both"
        else (COHORT_2330 if args.cohort == "2330" else COHORT_ALL_ACTIVE,)
    )
    reports = [
        _cohort_report(
            cohort_id=cohort_id,
            basis_date=args.basis_date,
            dry_run=args.dry_run,
        )
        for cohort_id in cohort_ids
    ]
    print(json.dumps({"basis_date": args.basis_date.isoformat(), "cohorts": reports}, ensure_ascii=False))
    return 1 if any(report["status"] == "error" for report in reports) else 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    raise SystemExit(main())
