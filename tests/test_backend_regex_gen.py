import re

import pytest

from backend import regex_gen


def test_regex_from_examples_infers_clean_pattern():
    result = regex_gen.regex_from_examples(["Rv1000", "Rv2070c", "Rv3415A"])

    assert result["regex"] == r"^Rv\d{4}[Ac]?$"
    assert all(entry["ok"] for entry in result["matched"])
    assert [entry["value"] for entry in result["matched"]] == [
        "Rv1000",
        "Rv2070c",
        "Rv3415A",
    ]
    assert result["explanation"]


def test_regex_from_examples_strips_and_dedupes():
    result = regex_gen.regex_from_examples([" Rv1000 ", "Rv1000", "", "Rv2070c"])

    compiled = re.compile(result["regex"])
    assert compiled.fullmatch("Rv1000")
    assert compiled.fullmatch("Rv2070c")
    assert len(result["matched"]) == 2


def test_regex_from_examples_requires_examples():
    with pytest.raises(ValueError):
        regex_gen.regex_from_examples(["", "   "])
