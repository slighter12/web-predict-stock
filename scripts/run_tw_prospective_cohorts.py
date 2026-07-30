from __future__ import annotations

import argparse
import json
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Create manual, strict TW prospective cohort runs.")
    parser.add_argument("--basis-date", required=True, type=date.fromisoformat)
    parser.add_argument("--cohort", choices=("2330", "all", "both"), default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cohort_ids = (
        (COHORT_2330, COHORT_ALL_ACTIVE)
        if args.cohort == "both"
        else (COHORT_2330 if args.cohort == "2330" else COHORT_ALL_ACTIVE,)
    )
    reports = []
    for cohort_id in cohort_ids:
        existing = valid_successful_cohort_runs(
            cohort_id=cohort_id,
            basis_date=args.basis_date,
        )
        if len(existing) == 1:
            reports.append(
                {
                    "cohort_id": cohort_id,
                    "basis_date": args.basis_date.isoformat(),
                    "status": "existing",
                    "run_id": existing[0]["run_id"],
                }
            )
            continue
        if len(existing) > 1:
            reports.append(
                {
                    "cohort_id": cohort_id,
                    "basis_date": args.basis_date.isoformat(),
                    "status": "no-opinion",
                    "reason": "Multiple valid strict runs already exist for this basis date.",
                    "run_ids": [record["run_id"] for record in existing],
                }
            )
            continue
        preflight = preflight_cohort(cohort_id=cohort_id, basis_date=args.basis_date)
        if args.dry_run or preflight["status"] != "ready":
            reports.append(preflight)
            continue
        payload = strict_request_payload(
            symbols=preflight["execution_symbols"],
            basis_date=args.basis_date,
            cohort_id=cohort_id,
            full_universe_symbols=preflight["full_universe_symbols"],
        )
        request = ResearchRunCreateRequest.model_validate(payload)
        response = create_research_run(
            request,
            request_id=f"prospective-{uuid4()}",
            run_id=prospective_run_id(
                cohort_id=cohort_id,
                basis_date=args.basis_date,
            ),
        )
        reports.append({**preflight, "run_id": response.run_id, "status": "created"})
    print(json.dumps({"basis_date": args.basis_date.isoformat(), "cohorts": reports}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
