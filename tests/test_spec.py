import pytest

from teaching_tools.core import spec


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
        spec.load_taxonomy("edexcel")
