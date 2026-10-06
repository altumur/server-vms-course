"""A recording moved to another volume, and the footage it left on the first (the architect's decision after step 7).

The console carries no bytes: no `/timeline`, no `/whep` of its own. The scale is built from holders' doors only — the
recording's own (`GET /rec/where/<recording>`), and, for what it left on a volume another recorder holds now, that
volume's: `GET /rec/where/volumes/<volume>?unit=rec/<recording>` → the recorder holding the volume and its door, with a
token for THAT recorder and that recording. A volume nobody holds is said as `X-Unreachable: <volume>@<server>`, and
the page names it. `_timeline` below is what the page does (`loadTimeline` in `vms/vms.shell.html`, the core it shares with
the product's page: `test_shell_core.py`)."""
import json
import urllib.error
import urllib.parse
import urllib.request

from vms import volumes
from vms.config import REC_SPEC, SPEC
from vms.console import make_console
from vms.controller import VmsController
from w2cplatform.door import DoorKeeper
from w2cplatform.spec import SpecController
from tests.conftest import door_keys
from tests.vmsconftest import Box, door, footage, store


def _get(url, token=None):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


def _timeline(base, rec):
    """The page's scale of one recording: its own door's spans, then each volume's holder's (`/rec/volumes`, asked by
    `/rec/where/volumes/<v>?unit=rec/<rec>`), one holder once, merged without doubling; the notes it would show."""
    spans, notes, asked = [], set(), set()

    def ask(where):
        st, w, headers = _get(base + where)
        if headers.get("X-Unreachable"):
            notes.add(headers["X-Unreachable"])
        d = w.get("door")
        if not d or w.get("worker") in asked:
            return
        asked.add(w["worker"])
        st, got, headers = _get(f"{d['url']}/timeline/{rec}?from=0&to=1e12", d["token"])
        assert st == 200, (st, got)
        spans.extend(got)
    ask(f"/rec/where/{rec}")
    for v in _get(base + "/rec/volumes")[1]["volumes"]:
        ask(f"/rec/where/volumes/{urllib.parse.quote(v['name'])}?unit=rec/{rec}")
    seen, merged = set(), []
    for s in spans:
        k = (s["start_ms"], s["end_ms"], s["epoch"], s.get("source", ""))
        if k not in seen:
            seen.add(k); merged.append(s)
    return merged, notes


def _site(box):
    """Three local volumes — `old` on srv-1, `new` on srv-2, `gone` on srv-3 — recording 1 written into `old` under
    epoch 1 and now into `new` under epoch 2 (placed on `r-new`), and nobody holding `gone`; a console over the VMS
    and rec, with the cluster's door key (`door/keys`), each recorder's door checking the tokens it is given."""
    t = box.wall()
    for name, server in (("old", "srv-1"), ("new", "srv-2"), ("gone", "srv-3")):
        volumes.write(box.vars, {"name": name, "kind": "local", "url": f"/data/{name}", "server": server,
                                 "quota_bytes": 64 << 20})
    box.vars.put("rec/recordings/1", {"name": "1", "cam": "1"})
    old_st, new_st = store("old"), store("new")
    footage(old_st, "1", 1, t - 3600, t - 3000)
    footage(new_st, "1", 2, t - 600, t - 60)
    with door_keys(box.vars):
        ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
        rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
        m = make_console(ctl, box.resource_root, box.wall, mounts={"rec": rec})
    old = door(box, old_st, "r-old", "srv-1", keeper=DoorKeeper("r-old", box.wall, box.vars))
    new = door(box, new_st, "r-new", "srv-2", status=[{"id": "1", "phase": "running", "epoch": 2}],
               keeper=DoorKeeper("r-new", box.wall, box.vars))
    box.vars.put("rec/placement/1", {"worker": "r-new", "reason": "test", "at": t, "rev": 1})
    srv = m.serve("127.0.0.1", 0)
    return srv, f"http://127.0.0.1:{srv.server_address[1]}", old, new


