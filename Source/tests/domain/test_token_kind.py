"""Feedback CE — a token says what it is for, and every door takes its own.

One key signs a person's token, a camera's stream token, an ask between cameras and a relay's token to the
centre. Read by signature alone, a stream token off a camera's flash passed a console's gate as the user
`cam-SN5001` — and a user of that name, granted anything, would have been impersonated."""
import time

from w2cplatform.cluster.variables import FakeVariables

from domain.access import ClusterAccess
from domain.agent import GRANTS_PATH, KEYS_PATH
from domain.grants import ClusterAuthoriser, ClusterGrants, Grant, grants_to_items
from domain.ingest import Ingest, Refused, audience
from domain.tokens import TokenIssuer, WrongKind, kind_of, verify
from w2cplatform.access import Denied

NOW = 1_000_000.0


def _tokens():
    t = TokenIssuer("acme")
    return t, {
        "person": t.issue("alice", 900, now=NOW, kind="person"),
        "stream": t.issue("cam-SN5001", 900, now=NOW, aud=audience("south"), ref="SN5001", kind="stream"),
        "ask": t.issue("cam-SN5002", 900, now=NOW, aud=audience("south"), ask="SN5001", by="SN5002", acts=[], kind="ask"),
        "relay": t.issue("south", 900, now=NOW, aud=audience("north"), ref="SN5001", kind="stream"),
    }


def test_every_token_says_what_it_is_for_and_old_ones_say_it_by_their_shape():
    t, tok = _tokens()
    ks = t.keyset()
    for kind in ("person", "stream", "ask"):
        assert kind_of(verify(tok[kind], ks, now=NOW)) == kind
        others = [k for k in ("person", "stream", "ask") if k != kind]
        for other in others:
            try:
                verify(tok[kind], ks, now=NOW, kind=other)
                raise AssertionError(f"a {kind} token passed as {other}")
            except WrongKind:
                pass
    legacy = {"person": t.issue("bob", 900, now=NOW), "stream": t.issue("cam-1", 900, now=NOW, aud="x", ref="1"),
              "ask": t.issue("cam-2", 900, now=NOW, aud="x", ask="1")}
    assert {k: kind_of(verify(v, ks, now=NOW)) for k, v in legacy.items()} == {"person": "person", "stream": "stream", "ask": "ask"}


def test_a_camera_or_relay_token_is_not_a_person_at_the_consoles_gate_even_with_grants_under_its_name():
    t, tok = _tokens()
    v = FakeVariables()
    v.put(KEYS_PATH, t.keyset().to_items())
    v.put(GRANTS_PATH, grants_to_items([Grant(s, "admin", None, NOW + 86400) for s in ("alice", "cam-SN5001", "south", "cam-SN5002")]))
    access = ClusterAccess(v, wall=lambda: NOW)
    assert access.who(tok["person"])["sub"] == "alice"
    for k in ("stream", "ask", "relay"):
        try:
            access.who(tok[k])
            raise AssertionError(f"a {k} token passed the console's gate")
        except Denied as e:
            assert e.status == 401 and "person" in e.why
    grants = ClusterGrants("south", now=lambda: NOW)
    grants.grant("cam-SN5001", "view", None, NOW + 86400)
    gateway = ClusterAuthoriser(grants, t.keyset(), now=lambda: NOW)
    try:
        gateway.subject(tok["stream"])
        raise AssertionError("the live gateway took a camera for a viewer")
    except WrongKind:
        pass


def test_an_ingest_takes_stream_tokens_for_streams_and_ask_tokens_for_asks():
    t, tok = _tokens()
    ing = Ingest("south", ["srt://srv-1.south:9000"], keys=t.keyset, wall=lambda: NOW)
    assert ing.poll(tok["stream"], "SN5001")["version"] >= 0
    for k in ("person", "ask"):
        try:
            ing.poll(tok[k], "SN5001")
            raise AssertionError(f"a {k} token polled as a camera")
        except Refused as e:
            assert "stream token refused" in str(e)
    try:
        ing.ask(tok["stream"], "SN5001", {"preset": 3}, NOW + 30)
        raise AssertionError("a stream token asked")
    except Refused as e:
        assert "ask token refused" in str(e)
