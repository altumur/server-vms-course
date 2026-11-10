#!/usr/bin/env python3
"""Checks file:line anchors of the models and the report against the bytes of the slice."""
import subprocess, sys
PIN = "c777fcc828a34ae41d9e91f63229913b22058888"
ROOT = "/home/pilot/review103-claude-adr0130-p07-quint"
NR = "Platform/07-console-module/spec/07-console-module.norms.md"
CM = "Platform/07-console-module/CONSOLE-MODULE.md"
LOC = "Platform/07-console-module/data/localization.tsv"
RC = "Platform/06-console/forms/runtime-constants.tsv"
FWD = "Platform/common/contracts/forwarding.md"
PO = "Platform/common/contracts/production-obligations.md"
GP = "Platform/common/contracts/gate-and-pass.md"
N61 = "Platform/06-console/spec/06.1-console.norms.md"
N63 = "Platform/06-console/spec/06.3-console.norms.md"
N64 = "Platform/06-console/spec/06.4-console.norms.md"
N65 = "Platform/06-console/spec/06.5-console.norms.md"
N88 = "Platform/08-domain/spec/08.8-domain.norms.md"
N10 = "Platform/10-domain-console/spec/10-domain-console.norms.md"
RC10 = "Platform/10-domain-console/forms/runtime-constants.tsv"
ADR = "decisions/0130-боевая-пригодность-сгенерированного-кода.md"
A = [
 (NR, 8, "it has no life cycle: a library has no process"), (NR, 27, "The lesson has no time fields"), (NR, 31, "no rows, objects or files of its own"),
 (NR, 43, "reads:   /session"), (NR, 46, "writes:  POST/PUT/DELETE"), (NR, 47, "/domain/* (forwarding contract"), (NR, 48, "never:   /{sub}/requests, /api/backup"), (NR, 49, "order:   /session"),
 (NR, 50, "polling every poll_s"), (NR, 53, "unplaceable: /unplaceable"), (NR, 56, "wait=15"), (NR, 57, "the same load `order` at once"), (NR, 57, "at most once a second after an immediate return"),
 (NR, 58, "it need not compare revision"), (NR, 59, "the next attempt after poll_s"), (NR, 61, "Polling by poll_s remains"),
 (NR, 74, "An unreadable, refused or unavailable profile remains unknown"), (NR, 85, "one module object"), (NR, 95, "the promise waits"),
 (NR, 98, "throw {status, body, retry}"), (NR, 99, "apply to page calls through console.api"), (NR, 100, "makes its own writes by N1.4 writes"),
 (NR, 107, "the module sends no other headers"), (NR, 110, "one key per logical action"), (NR, 111, "20 s for each attempt through the complete response body"),
 (NR, 112, "409 in flight allow a replay only at these doors"), (NR, 113, "the delay before a replay"), (NR, 114, "without it — 2, 3, 5 s, after the third replay"),
 (NR, 115, "401 → the login window"), (NR, 116, "on an unknown outcome — a read first"), (NR, 123, "sends PUT and DELETE with ifMatch"),
 (NR, 138, "another user — the page resets its own"), (NR, 139, "leaving the page"), (NR, 146, "busy"), (NR, 148, "repaintTree()"),
 (NR, 179, "A failed root read skips only this cluster emission"), (NR, 183, "A failed domain continuation"), (NR, 187, "For each `mount(root, opts)` instance"),
 (NR, 189, "UI timestamp/date renderings"), (NR, 195, "Both domain loaders follow the opaque cursor"), (NR, 221, "POST /domain/move"), (NR, 229, "with sections: [domain]"), (NR, 230, "the units by subsystems from the view /domain"),
 (NR, 249, "A real failed continuation still uses"), (NR, 255, "the lesson has no process, door or"), (NR, 282, "an unknown outcome of `PUT` and of tables — a read first"),
 (NR, 298, "P/07 is packaging"), (NR, 303, "`module-calls`: the order on mounting"), (NR, 304, "`module-changes`"),
 (NR, 306, "a replay only of `POST /<rows>`"), (NR, 310, "`module-page-calls`"), (NR, 327, "Immutable request snapshot"), (NR, 328, "Complete-attempt timeout"),
 (NR, 334, "mixed-language mounted instances"), (NR, 342, "an implementation does not write it"),
 (CM, 96, "`POST` and `PUT` carry a new `Idempotency-Key`"), (CM, 178, "localStorage"), (CM, 190, "**«Retry» at a toast.**"), (CM, 248, "`busy()`"), (CM, 292, "the limit is 90 s"),
 (LOC, 186, "No link with the console"), (LOC, 438, "Not handed over"),
 (RC, 7, "CHANGES_WAIT"), (RC, 8, "CHANGES_SUBSCRIBERS_MAX"), (RC, 32, "CLAIM_TAKEOVER_AFTER"), (RC, 33, "DONE_ANSWER_KEEP"),
 (FWD, 89, "FORWARD_WAIT"), (FWD, 90, "90 s at /api/take and /domain/move"), (FWD, 91, "/domain/handover — 100 s"), (FWD, 232, "/domain/handover"), (FWD, 278, "Q4: each ordinary logical operation"),
 (PO, 9, "finite positive budgets"), (GP, 199, "server_time: wall-clock seconds"),
 (N61, 201, "`503 Retry-After`"), (N61, 550, "A message with `revision: 0`"), (N61, 554, "after` is not a number of this instance"), (N61, 690, "key:        (user, method, path, key)"), (N61, 740, "409 in flight"),
 (N63, 152, "server_time"), (N64, 282, "`POST /marks`"), (N65, 99, "poll_s: 5"), (N65, 255, "a lane is busy"), (N65, 292, "`busy` with `Retry-After: 1`"),
 (N88, 302, "forwarding (100 s) is longer than the common deadline"), (N88, 407, "a move is under way here already"),
 (N10, 90, "cursor"), (N10, 98, "The limit is hard"), (N10, 100, "On unchanged readable data"), (RC10, 3, "DOMAIN_PAGE_MEMBERS"),
 (ADR, 148, "Quint для гонок и сроков"), (ADR, 147, "Применимость"),
 (ADR, 159, "«нет бюджета»"), (ADR, 161, "модель Quint одна на урок"), (ADR, 165, "модель Quint одна на единицу"),
 (ADR, 188, "Скачки часов"),
]
bad = 0; cache = {}
for path, line, needle in A:
    if path not in cache:
        cache[path] = subprocess.run(["git", "-C", ROOT, "show", f"{PIN}:{path}"], capture_output=True).stdout.decode("utf8").split("\n")
    got = cache[path][line-1] if line-1 < len(cache[path]) else ""
    ok = needle in got
    if not ok:
        bad += 1
        print("BAD", path, line, repr(needle), "->", got[:120])
print(f"{len(A)} anchors, {bad} bad, pin {PIN}")
sys.exit(1 if bad else 0)
