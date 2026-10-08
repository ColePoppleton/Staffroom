import pytest

from staffroom.core.table import Table, coerce


def test_shape_and_column() -> None:
    t = Table(["a", "b"], [[1, "x"], [2, "y"]])
    assert t.shape == (2, 2)
    assert t.column("b") == ["x", "y"]


def test_ragged_rows_rejected() -> None:
    with pytest.raises(ValueError, match="row 0"):
        Table(["a", "b"], [[1]])


def test_round_trip_dicts() -> None:
    t = Table.from_dicts([{"a": 1, "b": 2}, {"a": 3}])
    assert t.columns == ["a", "b"]
    assert t.to_dicts() == [{"a": 1, "b": 2}, {"a": 3, "b": None}]


def test_with_column_select_sort() -> None:
    t = Table(["n", "v"], [["x", 3], ["y", 1], ["z", None]])
    t2 = t.with_column("double", lambda r: (r["v"] or 0) * 2)
    assert t2.column("double") == [6, 2, 0]
    assert t2.select(["double"]).columns == ["double"]
    assert t.sorted_by("v").column("n") == ["y", "x", "z"]
    with pytest.raises(ValueError, match="already exists"):
        t.with_column("v", lambda r: 0)
    with pytest.raises(KeyError):
        t.column("missing")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3", 3), (" 2.5 ", 2.5), ("true", True), ("", None), ("Ada", "Ada"), (7, 7), (None, None)],
)
def test_coerce(raw: object, expected: object) -> None:
    assert coerce(raw) == expected
