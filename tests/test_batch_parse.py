import pytest

from autoannotation import batch_parse


def test_parse_single_column_newlines():
    entries = batch_parse.parse_batch_text("Rv0001\nRv0002\n# comment\ndnaA\n")
    assert entries == [
        {"input": "Rv0001"},
        {"input": "Rv0002"},
        {"input": "dnaA"},
    ]


def test_parse_single_column_commas():
    entries = batch_parse.parse_batch_text("Rv0001, Rv0002, dnaA")
    assert len(entries) == 3


def test_parse_two_column_csv_with_header():
    text = "locus,name\nRv0001,dnaA\nRv0002,\n"
    entries = batch_parse.parse_batch_text(text)
    assert entries == [
        {"locus": "Rv0001", "name": "dnaA"},
        {"locus": "Rv0002", "name": None},
    ]


def test_parse_rejects_three_columns():
    with pytest.raises(batch_parse.BatchParseError, match="two columns"):
        batch_parse.parse_batch_text("a,b,c\n")


def test_parse_strips_bom_and_quotes():
    entries = batch_parse.parse_batch_text('\ufeff"Rv0001"\n')
    assert entries == [{"input": "Rv0001"}]


def test_parse_empty_raises():
    with pytest.raises(batch_parse.BatchParseError, match="No genes found"):
        batch_parse.parse_batch_text("  \n# only comments\n")