def test_a_recording_moved_to_another_volume_shows_what_it_left_on_the_first_at_that_volumes_holders_door():
    """`GET /rec/where/volumes/old?unit=rec/1` names the recorder holding `old` and hands out its door with a token for
    it and recording 1; the token the recording's own place gives (`r-new`'s) does not open `r-old`'s door, the place's
    does, and it says the minutes of epoch 1. The scale is both volumes' minutes, each once; `gone` is named as
    `gone@srv-3`."""
    box = Box()
    srv, base, old, new = _site(box)
    try:
        st, w, _ = _get(base + "/rec/where/1")
        assert st == 200 and w["worker"] == "r-new" and w["door"]["url"] == new.url, w
        st, p, _ = _get(base + "/rec/where/volumes/old?unit=rec/1")
        assert st == 200 and p["worker"] == "r-old" and p["server"] == "srv-1" and p["door"]["url"] == old.url, p
        assert p["door"]["routes"] == ["timeline", "segment", "keeps"]   # …and a keep's seal (`keeps`)
        st, body, _ = _get(f"{old.url}/timeline/1", w["door"]["token"])
        assert st == 401 and body["reason"] == "holder", body                         # not the recording's own token
        st, spans, _ = _get(f"{old.url}/timeline/1?from=0&to=1e12", p["door"]["token"])
        assert st == 200 and {s["epoch"] for s in spans} >= {1}, spans                # the minutes `old` holds
        st, body, _ = _get(f"{old.url}/timeline/2", p["door"]["token"])
        assert st == 401 and body["reason"] == "unit"                                 # one recording's token

        merged, notes = _timeline(base, "1")
        assert {s["epoch"] for s in merged} == {1, 2}, merged                         # both volumes' minutes
        keys = [(s["start_ms"], s["end_ms"], s["epoch"]) for s in merged]
        assert len(keys) == len(set(keys))                                            # each once
        assert notes == {"gone@srv-3"}, notes
    finally:
        srv.shutdown(); old.shutdown(); new.shutdown()


def test_a_volume_whose_recorder_went_silent_is_named_and_its_minutes_are_missing_not_drawn():
    """`r-old` goes silent: nobody holds `old` now. Its place answers 404, `door: null`, `X-Unreachable: old@srv-1`, and
    the scale is `new`'s minutes with `old@srv-1` named beside `gone@srv-3` — not a hole drawn as if nothing were there."""
    box = Box()
    srv, base, old, new = _site(box)
    try:
        assert _get(base + "/rec/where/volumes/old?unit=rec/1")[0] == 200            # the console's first look at r-old
        box.wall.advance(60); box.clock.advance(60)
        new.announce()                                                                # only r-new still beats
        st, p, headers = _get(base + "/rec/where/volumes/old?unit=rec/1")
        assert st == 404 and p["door"] is None and headers.get("X-Unreachable") == "old@srv-1", (st, p, headers)
        merged, notes = _timeline(base, "1")
        assert {s["epoch"] for s in merged} == {2}, merged
        assert notes == {"old@srv-1", "gone@srv-3"}, notes
    finally:
        srv.shutdown(); old.shutdown(); new.shutdown()


def test_the_console_has_no_byte_routes_of_its_own():
    """No console `/timeline`, `/segment`, `/whep` — at the root or under a mount: the scale is built from holders' doors
    and a stream is opened at its gateway's door (`tests/test_lesson8_live.py`)."""
    box = Box()
    srv, base, old, new = _site(box)
    try:
        for path in ("/timeline/1", "/rec/timeline/1", "/segment/1/e1/0-1000.mp4", "/rec/segment/1/e1/0-1000.mp4",
                     "/whep/1", "/live/whep/1"):
            assert _get(base + path)[0] == 404, path
    finally:
        srv.shutdown(); old.shutdown(); new.shutdown()
