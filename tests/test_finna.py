from app.finna import (
    _extract_authors,
    _extract_formats,
    _select_best,
    normalize_record,
)
from app.isbn import ISBN


def test_extract_authors_from_object():
    authors = {
        "primary": {"Liksom, Rosa": {"role": ["kirjoittaja"]}},
        "secondary": ["Kääntäjä, Kalle"],
        "corporate": [],
    }
    assert _extract_authors(authors) == ["Liksom, Rosa", "Kääntäjä, Kalle"]


def test_extract_authors_handles_non_dict():
    assert _extract_authors(None) == []
    assert _extract_authors([]) == []


def test_extract_formats_prefers_translated():
    formats = [
        {"value": "0/Book/", "translated": "Kirja"},
        {"value": "1/Book/Book/", "translated": "Kirja"},
    ]
    assert _extract_formats(formats) == ["Kirja"]


def test_normalize_record(book_record):
    isbn = ISBN.parse("9789510392652")
    result = normalize_record(book_record, isbn, include_raw=False)
    assert result["isbn13"] == "9789510392652"
    assert result["isbn10"] == "9510392650"
    assert result["title"] == "Hytti nro 6"
    assert result["subtitle"] == "romaani"
    assert result["authors"] == ["Liksom, Rosa"]
    assert result["year"] == 2011
    assert result["publisher"] == "WSOY"
    assert result["languages"] == ["fin"]
    assert result["formats"] == ["Kirja"]
    assert result["finna_id"] == "helka.993408423506253"
    assert result["finna_url"] == "https://www.finna.fi/Record/helka.993408423506253"
    assert result["cover_url"].startswith("https://www.finna.fi/Cover/Show")
    assert result["source"] == "finna"
    assert "raw" not in result


def test_cover_url_fallback_to_isbn_endpoint():
    isbn = ISBN.parse("9789510392652")
    record = {"id": "x.1", "title": "T", "images": []}
    result = normalize_record(record, isbn, include_raw=False)
    assert result["cover_url"] == ("https://www.finna.fi/Cover/Show?isbn=9789510392652&size=large")


def test_finna_url_encodes_id():
    isbn = ISBN.parse("9789510392652")
    record = {"id": "siiri.urn:nbn/fi-abc", "title": "T", "images": []}
    result = normalize_record(record, isbn, include_raw=False)
    assert result["finna_url"] == "https://www.finna.fi/Record/siiri.urn%3Anbn%2Ffi-abc"


def test_select_best_prefers_matching_book():
    isbn = ISBN.parse("9789510392652")
    audiobook = {
        "id": "a.audio",
        "cleanIsbn": "9510392650",
        "formats": [{"value": "0/Book/"}, {"value": "1/Book/AudioBook/"}],
    }
    video = {"id": "a.video", "isbns": [], "formats": [{"value": "0/Video/"}]}
    book = {
        "id": "a.book",
        "cleanIsbn": "9510392650",
        "formats": [{"value": "0/Book/"}, {"value": "1/Book/Book/"}],
    }
    # order: video first, audiobook, book -> best must be the plain book
    best = _select_best([video, audiobook, book], isbn)
    assert best["id"] == "a.book"


def test_select_best_falls_back_to_first_when_no_match():
    isbn = ISBN.parse("9789510392652")
    other = {"id": "a.other", "cleanIsbn": "0000000000", "formats": [{"value": "0/Video/"}]}
    best = _select_best([other], isbn)
    assert best["id"] == "a.other"
