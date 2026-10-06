"""Every request ends with its outcome in its mark (ADR-0054), on testsub and testsub2 — `<sub>/commands/<id>`, where
whoever asked reads how it went, byte for byte with the product (`requestserver.go`: `endMark`, `notKnown`,
`CompleteMark`, `MarkError`; `requests.go`: `endedMark`):

    outcome     performed | refused | unknown | expired
    error       the reason of `refused` and `unknown`, at most 200 characters (cut, never refused)
    late        true on an answer that came after the request was answered "did not answer"
    ended_by    `reaper` on the console's `expired` for a request nobody began, written create-only, with `ended_at`

Who writes what and whose word wins: the holder writes a refusal before any call and `expired` create-only, its answer
over whatever stands (its word wins), `unknown` into another instance's mark with no outcome (its beginner kept);
the reaper writes `expired` create-only and never over a mark that stands. BEGUN IS NOT EXPIRED. A closer (the reaper,
a holder's `unknown`) writes BY THE INDEX IT READ: a conflict is read again — an outcome there now stops it, none
writes again, eight times at most.
"""
import json
import logging
import threading
import time

from tests.conftest import Box, testsub, testsub2
from tests.test_holder_requests import Holder, _ask, _holder, _look
from w2cplatform import requests
from w2cplatform.canonical import canonical_json
from w2cplatform.objects import FsObjectStore, bytes_index
from w2cplatform.requests import CLOSE_ATTEMPTS, MARK_ERROR, MARK_TEXT, complete_mark, mark_error, mark_text
from w2cplatform.spec import SpecController


def _mark(box, spec, rid) -> dict:
    raw = box.objects.get(spec.sub.command_key(rid))
    assert raw is not None, rid
    assert raw.decode() == canonical_json(json.loads(raw)), raw          # the one text of a row
    return json.loads(raw)


def _other(box, spec, rid, unit, instance="box-b:1:bbbbbb", slot="w-9", at=None) -> None:
    """A mark another instance left before its call, and no answer after it."""
    body = {"instance": instance, "slot": slot, "unit": unit, "at": box.wall() - 5 if at is None else at}
    box.objects.put(spec.sub.command_key(rid), canonical_json(body).encode())


def test_each_of_the_four_outcomes_ends_in_the_mark():
    """performed, refused (by the target, and before any call), expired (nobody began it), unknown (another instance
    began it): each is in the request's mark, with the reason beside a refusal and `unknown`."""
    box, spec = Box(), testsub()
    w = _holder(box, spec, ["c1", "c2", "c3", "c4", "c5"])
    _ask(box, spec, "ok", "c1", 2, action="add")
    _ask(box, spec, "no", "c2", -1)                                                   # the target refuses
    box.vars.put(spec.sub.request_key("far"), {"unit": "c3", "add": "1", "valid_until": str(box.wall() + 3600)})
    box.vars.put(spec.sub.request_key("old"), {"unit": "c4", "add": "1", "valid_until": str(box.wall() - 1)})
    _ask(box, spec, "theirs", "c5", 1)
    _other(box, spec, "theirs", "c5")
    _look(w, 5)
    ok = _mark(box, spec, "ok")
    assert (ok["outcome"], ok["instance"], ok["slot"], ok["unit"], ok["action"]) == ("performed", w.instance, w.name,
                                                                                    "c1", "add"), ok
    assert "error" not in ok and "late" not in ok and "ended_by" not in ok
    no = _mark(box, spec, "no")
    assert (no["outcome"], no["error"], no["instance"]) == ("refused", "a tally only grows", w.instance), no
    far = _mark(box, spec, "far")                                                     # refused BEFORE any call: create-only
    assert far["outcome"] == "refused" and far["error"].startswith("`valid_until` is more than") and far["slot"] == w.name
    old = _mark(box, spec, "old")
    assert old["outcome"] == "expired" and "error" not in old and "ended_by" not in old and old["instance"] == w.instance
    theirs = _mark(box, spec, "theirs")
    assert (theirs["outcome"], theirs["instance"], theirs["slot"]) == ("unknown", "box-b:1:bbbbbb", "w-9"), theirs
    assert theirs["error"].startswith("unknown: an earlier instance (box-b:1:bbbbbb) began it") and "ended_at" in theirs
    assert w.commands == {"performed": 1, "refused": 2, "expired": 1, "unknown": 1}
    assert [c[1] for c in w.calls] == ["c1"]                                          # only `ok` reached its target


