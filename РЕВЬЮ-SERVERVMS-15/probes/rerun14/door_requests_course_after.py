# RERUN-15 COPY of РЕВЬЮ-SERVERVMS-14/probes/door/door_requests_course.py for course 2f90fbd5: the ledgers moved from
# `<sub>/requests/asks-…` to `<sub>/asked/<16hex>` (ADR 0060). Case 4 counts rows under sub.asked_prefix() and runs
# clear_requests(sweep=True) and then clear_asked(ctl); case 2 names the victim ledger by its new basename (16 hex).
# Probe (r14 door, COURSE): the request door POST /<sub>/requests — same rid under another person/body, rid "asks-<victim>",
# rid edge cases (unicode length, backslash, U+2028, U+0085), maxLength on 100 000 chars, Idempotency-Key replay
# (same body / other body / other user), a garbled request row in a person's ledger, ledger reaped after ttl.
# Run: <venv python> door_requests_course.py <course Source root>. Prints one line per case: name, status, what came back.
# Expected (correct behaviour): cross-person same rid -> 409 (measured 202 with the other's row = defect);
# asks-<victim> -> 400 (product refuses; measured 202 with the victim's ledger = defect); garbled own row -> 429/503 not 500.
import copy
import hashlib
import json
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, root)
os.chdir(root)

import yaml  # noqa: E402

from tests.conftest import TESTSUB2, Box, Served, controller, testsub2  # noqa: E402
from w2cplatform.console import SpecConsole  # noqa: E402
from w2cplatform.spec import SubsystemSpec  # noqa: E402

testsub2()  # registers testsub in the catalogue (testsub2 follows it)
raw = yaml.safe_load(open(TESTSUB2))


def spec_with(per_person: bool, key: bool):
    d = copy.deepcopy(raw)
    r = d["requests"]
    r["schema"]["properties"]["id"] = {"type": "string"}          # as vms.subsystem.yaml allows `id`
    r["schema"]["properties"]["note"] = {"type": "string", "maxLength": 32}
    if not key:
        r.pop("key", None)
    if not per_person:
        r.pop("per_person", None)
    return SubsystemSpec.from_dict(d)


def run():
    out = []
    as_ = lambda who: {"X-User": who}  # noqa: E731

    # 1. same rid, another person, another unit/body (no `key`: the body's id names it, as on vms)
    box = Box(); spec = spec_with(per_person=False, key=False)
    ctl = controller(box, spec=spec)
    ctl.create({"name": "t1", "of": "c1"}); ctl.create({"name": "t2", "of": "c1"})
    with Served(SpecConsole(ctl, wall=box.wall)) as call:
        a = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "r1", "note": "anna's"}, headers=as_("anna"))
        b = call("POST", "/requests", {"unit": "testsub2/t2", "add": 9, "id": "r1", "note": "boris's"}, headers=as_("boris"))
        out.append(("cross_person_same_rid", a[0], b[0], b[1].get("queued")))
        # idempotency: same key same body / same key other body / same key other user
        body = {"unit": "testsub2/t1", "add": 2, "id": "r2"}
        k1 = call("POST", "/requests", body, headers=as_("anna"), key="K-1")
        k2 = call("POST", "/requests", body, headers=as_("anna"), key="K-1")
        k3 = call("POST", "/requests", {**body, "add": 3}, headers=as_("anna"), key="K-1")
        k4 = call("POST", "/requests", body, headers=as_("boris"), key="K-1")
        out.append(("idem_same", k1[0], k2[0], k1[1] == k2[1]))
        out.append(("idem_other_body", k3[0], k3[1].get("error")))
        out.append(("idem_other_user", k4[0], k4[1].get("error")))
        # rid edge cases
        for name, rid in [("rid_cyr150", "я" * 150), ("rid_cyr201", "я" * 201), ("rid_backslash", "a\\b"),
                          ("rid_u2028", "a b"), ("rid_u0085", "a\u0085b"), ("rid_dotdot", ".."), ("rid_slash", "a/b"),
                          ("rid_bidi", "a‮b"), ("rid_empty_string", "")]:
            r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": rid}, headers=as_("anna"))
            out.append((name, r[0], (r[1].get("queued") or {}).get("id", r[1].get("error")) if isinstance(r[1], dict) else r[1]))
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "note": "x" * 100_000}, headers=as_("anna"))
        out.append(("note_100000", r[0], r[1].get("fault")))
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "s1", "by": "admin"}, headers=as_("anna"))
        out.append(("forged_by_in_body", r[0], r[1].get("error")))

    # 2. rid = another person's ledger name, in a per_person family with no `key`
    box = Box(); spec = spec_with(per_person=True, key=False)
    ctl = controller(box, spec=spec)
    ctl.create({"name": "t1", "of": "c1"})
    with Served(SpecConsole(ctl, wall=box.wall)) as call:
        call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "secret-anna-ask"}, headers=as_("anna"))
        victim = hashlib.sha256(b"anna").hexdigest()[:16]; victim_key = spec.sub.asked_key("anna") if hasattr(spec.sub, "asked_key") else None
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": victim}, headers=as_("mallory"))
        out.append(("rid_is_victims_ledger", r[0], r[1].get("queued"), "victim ledger key", victim_key, "ledger row", box.vars.get(victim_key)[0] if victim_key else None))
        # 3. a garbled REQUEST row named in a person's ledger (the ledger itself reads)
        call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "own-1"}, headers=as_("vera"))
        path = box.vars._file(spec.sub.request_key("own-1"))
        open(path, "wb").write(b"{torn")
        box.wall.advance(spec.requests["settle"] + 1)       # past `settle`: the ledger now reads the row to keep the id
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "own-2"}, headers=as_("vera"))
        out.append(("garbled_own_row_in_ledger", r[0], r[1].get("error"), r[1].get("detail", "")[:80]))

    # 4. the ledger row after ttl: does the sweep remove it?
    box = Box(); spec = spec_with(per_person=True, key=True)
    ctl = controller(box, spec=spec)
    ctl.create({"name": "t1", "of": "c1"})
    from w2cplatform import requests as rq
    with Served(SpecConsole(ctl, wall=box.wall)) as call:
        call("POST", "/requests", {"unit": "testsub2/t1", "add": 1}, headers=as_("anna"))
    led = list(box.vars.list(spec.sub.asked_prefix()))
    box.wall.advance(spec.requests["ttl"] + 120)
    rq.clear_requests(ctl, sweep=True)
    left = list(box.vars.list(spec.sub.asked_prefix())); asked_gone = rq.clear_asked(ctl); left2 = list(box.vars.list(spec.sub.asked_prefix()))
    out.append(("ledger_after_ttl_sweep", len(led), len(left), "clear_asked removed", asked_gone, "left after clear_asked", len(left2)))
    for line in out:
        print(json.dumps(line, ensure_ascii=True, default=str)[:400])


run()
