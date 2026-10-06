"""A worker files a request to another subsystem through the base, and only where its spec says (ADR-0013: the platform
executes its own key). `worker: {requests: [<sub>, …]}` shaped only the store's grant — a cluster's rights refused a write
past it, a box's file store checked nothing — and the workers wrote `<sub>/requests/<id>` by hand. Now
`Worker.file_request` refuses an undeclared subsystem (nothing written, counted, said), stamps the row as the platform
does (`by`, `at`, `filed`) and writes it create-only — idempotently: the same request filed again stands, a different
one under a taken id is refused (ADR-0013: "not more than once" is about performing); and no worker of the VMS writes a
request row by hand."""
import ast
import glob
import os

from tests.conftest import Box, testsub, testsub2
from w2cplatform.contract import requests_acl
from w2cplatform.worker import RequestRefused, Worker

SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Bare(Worker):
    def reconcile_once(self, now=None):
        return []


def _worker(box, spec, name, vars_=None):
    w = _Bare(spec.sub, None, vars_ or box.vars, box.objects, clock=box.clock, wall=box.wall, spec=spec,
              resource_root=box.resource_root)
    w.claim_slot(name)
    return w


def _refused(fn, words: str) -> None:
    try:
        fn()
    except RequestRefused as e:
        assert words in str(e), str(e)
        return
    raise AssertionError(f"not refused: {words}")


def test_a_worker_whose_spec_names_no_subsystem_files_nothing():
    """testsub's spec has no `worker.requests`: every filing is refused, nothing is written — on a box's store, which
    has no rights to refuse it — and the refusal is counted and in the heartbeat."""
    box = Box()
    w = _worker(box, testsub(), "w-1")
    assert testsub().worker_requests == ()
    _refused(lambda: w.file_request("testsub2", "r1", {"unit": "testsub2/t1", "add": 1}), "does not name 'testsub2'")
    _refused(lambda: w.file_request("testsub", "r2", {"unit": "testsub/c1", "add": 1}), "`worker.requests` (none)")
    assert box.vars.list("testsub2/requests/") == [] and box.vars.list("testsub/requests/") == []
    assert w.filings == {"filed": 0, "again": 0, "refused": 2}
    assert w.platform_fields()["filings"] == {"filed": 0, "again": 0, "refused": 2}


def test_a_worker_files_to_the_subsystem_its_spec_names_and_to_no_other():
    """testsub2 declares `worker.requests: [testsub]`: it files to testsub — stamped by the platform, the values in
    their one text, create-only — and not to itself nor to anybody else. Under the grant its spec shapes, too."""
    box = Box()
    spec = testsub2()
    assert spec.worker_requests == ("testsub",)
    grant = box.vars.as_writer("testsub2-worker", spec.acl_worker_role())
    assert set(requests_acl("testsub")) <= set(spec.acl_worker_role())
    w = _worker(box, spec, "t-1", vars_=grant)
    now = box.wall()
    assert w.file_request("testsub", "add-1", {"unit": "testsub/c1", "add": 2, "valid_until": now + 30.5, "none": None},
                          unit="t1", at=now - 4)
    row, _ = box.vars.get("testsub/requests/add-1")
    assert set(row) == {"unit", "add", "valid_until", "by", "at", "filed"}, row            # `None`: no value, left out
    assert (row["unit"], row["add"], row["by"]) == ("testsub/c1", "2", "testsub2/t1"), row
    assert float(row["valid_until"]) == now + 30.5 and float(row["at"]) == now - 4 and float(row["filed"]) == now
    # another request under the same id is refused, and the row that stands is left as it is (the idempotence: below)
    _refused(lambda: w.file_request("testsub", "add-1", {"unit": "testsub/c1", "add": 9}),
             "under this rid stands a different request")
    assert box.vars.get("testsub/requests/add-1")[0]["add"] == "2"
    # no unit named: the slot is who filed it
    assert w.file_request("testsub", "add-2", {"unit": "testsub/c1", "add": 1})
    assert box.vars.get("testsub/requests/add-2")[0]["by"] == "testsub2/t-1"
    _refused(lambda: w.file_request("testsub2", "self", {"unit": "testsub2/t1", "add": 1}), "does not name 'testsub2'")
    _refused(lambda: w.file_request("vms", "x", {"unit": "vms/1"}), "does not name 'vms'")
    _refused(lambda: w.file_request("testsub", "a/b", {"unit": "testsub/c1"}), "a name, not a path")
    _refused(lambda: w.file_request("testsub", "own", {"unit": "testsub/c1", "by": "me"}), "the platform's to stamp")
    assert box.vars.list("testsub2/requests/") == [] and box.vars.list("vms/requests/") == []
    assert sorted(box.vars.list("testsub/requests/")) == ["testsub/requests/add-1", "testsub/requests/add-2"]
    assert w.filings == {"filed": 2, "again": 0, "refused": 5}


