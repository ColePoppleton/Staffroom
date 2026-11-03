import pytest

from staffroom.core import spec


def test_taxonomies_load_and_lookup() -> None:
    ocr = spec.load_taxonomy("ocr")
    aqa = spec.load_taxonomy("AQA")
    assert len(ocr) >= 20 and len(aqa) >= 25
    point = spec.find("ocr:1.2.4")
    assert point and point.title.startswith("Data storage") and point.unit.startswith("1.2")
    assert point.matches("1.2") and point.matches("1.2.4") and not point.matches("1.2.")
    assert spec.find("aqa:3.3.4").title == "Binary arithmetic"  # type: ignore[union-attr]
    assert spec.find("ocr:9.9.9") is None and spec.find("nope:1") is None
    assert spec.describe("aqa:3.6.2") == "aqa:3.6.2 Cyber security threats"
    assert spec.describe("topic:loops") == "topic:loops"
    with pytest.raises(ValueError, match="unknown board"):
        spec.load_taxonomy("wjec")


@pytest.mark.parametrize("board", list(spec.BOARDS))
def test_every_board_has_unique_codes_and_titles(board: str) -> None:
    points = spec.load_taxonomy(board)
    codes = [p.code for p in points]
    assert len(codes) == len(set(codes)), "duplicate spec codes"
    assert all(p.title.strip() and p.unit.strip() for p in points)
    # Every point sits in the unit its code starts with.
    assert all(p.unit.split(" ", 1)[0] == p.code.rsplit(".", 1)[0] for p in points)
    assert board in spec.SHORT_NAMES


def test_edexcel_1cp2_topics_and_subtopics() -> None:
    points = spec.load_taxonomy("edexcel")
    units = {p.unit for p in points}
    # Topics 1-5 are Paper 1, Topic 6 is Paper 2; 20 subtopics and 66 points in Issue 1.
    assert {u.split(".", 1)[0] for u in units} == {"1", "2", "3", "4", "5", "6"}
    assert len(units) == 20 and len(points) == 66
    assert spec.describe("edexcel:1.3.1").startswith("edexcel:1.3.1 Truth tables with AND, OR")
    assert spec.find("edexcel:6.4.2").unit == "6.4 Input/output"  # type: ignore[union-attr]
    assert spec.find("edexcel:2.1.6").matches("2.1")  # type: ignore[union-attr]


def test_edexcel_names_the_specification_issue_it_follows() -> None:
    src = spec.source("edexcel")
    assert "1CP2" in src["document"]
    assert src["issue"] == "Issue 1" and src["date"] == "January 2020"
    assert src["url"].startswith("https://qualifications.pearson.com/")
    assert spec.source("ocr") == {}  # older files do not say yet


def test_board_choices_reads_boards() -> None:
    assert spec.board_choices() == "ocr, aqa or edexcel"
    assert spec.board_choices("|", "|") == "ocr|aqa|edexcel"