def test_a_reason_is_cut_at_two_hundred_characters_in_the_mark_and_said_whole_in_the_answer():
    """A mark is read by every holder of the unit and by whoever asked: a reason is a sentence, not a payload — cut at
    `MARK_ERROR` characters with `…` (the product's `MarkError`, by characters, not bytes), never refused. The answer
    and the event keep it whole."""
    assert MARK_ERROR == 200 and mark_error("x" * 200) == "x" * 200
    assert mark_error("я" * 201) == "я" * 200 + "…" and mark_error("") == ""
    box, spec = Box(), testsub()
    long = "the target says: " + "no " * 300

    class Talkative(Holder):
        def perform(self, target, row, it):
            raise RuntimeError(long)

    w = _holder(box, spec, ["c1"], cls=Talkative)
    _ask(box, spec, "r1", "c1", 1)
    [answer] = _look(w, 1)
    assert answer["error"] == long
    m = _mark(box, spec, "r1")
    assert m["outcome"] == "refused" and m["error"] == long[:200] + "…" and len(m["error"]) == 201


def test_a_begun_request_past_its_deadline_is_unknown_not_expired_and_its_beginner_is_kept():
    """BEGUN IS NOT EXPIRED: another instance marked the request and never answered; past the deadline the holder now
    says `unknown` — that instance may have acted on the unit — completing that mark: `instance` and `slot` stay the
    beginner's, `outcome`, `error` and `ended_at` are added. Nothing is called."""
    box, spec = Box(), testsub2()
    box.vars.put(spec.sub.config("tallies", "t1"), {"name": "t1", "of": "c1"})
    w = Holder(box, spec)
    w.server = "srv-1"
    w.claim_slot("t-1")
    from w2cplatform.contract import Controller
    Controller(spec.sub, box.vars, box.objects, wall=box.wall).assign("t-1", ["t1"])
    w.assignment()
    w.open = {"t1": {"id": "t1", "of": "c1"}}
    box.vars.put(spec.sub.request_key("r1"), {"unit": "t1", "add": "1", "valid_until": str(box.wall() - 10)})
    _other(box, spec, "r1", "t1", at=box.wall() - 40)
    done = w.requests()
    assert [d.get("error", "")[:8] for d in done] == ["unknown:"] and not any(d.get("expired") for d in done), done
    m = _mark(box, spec, "r1")
    assert (m["outcome"], m["instance"], m["slot"], m["at"]) == ("unknown", "box-b:1:bbbbbb", "w-9", box.wall() - 40), m
    assert m["ended_at"] == box.wall() and m["error"].startswith("unknown: an earlier instance (box-b:1:bbbbbb)")
    assert w.commands["unknown"] == 1 and w.commands["expired"] == 0 and w.calls == []