def test_the_same_request_filed_again_stands_and_a_different_one_under_its_id_is_refused():
    """ADR-0013: "not more than once" is about PERFORMING; FILING is idempotent. A filer that files again — a pusher
    replaying an event after a restart — files the same request: `by`, `at` (the event's moment) and the fields the
    same, only the base's own `filed` later by the clock. That is a success, counted `again`, and the row that stands
    keeps its first `filed`. Anything else under the same id — another value, another `at`, another `by` — is another
    request: refused, said and counted, the row untouched. It passed silently before, as `False`."""
    box = Box()
    w = _worker(box, testsub2(), "t-1")
    t0 = box.wall()
    asked = {"unit": "testsub/c1", "add": 2, "valid_until": t0 + 30}
    assert w.file_request("testsub", "r1", asked, unit="t1", at=t0 - 4)
    first, idx = box.vars.get("testsub/requests/r1")
    box.wall.advance(7)                                  # the clock moved on: only `filed` would differ
    assert w.file_request("testsub", "r1", dict(asked), unit="t1", at=t0 - 4) is False     # stands; this call wrote nothing
    assert box.vars.get("testsub/requests/r1") == (first, idx) and float(first["filed"]) == t0
    assert box.vars.list("testsub/requests/") == ["testsub/requests/r1"]
    assert w.filings == {"filed": 1, "again": 1, "refused": 0}
    for other in (lambda: w.file_request("testsub", "r1", {**asked, "add": 3}, unit="t1", at=t0 - 4),       # a field
                  lambda: w.file_request("testsub", "r1", {**asked, "more": "x"}, unit="t1", at=t0 - 4),    # one more
                  lambda: w.file_request("testsub", "r1", asked, unit="t1", at=t0 - 3),                     # `at`
                  lambda: w.file_request("testsub", "r1", asked, unit="t2", at=t0 - 4),                     # `by`
                  lambda: w.file_request("testsub", "r1", asked, unit="t1")):                    # `at`: now, by default
        _refused(other, "under this rid stands a different request")
    assert box.vars.get("testsub/requests/r1") == (first, idx)
    assert w.filings == {"filed": 1, "again": 1, "refused": 5}


def test_the_filings_are_on_metrics_by_the_specs_own_line():
    """The review's fourteenth pass, major 3: `filings` were in the heartbeat alone, and a filing refused again and again
    raised no alert. The spec of a subsystem whose workers file says it (`filings_total`, from
    `heartbeat.filings.<outcome>`, summed over its workers — «Паритет»'s line in testsub2, `auto`, `rec`): one line per
    outcome, each number by its value (ADR 0055)."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.spec import SpecController
    box = Box()
    spec = testsub2()
    assert any(m["name"] == "filings_total" and m["path"] == ["filings", "<outcome>"] for m in spec.metrics)
    w = _worker(box, spec, "t-1")
    w.server = "srv-1"                                                  # a heartbeat names its server, or does not parse
    row = {"unit": "testsub/c1", "add": 1, "valid_until": box.wall() + 30}
    assert w.file_request("testsub", "f-1", row, unit="t1") is True
    assert w.file_request("testsub", "f-1", dict(row), unit="t1") is False
    _refused(lambda: w.file_request("testsub", "f-1", {**row, "add": 2}, unit="t1"), "a different request")
    assert w.platform_fields()["filings"] == {"filed": 1, "again": 1, "refused": 1}
    w.heartbeat_once()
    text = SpecConsole(SpecController(spec, box.vars, box.objects, wall=box.wall)).metrics_text()
    said = [ln for ln in text.splitlines() if ln.startswith("testsub2_filings_total")]
    assert said == ['testsub2_filings_total{outcome="again"} 1', 'testsub2_filings_total{outcome="filed"} 1',
                    'testsub2_filings_total{outcome="refused"} 1'], said
    assert "# TYPE testsub2_filings_total counter" in text.splitlines()


def test_a_standing_row_that_does_not_read_is_refused_and_never_overwritten():
    box = Box()
    w = _worker(box, testsub2(), "t-1")
    torn = b'{"items": {"unit": "testsub/c1"'          # a row torn mid-write
    path = box.vars._file("testsub/requests/torn")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(torn)
    _refused(lambda: w.file_request("testsub", "torn", {"unit": "testsub/c1", "add": 1}), "does not parse")
    with open(path, "rb") as f:
        assert f.read() == torn
    assert w.filings == {"filed": 0, "again": 0, "refused": 1}


def test_a_fenced_instance_files_nothing():
    box = Box()
    w = _worker(box, testsub2(), "t-1")
    w.fence("its name was taken")
    _refused(lambda: w.file_request("testsub", "r1", {"unit": "testsub/c1", "add": 1}), "fenced")
    assert box.vars.list("testsub/requests/") == []


# THE BASE IS THE ONE WAY (ADR-0013): in a module of the VMS that defines a worker, no store write whose key is a
# request row — `put(f"{sub}/requests/{rid}", …)`, `put(X.request_key(…), …)` — and no `request_key` at all.
def _raw_request_writes(text: str) -> list[str]:
    tree = ast.parse(text)
    if not any(isinstance(n, ast.ClassDef) and any("Worker" in ast.unparse(b) for b in n.bases) for n in ast.walk(tree)):
        return []
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            first = ast.unparse(n.args[0]) if n.args else ""
            if n.func.attr == "request_key" or (n.func.attr in ("put", "put_new") and
                                                ("requests/" in first or "request_key" in first or "REQUESTS" in first)):
                out.append(f"line {n.lineno}: {ast.unparse(n)[:120]}")
    return out


def test_no_worker_of_the_vms_writes_a_request_row_by_hand():
    old = ('class AutoWorker(Worker):\n    def file(self, sub, rid, at):\n'
           '        self.vars.put(f"{sub}/requests/{rid}", {"at": str(at)})\n')
    assert _raw_request_writes(old), "the check finds the write it was made for"
    found = {}
    for path in sorted(glob.glob(os.path.join(SOURCE, "vms", "*.py"))):
        with open(path, encoding="utf-8") as f:
            bad = _raw_request_writes(f.read())
        if bad:
            found[os.path.basename(path)] = bad
    assert not found, f"a worker files only by `Worker.file_request` (ADR-0013): {found}"
