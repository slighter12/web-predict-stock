from __future__ import annotations

import argparse
import json

from backend.research.services.prospective import (
    COHORT_2330,
    COHORT_ALL_ACTIVE,
    evaluate_cohort,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only evaluator for strict TW prospective cohorts.")
    parser.add_argument("--cohort", choices=("2330", "all"), required=True)
    args = parser.parse_args()
    cohort_id = COHORT_2330 if args.cohort == "2330" else COHORT_ALL_ACTIVE
    print(json.dumps(evaluate_cohort(cohort_id), ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