def test_the_reaper_writes_expired_create_only_and_never_over_a_mark_that_stands():
    """A request nobody held past its deadline and `REAP_AFTER`: the reaper ends it and says so in its mark —
    `outcome: expired`, `ended_by: reaper`, `ended_at`, the unit and the action — create-only. A mark that stands is
    never written over: an answer stays the holder's; a begun mark of a holder still there keeps its row."""
    box, spec = Box(), testsub()
    con = SpecController(spec, box.vars, box.objects, wall=box.wall)
    late = box.wall() - requests.REAP_AFTER - 5
    for rid in ("nobody", "answered", "raced"):
        box.vars.put(spec.sub.request_key(rid), {"unit": "c1", "add": "1", "action": "add", "valid_until": str(late),
                                                 "at": str(late - 10)})
    answer = canonical_json({"instance": "a:1:x", "outcome": "performed", "slot": "w-1", "unit": "c1"}).encode()
    box.objects.put(spec.sub.command_key("answered"), answer)
    requests.clear_requests(con)
    assert box.vars.list(spec.sub.requests_prefix()) == []
    raw = box.objects.get(spec.sub.command_key("nobody")).decode()
    assert raw == canonical_json({"action": "add", "at": box.wall(), "ended_at": box.wall(), "ended_by": "reaper",
                                  "outcome": "expired", "unit": "c1"}), raw
    assert box.objects.get(spec.sub.command_key("answered")) == answer              # the holder's answer stands
    # create-only: the end is not written over a mark made between the reaper's read and its write — a holder began it
    began = canonical_json({"instance": "a:1:x", "slot": "w-1", "unit": "c1", "at": late}).encode()
    box.objects.put(spec.sub.command_key("raced"), began)
    requests._ended_mark(con, "raced", {"unit": "c1"}, "expired", box.wall())
    assert box.objects.get(spec.sub.command_key("raced")) == began


def test_the_reaper_completes_a_gone_holders_mark_unknown_keeping_its_beginner():
    """A mark with no outcome whose holder no longer holds the name it marked under: the reaper completes it `unknown`
    by the index it read — the beginner's `instance` and `slot` stay, no `ended_by` (the reaper is not who began it)."""
    from w2cplatform.contract import Slot
    box, spec = Box(), testsub()
    con = SpecController(spec, box.vars, box.objects, wall=box.wall)
    late = box.wall() - requests.REAP_AFTER - 5
    box.vars.put(spec.sub.request_key("r1"), {"unit": "c1", "add": "1", "valid_until": str(late)})
    box.vars.put(spec.sub.slot_key("w-1"), Slot("w-1", "b:2:other", box.wall() + 45, False, 2).to_items())   # it went
    _other(box, spec, "r1", "c1", instance="a:1:gone", slot="w-1", at=late - 1)
    was = requests.unknown.get(spec.name, 0)
    requests.clear_requests(con)
    m = _mark(box, spec, "r1")
    assert (m["outcome"], m["instance"], m["slot"], m["ended_at"]) == ("unknown", "a:1:gone", "w-1", box.wall()), m
    assert m["error"] == "its holder began it and is gone without saying how it went" and "ended_by" not in m
    assert requests.unknown.get(spec.name, 0) == was + 1


def test_the_holders_answer_is_written_over_the_reapers_and_another_instances_word():
    """The holder's answer is the truth of what was done to the unit: written over another's `unknown` when its call
    comes back, and — late, `late: true` — over the reaper's `expired` too. Its own instance and slot, not the closer's;
    no `ended_by` and no closer's `error`: the closer's words go with its word. One form of a mark: `at` when this instance
    made it, `ended_at` when its outcome was written (ADR 0054)."""
    box, spec = Box(), testsub()
    gate = threading.Event()
    w = _holder(box, spec, ["c1"], gate=gate)
    _ask(box, spec, "r1", "c1", 4)
    assert w.requests() == [] and len(w._performing) == 1                             # begun: the call hangs
    assert complete_mark(box.objects, spec.sub.command_key("r1"), "unknown", "seen from elsewhere", box.wall())
    assert _mark(box, spec, "r1")["outcome"] == "unknown"
    gate.set()
    _look(w, 1)
    m = _mark(box, spec, "r1")
    assert (m["outcome"], m["instance"], m["slot"]) == ("performed", w.instance, w.name), m
    assert not {"error", "ended_by", "late"} & set(m) and m["ended_at"] >= m["at"], m
    # late: answered "did not answer", the reaper's `expired` there meanwhile, the call back after all
    gate.clear()
    _ask(box, spec, "r2", "c1", 5)
    assert w.requests() == []
    box.clock.advance(w.PERFORM_TIMEOUT)
    assert [d.get("error") for d in w.requests()] == ["the target did not answer"]
    box.objects.put(spec.sub.command_key("r2"), canonical_json({"unit": "c1", "outcome": "expired", "at": box.wall(),
                                                                "ended_by": "reaper", "ended_at": box.wall()}).encode())
    gate.set()
    for _ in range(100):
        if not w._performing:
            break
        w.requests()
        time.sleep(0.02)
    m = _mark(box, spec, "r2")
    assert (m["outcome"], m["late"], m["instance"]) == ("performed", True, w.instance) and "ended_by" not in m, m


