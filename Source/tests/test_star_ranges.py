"""C3b range credentials and delayed responses obey the current upstream scope."""
from tests.test_upstream_runtime import fixture, topology, upstream
from vms.ingest import Ingest, RangeFailed, Refused
from w2cplatform.trust.tokens import TokenIssuer


def refuses(call, error):
    try:
        call()
    except error:
        return
    raise AssertionError("an unauthorized or withdrawn range was accepted")


def test_remote_range_checks_kind_audience_and_reference_before_requesting_the_camera():
    issuer = TokenIssuer("domain")
    ing = Ingest("centre", [], issuer.keyset, wall=lambda: 1000)
    asked = []
    ing.fetch_range = lambda *args: asked.append(args) or [b"frame"]
    def token(**over):
        return issuer.issue("relay", 60, now=1000, **{"kind": "upstream", "aud": ["centre"], "ref": "serial", **over})
    for change in ({"kind": "stream"}, {"aud": ["other"]}, {"ref": "different"}):
        refuses(lambda c=change: ing.fetch(token(**c), "serial", 10, 11, recording="2-card"), Refused)
    assert not asked
    assert ing.fetch(token(), "serial", 10, 11, .2, "2-card") == [b"frame"]
    assert asked == [("serial", 10, 11, .2, "2-card")]


def test_range_reply_from_a_replaced_centre_is_not_applied():
    box, fwd, _, centre, _ = fixture(star=True)
    def delayed(*args):
        topology(box, rev=2, centre="new-centre", star=["relay"])
        upstream(box, member="new-centre", urls=("http://new-centre",))
        return [b"old-centre-frame"]
    centre.fetch = delayed
    refuses(lambda: fwd.fetch_range("serial", 10, 11, .2, "2-card"), RangeFailed)


def test_refused_range_forgets_the_token_and_a_role_outage_opens_no_new_request():
    _, fwd, door, centre, _ = fixture(star=True)
    def denied(*args):
        raise Refused("retired upstream credential")
    centre.fetch = denied
    refuses(lambda: fwd.fetch_range("serial", 10, 11), RangeFailed)
    assert not fwd.tokens.cached and len(door.calls) == 1
    door.failure = True
    refuses(lambda: fwd.fetch_range("serial", 10, 11), RangeFailed)
    assert len(door.calls) == 2 and not fwd.tokens.cached


def test_ordinary_recorder_fetches_locally_and_does_not_request_a_centre_token():
    _, fwd, door, _, _ = fixture()
    asked = []
    fwd.local.fetch_range = lambda *args: asked.append(args) or [b"local-frame"]
    assert fwd.fetch_range("serial", 10, 11, .2, "2-card") == [b"local-frame"]
    assert asked == [("serial", 10, 11, .2, "2-card")] and not door.calls
