"""One canon of what the platform signs — RFC 8785 (JCS), whole (ADR-0072): one table of vectors for the course and the
product (`testdata/canonical_json.tsv`, the product's first, a copy here byte for byte). A row is a JSON text as it may
come, its RFC 8785 form and the sha256 of that form's UTF-8. The course's side: `trust.jcs.jcs` over the platform's one
reading (`canonical.parse_json`) writes every row's form, and a signed document's signature covers exactly that form.
The course signed `json.dumps(sort_keys=True)` and the product `json.Marshal`: `A&B <gate>` and `1.0` signed by one did
not verify at the other (the external review of 2026-10-11, its fourth defect)."""
from __future__ import annotations

from tests.frozen_data import frozen_testdata

import hashlib
import math
import os

from tests.productdir import SOURCE, product_file

TABLE = os.path.join(frozen_testdata(), "canonical_json.tsv")


def _rows():
    """(line, input, canon, sha256) of every row."""
    with open(TABLE, encoding="utf-8", newline="") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 3 and len(cols[2]) == 64, f"line {i}: a row is input, canon, sha256: {line!r}"
            yield i, *cols


def test_the_course_writes_every_vector_of_the_table_in_its_canon_and_its_hash():
    from w2cplatform.canonical import parse_json
    from w2cplatform.trust.jcs import jcs
    rows = list(_rows())
    assert len(rows) >= 17, f"the table holds {len(rows)} vectors"
    for i, given, canon, digest in rows:
        got = jcs(parse_json(given.encode()))
        assert got == canon.encode(), f"line {i}: {given!r} → {got.decode()!r}, the table says {canon!r}"
        assert hashlib.sha256(got).hexdigest() == digest, f"line {i}: the sha256 of {canon!r} is not the table's"
        assert jcs(parse_json(got)) == got, f"line {i}: the canon of the canon is another text"


def test_the_table_is_the_products_byte_for_byte_when_the_product_keeps_one():
    """When the product's committed `main` keeps `testdata/canonical_json.tsv`, the course's is a copy of it."""
    theirs = product_file("testdata/canonical_json.tsv")
    if theirs is None:
        print("  the product's main keeps no testdata/canonical_json.tsv: the course's copy stands")
        return
    with open(TABLE, "rb") as b:
        assert theirs == b.read(), f"{TABLE} is not the product's testdata/canonical_json.tsv byte for byte"


def test_names_sort_by_utf16_code_units_not_by_code_points():
    """`sort_keys` puts U+FB33 before U+1F600 (code points); RFC 8785 the other way (the surrogate D83D < FB33)."""
    from w2cplatform.trust.jcs import jcs
    doc = {"דּ": 2, "\U0001f600": 1, "a": 0}
    assert jcs(doc) == '{"a":0,"\U0001f600":1,"דּ":2}'.encode()
    assert sorted(doc) != sorted(doc, key=lambda k: k.encode("utf-16-be"))


def test_numbers_are_es6s_shortest_form():
    from w2cplatform.trust.jcs import jcs
    for v, want in ((1.0, "1"), (-0.0, "0"), (0, "0"), (1e21, "1e+21"), (1e20, "100000000000000000000"),
                    (1e-6, "0.000001"), (1e-7, "1e-7"), (-1.5e-10, "-1.5e-10"), (0.1, "0.1"), (123.456, "123.456"),
                    (2 ** 53 + 1, "9007199254740992"), (10 ** 30, "1e+30"), (5e-324, "5e-324"),
                    (1.7976931348623157e308, "1.7976931348623157e+308"), (-12345.678e3, "-12345678")):
        assert jcs(v) == want.encode(), f"{v!r} → {jcs(v)!r}, ES6 says {want}"


def test_what_has_no_form_is_refused():
    """NaN, the infinities, an integer past a double, a lone surrogate: no form, nothing signs them. A name that is not
    a string, a value that is not JSON: no form either."""
    from w2cplatform.trust.jcs import NotCanonical, jcs
    for bad in (math.nan, math.inf, -math.inf, 10 ** 400, {"a": [math.nan]}, "\ud800", {"\udfff": 1}):
        try:
            jcs(bad)
        except NotCanonical:
            continue
        raise AssertionError(f"{bad!r:.40} has a canon")
    for bad in ({1: "a"}, {None: 1}, {"a": {1, 2}}, b"bytes"):
        try:
            jcs(bad)
        except TypeError:
            continue
        raise AssertionError(f"{bad!r:.40} has a canon")


def test_a_signed_document_covers_its_rfc8785_form_and_verifies_with_html_characters_floats_and_names_past_the_bmp():
    """`documents.sign` signs `jcs` of the document without `kid` and `sig`; `verify` takes it — `A&B <gate>`, `1.0`,
    a name outside the BMP, as the product's `trust.canonical` writes them — and refuses a document a byte changed."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from w2cplatform.trust.documents import NotTaken, sign, verify
    from w2cplatform.trust.jcs import jcs
    from w2cplatform.trust.tokens import TokenIssuer, _unb64
    issuer = TokenIssuer("acme")
    body = {"label": "A&B <gate>", "at": 1.0, "rev": 1, "\U0001f600": "x", "דּ": "y", "big": 1e21}
    doc = sign(body, issuer)
    covered = jcs(body)
    assert covered == ('{"at":1,"big":1e+21,"label":"A&B <gate>","rev":1,"\U0001f600":"x","דּ":"y"}').encode()
    Ed25519PublicKey.from_public_bytes(issuer.public_bytes).verify(_unb64(doc["sig"]), covered)
    assert verify(doc, issuer.keyset(), now=0) is doc
    assert verify({**doc, "at": 1}, issuer.keyset(), now=0)            # the same value, the same canon
    try:
        verify({**doc, "label": "A&B <gate> "}, issuer.keyset(), now=0)
    except NotTaken:
        pass
    else:
        raise AssertionError("a changed document verified")