class Racing:
    """The object store, and another writer of one mark between a closer's read and its write: `writes` is what the
    other writes before each `put_at` (None: nothing), so the closer's index is stale exactly then."""

    def __init__(self, real, key, writes):
        self.real, self.key, self.writes = real, key, list(writes)
        self.read_at = self.wrote_at = 0

    def get_at(self, key):
        self.read_at += 1
        return self.real.get_at(key)

    def put_at(self, key, data, index):
        self.wrote_at += 1
        if self.writes:
            other = self.writes.pop(0)
            if other is not None:
                self.real.put(self.key, canonical_json(other).encode())
        return self.real.put_at(key, data, index)

    def __getattr__(self, name):
        return getattr(self.real, name)


def test_a_closer_whose_index_went_stale_reads_again_stops_on_an_outcome_writes_again_without_and_gives_up_after_eight():
    """A closer writes by the index it read (`put_at`); a conflict means somebody wrote the mark meanwhile. Read again:
    the beginner's answer there now — stop, it stands; still no outcome — write again by the new index; written over
    every time — give up after `CLOSE_ATTEMPTS` (8), the mark as the last writer left it."""
    box, spec = Box(), testsub()
    key = spec.sub.command_key("r1")
    begun = {"instance": "a:1:x", "slot": "w-1", "unit": "c1", "at": 1.0}
    answered = {**begun, "outcome": "performed", "action": "", "at": 2.0}

    box.objects.put(key, canonical_json(begun).encode())
    store = Racing(box.objects, key, [answered])                       # the beginner answers between read and write
    assert not complete_mark(store, key, "unknown", "why", 3.0)
    assert json.loads(box.objects.get(key)) == answered and (store.read_at, store.wrote_at) == (2, 1)

    box.objects.put(key, canonical_json(begun).encode())
    store = Racing(box.objects, key, [{**begun, "at": 1.5}])             # rewritten, still no outcome: write again
    assert complete_mark(store, key, "unknown", "why", 3.0)
    m = json.loads(box.objects.get(key))
    assert (m["outcome"], m["at"], m["instance"], store.wrote_at) == ("unknown", 1.5, "a:1:x", 2), m

    box.objects.put(key, canonical_json(begun).encode())
    store = Racing(box.objects, key, [{**begun, "at": 10.0 + i} for i in range(CLOSE_ATTEMPTS)])
    assert CLOSE_ATTEMPTS == 8 and not complete_mark(store, key, "unknown", "why", 3.0)
    assert store.wrote_at == 8 and json.loads(box.objects.get(key)) == {**begun, "at": 17.0}


