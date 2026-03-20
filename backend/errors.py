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


class DataAccessError(Exception):
    pass
