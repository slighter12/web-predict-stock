class BacktestError(Exception):
    status_code = 400


class DataNotFoundError(BacktestError):
    status_code = 404


class InsufficientDataError(BacktestError):
    status_code = 400


class UnsupportedConfigurationError(BacktestError):
    status_code = 400


class ExternalFetchError(BacktestError):
    status_code = 502

    def __init__(self, message: str, *, error_type: str | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type or type(self).__name__


class CalibrationBusyError(BacktestError):
    status_code = 429
    retry_after_seconds = 1


class CalibrationEvaluationError(BacktestError):
    status_code = 500


class DataAccessError(Exception):
    pass
