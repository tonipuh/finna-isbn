import pytest

from app.isbn import (
    ISBN,
    InvalidISBNError,
    is_valid_isbn10,
    is_valid_isbn13,
    normalize,
    to_isbn10,
    to_isbn13,
)


def test_normalize_strips_hyphens_and_spaces():
    assert normalize(" 978-951-0-39265-2 ") == "9789510392652"
    assert normalize("951123456x") == "951123456X"


def test_valid_isbn13():
    assert is_valid_isbn13("9789510392652")
    assert not is_valid_isbn13("9789510392653")  # wrong checksum
    assert not is_valid_isbn13("1234567890123")  # wrong prefix


def test_valid_isbn10():
    assert is_valid_isbn10("9510392650")
    assert not is_valid_isbn10("9510392651")


def test_conversion_roundtrip():
    assert to_isbn13("9510392650") == "9789510392652"
    assert to_isbn10("9789510392652") == "9510392650"
    # 979-prefixed ISBN-13 has no ISBN-10 equivalent
    assert to_isbn10("9790000000000") is None


def test_isbn_parse_from_both_forms():
    a = ISBN.parse("978-951-0-39265-2")
    b = ISBN.parse("951-0-39265-0")
    assert a.isbn13 == b.isbn13 == "9789510392652"
    assert a.isbn10 == b.isbn10 == "9510392650"


def test_isbn_parse_rejects_invalid():
    with pytest.raises(InvalidISBNError):
        ISBN.parse("1234567890")
    with pytest.raises(InvalidISBNError):
        ISBN.parse("12345")
