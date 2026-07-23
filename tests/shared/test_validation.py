import pytest

from backend.shared.analytics.validation import generate_splits


def test_generate_splits_holdout():
    splits = generate_splits(length=100, method="holdout", splits=1, test_size=0.2)
    assert len(splits) == 1
    train_range, test_range = splits[0]
    assert train_range.start == 0
    assert train_range.stop == 80
    assert test_range.start == 80
    assert test_range.stop == 100


def test_generate_splits_walk_forward():
    splits = generate_splits(length=100, method="walk_forward", splits=2, test_size=0.2)
    assert len(splits) == 2

    train_range, test_range = splits[0]
    assert train_range.start == 0
    assert train_range.stop == 60
    assert test_range.start == 60
    assert test_range.stop == 80

    train_range, test_range = splits[1]
    assert train_range.start == 0
    assert train_range.stop == 80
    assert test_range.start == 80
    assert test_range.stop == 100


def test_generate_splits_rolling():
    splits = generate_splits(
        length=100, method="rolling_window", splits=2, test_size=0.2
    )
    assert len(splits) == 2

    train_range, test_range = splits[0]
    assert train_range.start == 0
    assert train_range.stop == 60
    assert test_range.start == 60
    assert test_range.stop == 80

    train_range, test_range = splits[1]
    assert train_range.start == 20
    assert train_range.stop == 80
    assert test_range.start == 80
    assert test_range.stop == 100


def test_generate_splits_expanding_window():
    splits = generate_splits(
        length=100, method="expanding_window", splits=2, test_size=0.2
    )
    assert len(splits) == 2

    train_range, test_range = splits[0]
    assert train_range.start == 0
    assert train_range.stop == 60
    assert test_range.start == 60
    assert test_range.stop == 80

    train_range, test_range = splits[1]
    assert train_range.start == 0
    assert train_range.stop == 80
    assert test_range.start == 80
    assert test_range.stop == 100


def test_generate_splits_invalid_method():
    with pytest.raises(ValueError):
        generate_splits(length=100, method="bad", splits=1, test_size=0.2)


@pytest.mark.parametrize(
    ("method", "expected_stops"),
    [
        ("holdout", [77]),
        ("walk_forward", [57, 77]),
        ("expanding_window", [57, 77]),
        ("rolling_window", [57, 77]),
    ],
)
def test_generate_splits_purges_training_targets(method, expected_stops):
    splits = generate_splits(
        length=100, method=method, splits=2, test_size=0.2, purge=3
    )

    assert [train_range.stop for train_range, _ in splits] == expected_stops
    assert all(
        test_range.start - train_range.stop == 3
        for train_range, test_range in splits
    )
