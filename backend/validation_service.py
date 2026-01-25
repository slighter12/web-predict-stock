from typing import List, Tuple


def generate_splits(
    length: int,
    method: str,
    splits: int,
    test_size: float,
) -> List[Tuple[range, range]]:
    if length <= 0:
        raise ValueError("length must be positive")
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1")
    if splits < 1:
        raise ValueError("splits must be >= 1")

    test_len = int(length * test_size)
    if test_len <= 0:
        raise ValueError("test_size too small for available data")

    method = method.lower()
    if method == "holdout":
        if length <= test_len:
            raise ValueError("Not enough data for holdout split")
        train_range = range(0, length - test_len)
        test_range = range(length - test_len, length)
        return [(train_range, test_range)]

    if length <= test_len * splits:
        raise ValueError("Not enough data for the requested number of splits")

    train_len = length - test_len * splits
    split_ranges: List[Tuple[range, range]] = []

    if method in {"walk_forward", "expanding_window"}:
        for i in range(splits):
            train_end = train_len + i * test_len
            test_start = train_end
            test_end = test_start + test_len
            split_ranges.append((range(0, train_end), range(test_start, test_end)))
        return split_ranges

    if method == "rolling_window":
        for i in range(splits):
            train_start = i * test_len
            train_end = train_start + train_len
            test_start = train_end
            test_end = test_start + test_len
            split_ranges.append((range(train_start, train_end), range(test_start, test_end)))
        return split_ranges

    raise ValueError(f"Unknown validation method: {method}")