def test_both_object_stores_write_by_the_index_read():
    """The file store: the index is a digest of the bytes, compared and written under the directory's lock, which every
    write of the store takes; `""` is no object at all. The rows (`VariablesObjectStore`, the cluster's create-only keys):
    the row's own index, 0 for none. Each writes only while the object stands where it was read."""
    from w2cplatform.cluster.objectstore import VariablesObjectStore
    from w2cplatform.cluster.variables import FakeVariables
    for store in (FsObjectStore(Box().root + "/o"), VariablesObjectStore(FakeVariables())):
        data, index = store.get_at("testsub/commands/r1")
        assert data is None
        assert store.put_at("testsub/commands/r1", b"one", index)                      # none read, none there: made
        assert not store.put_at("testsub/commands/r1", b"two", index)                  # made since: stale
        data, index = store.get_at("testsub/commands/r1")
        assert data == b"one"
        store.put("testsub/commands/r1", b"other")                                       # another writer
        assert not store.put_at("testsub/commands/r1", b"two", index)
        data, index = store.get_at("testsub/commands/r1")
        assert store.put_at("testsub/commands/r1", b"two", index) and store.get("testsub/commands/r1") == b"two"
    assert bytes_index(None) == "" and bytes_index(b"two") != bytes_index(b"one")
    files = FsObjectStore(Box().root + "/o")
    files.put("testsub/commands/r1", b"x")
    assert files.list("testsub/") == ["testsub/commands/r1"]                            # the lock is no object


def test_every_mark_with_an_outcome_says_when_it_was_made_and_when_it_ended():
    """ADR 0054, one form of a mark: `at` is when the mark was made, `ended_at` when its outcome was written — the holder's
    answer keeps the `at` it began at; a mark made and ended at once (a refusal before the call) has the two equal."""
    box, spec = Box(), testsub()
    gate = threading.Event()
    w = _holder(box, spec, ["c1"], gate=gate)
    _ask(box, spec, "r1", "c1", 4)
    assert w.requests() == []
    began = _mark(box, spec, "r1")["at"]
    box.wall.advance(3); box.clock.advance(3)
    gate.set()
    _look(w, 1)
    m = _mark(box, spec, "r1")
    assert m["outcome"] == "performed" and m["at"] == began and m["ended_at"] == began + 3, m


# A garbled or hostile mark another wrote: an `instance` of ten thousand characters, a newline, an escape, a NUL, a
# carriage return and U+2028 in it — and, as a reader says it, one line of `MARK_TEXT` characters and `…`.
HOSTILE = "box-b\n\x1b[31m" + "x" * 9980 + "\r\n\x00 \t" + "y" * 5
SAID = "box-b  [31m" + "x" * 69 + "…"


def _one_line_and_short(text: str, clipped: str) -> None:
    assert clipped in text, (clipped, text[:200])
    assert text.isprintable() and len(text) < 400, repr(text[:200])                  # no control character, no flood


class _Said(logging.Handler):
    """Every line the platform logs while it stands, as its reader would see it."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines: list[str] = []
        self.logger = logging.getLogger("w2cplatform")

    def emit(self, record):
        self.lines.append(record.getMessage())

    def __enter__(self):
        self.level = self.logger.level
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self)
        return self

    def __exit__(self, *exc):
        self.logger.removeHandler(self)
        self.logger.setLevel(self.level)


def test_a_marks_words_are_said_on_one_line_cut_at_eighty_characters():
    """The product's `markText` (80 and `…`), and one line: what is not printable is a space. By characters, after the
    word is a field's text (a string as it is, the rest its JSON); a mark with no such word says ""."""
    assert MARK_TEXT == 80 and mark_text({"instance": HOSTILE}, "instance") == SAID
    assert mark_text({"slot": "w-1"}, "slot") == "w-1" and mark_text({"slot": None}, "slot") == ""
    assert mark_text({}, "slot") == "" and mark_text(None, "slot") == "" and mark_text("garbled", "slot") == ""
    assert mark_text({"o": "a" * 80}, "o") == "a" * 80 and mark_text({"o": "я" * 81}, "o") == "я" * 80 + "…"
    assert mark_text({"o": True}, "o") == "true" and mark_text({"o": 5.0}, "o") == "5"
    assert mark_text({"o": {"b": 1, "a": "\n"}}, "o") == '{"a":"\\n","b":1}'
    assert mark_text({"o": "a b\u0085c\td"}, "o") == "a b c d"
    assert mark_text({"o": float("nan")}, "o") == "nan"


