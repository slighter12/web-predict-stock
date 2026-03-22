from __future__ import annotations

import logging
from typing import Any, Callable
from uuid import uuid4

from ..errors import BacktestError, DataAccessError
from ..repositories.research_run_repository import (
    get_research_run_record,
    list_research_run_records,
)
from ..schemas.research_runs import (
    ResearchRunCreateRequest,
    ResearchRunRecordResponse,
    ResearchRunResponse,
)
from .backtest_engine_service import execute_research_run
from .research_run_registry_service import (
    record_failure,
    record_rejection,
    record_started,
    record_success,
    record_unexpected_failure,
)

logger = logging.getLogger(__name__)


def _record_registry_event(
    callback: Callable[..., dict[str, Any]],
    *,
    raise_on_failure: bool = False,
    **kwargs: Any,
) -> None:
    try:
        callback(**kwargs)
    except DataAccessError:
        logger.exception(
            "Failed to persist research run record run_id=%s",
            kwargs.get("run_id"),
        )
        if raise_on_failure:
            raise


def create_research_run(
    request: ResearchRunCreateRequest, request_id: str, run_id: str | None = None
) -> ResearchRunResponse:
    run_id = run_id or str(uuid4())
    runtime_context = None
    try:
        _record_registry_event(
            record_started,
            raise_on_failure=True,
            run_id=run_id,
            request_id=request_id,
            request=request,
        )
        artifacts = execute_research_run(run_id=run_id, request=request)
        runtime_context = artifacts.runtime_context
        _record_registry_event(
            record_success,
            raise_on_failure=True,
            run_id=run_id,
            request_id=request_id,
            request=request,
            runtime_context=runtime_context,
            response=artifacts.response,
            validation_summary=artifacts.validation_summary,
            warnings=artifacts.warnings,
        )
        return artifacts.response
    except BacktestError as exc:
        # Preserve the original rejection even if audit persistence fails.
        _record_registry_event(
            record_rejection,
            run_id=run_id,
            request_id=request_id,
            request=request,
            runtime_context=runtime_context,
            exc=exc,
        )
        raise
    except DataAccessError as exc:
        # Preserve the original storage failure instead of masking it with
        # a second registry persistence error.
        _record_registry_event(
            record_failure,
            run_id=run_id,
            request_id=request_id,
            request=request,
            runtime_context=runtime_context,
            exc=exc,
        )
        raise
    except Exception as exc:
        # Preserve the unexpected application error as the primary failure.
        _record_registry_event(
            record_unexpected_failure,
            run_id=run_id,
            request_id=request_id,
            request=request,
            runtime_context=runtime_context,
            rejection_reason=str(exc),
        )
        raise


def get_research_run(run_id: str) -> ResearchRunRecordResponse:
    return ResearchRunRecordResponse(**get_research_run_record(run_id))


def list_research_runs(limit: int = 20) -> list[ResearchRunRecordResponse]:
    return [
        ResearchRunRecordResponse(**item)
        for item in list_research_run_records(limit=limit)
    ]
