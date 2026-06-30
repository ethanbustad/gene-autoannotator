import re

HEADER_TOKENS = frozenset({"locus", "gene", "name", "id"})


class BatchParseError(ValueError):
    pass


def parse_batch_text(text, *, delimiter=None):
    text = str(text or "").lstrip("\ufeff")
    lines = text.splitlines()
    non_comment_lines = [
        line for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    if not non_comment_lines:
        raise BatchParseError("No genes found.")

    mode, split_delim = _detect_format(non_comment_lines, delimiter=delimiter)
    if mode == "two_column":
        return _parse_two_column(non_comment_lines, split_delim)
    return _parse_single_column(non_comment_lines)


def _detect_format(lines, *, delimiter=None):
    if delimiter == "tab":
        field_counts = [len(line.split("\t")) for line in lines]
        if any(count >= 3 for count in field_counts):
            raise BatchParseError("Only one column or two columns (locus, name) are supported.")
        if any(count == 2 for count in field_counts):
            return "two_column", "\t"

    field_counts = [len(re.split(r"[,\t]", line)) for line in lines]
    if len(lines) == 1 and field_counts[0] >= 3:
        tokens = [_clean_token(token) for token in re.split(r"[,\t]", lines[0])]
        if tokens and all(token and len(token) == 1 for token in tokens):
            raise BatchParseError("Only one column or two columns (locus, name) are supported.")
    if any(count == 2 for count in field_counts):
        if any(count >= 3 for count in field_counts):
            raise BatchParseError("Only one column or two columns (locus, name) are supported.")
        split_delim = "\t" if all("\t" in line and "," not in line for line in lines) else ","
        return "two_column", split_delim
    return "single_column", None


def _parse_single_column(lines):
    entries = []
    for line in lines:
        for token in re.split(r"[\n,;\t]+", line):
            cleaned = _clean_token(token)
            if cleaned:
                entries.append({"input": cleaned})
    if not entries:
        raise BatchParseError("No genes found.")
    return entries


def _parse_two_column(lines, split_delim):
    data_lines = list(lines)
    first_fields = [field.strip() for field in data_lines[0].split(split_delim)]
    if len(first_fields) == 2 and all(field.casefold() in HEADER_TOKENS for field in first_fields if field):
        data_lines = data_lines[1:]
    entries = []
    for line in data_lines:
        fields = line.split(split_delim)
        if len(fields) != 2:
            raise BatchParseError("Only one column or two columns (locus, name) are supported.")
        locus = _clean_token(fields[0]) or None
        name = _clean_token(fields[1]) or None
        if not locus and not name:
            continue
        entries.append({"locus": locus, "name": name})
    if not entries:
        raise BatchParseError("No genes found.")
    return entries


def _clean_token(value):
    value = str(value).strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1].strip()
    return value or None