def test_a_foreign_marks_words_are_clipped_where_they_are_said_and_the_mark_is_kept_whole():
    """A mark another instance (or the reaper) wrote is another writer's data. Wherever a reader SAYS one of its words —
    `unknown: an earlier instance (…) began it` in the answer, the `command.failed` event and the log line; the
    `outcome` and `slot` of an answer said again; the reaper's line of an answer that never reached a heartbeat — it says
    it on one line and at most 80 characters (`mark_text`, the product's `markText`). The mark itself is not rewritten
    by the reader: its `instance` stays as its writer wrote it."""
    box, spec = Box(), testsub()
    w = _holder(box, spec, ["c1", "c2", "c3"])
    events: list[tuple] = []
    real = w.observe

    def observe(unit, kind, **fields):
        events.append((kind, dict(fields)))
        return real(unit, kind, **fields)

    w.observe = observe
    _ask(box, spec, "theirs", "c1", 1)                                                # begun elsewhere, in time
    _other(box, spec, "theirs", "c1", instance=HOSTILE, slot=HOSTILE)
    box.vars.put(spec.sub.request_key("late"), {"unit": "c2", "add": "1", "valid_until": str(box.wall() - 1)})
    _other(box, spec, "late", "c2", instance=HOSTILE)                                 # …and past its deadline
    _ask(box, spec, "answered", "c3", 1)
    box.objects.put(spec.sub.command_key("answered"), canonical_json(
        {"instance": HOSTILE, "slot": HOSTILE, "unit": "c3", "outcome": HOSTILE, "at": box.wall()}).encode())
    with _Said() as said:
        done = _look(w, 3)
    by = {d["request"]: d for d in done}
    for rid in ("theirs", "late"):
        _one_line_and_short(by[rid]["error"], f"an earlier instance ({SAID}) began it")
        m = _mark(box, spec, rid)
        assert m["instance"] == HOSTILE and m["outcome"] == "unknown", rid              # kept whole: only what is said
        assert m["error"] == mark_error(by[rid]["error"]) and SAID in m["error"]
    assert _mark(box, spec, "theirs")["slot"] == HOSTILE
    assert (by["answered"]["answered"], by["answered"]["by"]) == (SAID, SAID)
    failed = [f for k, f in events if k == "command.failed"]
    assert len(failed) == 2 and all(f["outcome"] == "unknown" for f in failed), events
    for f in failed:
        _one_line_and_short(f["error"], f"({SAID})")
    quoting = [line for line in said.lines if "box-b" in line]
    assert len(quoting) == 3, said.lines                                              # two not performed, one said again
    for line in quoting:
        _one_line_and_short(line, SAID)
    assert json.loads(box.objects.get(spec.sub.command_key("answered")))["outcome"] == HOSTILE   # not rewritten
    # the reaper: an answer that never reached a heartbeat, its row cleared and its `outcome` said in the line
    con = SpecController(spec, box.vars, box.objects, wall=box.wall)
    old = box.wall() - requests.REAP_AFTER - 5
    box.vars.put(spec.sub.request_key("gone"), {"unit": "c1", "add": "1", "valid_until": str(old)})
    box.objects.put(spec.sub.command_key("gone"), canonical_json(
        {"instance": HOSTILE, "slot": "w-9", "unit": "c1", "outcome": HOSTILE, "at": old}).encode())
    with _Said() as said:
        requests.clear_requests(con)
    [line] = [line for line in said.lines if "gone" in line]
    _one_line_and_short(line, f"was answered ({SAID})")
    assert json.loads(box.objects.get(spec.sub.command_key("gone")))["outcome"] == HOSTILE
