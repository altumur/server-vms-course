#!/usr/bin/env python3
"""Сверка якорей отчёта и моделей по байтам среза (git show <pin>:path)."""
import subprocess, sys, pathlib

PIN = "959af8d62e7c35ab527fde6e86979b1279ead2ba"
A = {
 "N": "Platform/04-controller/spec/04-controller.norms.md",
 "L": "Platform/04-controller/lifecycle.md",
 "T": "Platform/common/contracts/turn.md",
 "RCK": "Platform/common/contracts/row-check.md",
 "OB": "Platform/common/contracts/observation.md",
 "SL": "Platform/common/contracts/slot.md",
 "EF": "Platform/common/contracts/env-file.md",
 "PO": "Platform/common/contracts/production-obligations.md",
 "S1": "Platform/01-store/spec/01.1-store.norms.md",
 "01C": "Platform/01-store/forms/runtime-constants.tsv",
 "024": "Platform/02-installer/spec/02.4-installer.norms.md",
 "RC": "Platform/04-controller/forms/runtime-constants.tsv",
 "SF": "Platform/04-controller/forms/slot-fate.tsv",
 "SR": "Platform/04-controller/forms/slot-release.tsv",
 "DF": "Platform/04-controller/forms/daemon-flags.tsv",
 "ADR": "decisions/0130-боевая-пригодность-сгенерированного-кода.md",
}
CHECKS = [
 ("N", 18, "Q4 retry ownership and Q5 bounded"), ("N", 185, "after a restart of the controller"), ("N", 186, "not later than the clock of the controller"),
 ("N", 188, "longer than N s by the clock of the controller"), ("N", 323, "moves nothing for the first LOST_AFTER"),
 ("N", 800, "delete of a unit row by delete_after"), ("N", 800, "turn is given up at the end of the pass"),
 ("N", 808, "first complete it"), ("N", 810, "freshly read"), ("N", 812, "free capacity with the reserves"),
 ("N", 819, "write the active intent"), ("N", 821, "freshly list/read ALL workers"), ("N", 824, "assign to each placement"),
 ("N", 826, "add ALL members"), ("N", 828, "write the intent {state: idle"), ("N", 842, "recovered **from step 3**"),
 ("N", 849, "Two admissions of different units"), ("N", 858, "every PASS_EVERY"), ("N", 868, "fresh look"),
 ("N", 877, "remove by ends"), ("N", 888, "unplaced for longer than delete_after"), ("N", 895, "ends deletes right"),
 ("N", 896, "manual row is not deleted"), ("N", 897, "A row with made is deleted"), ("N", 900, "deleted physically"),
 ("N", 911, "release the turn"), ("N", 912, "final"), ("N", 998, "counted from the first observation"),
 ("N", 1053, "shift of the writer clock"), ("N", 890, "delete the row with cas"), ("N", 1309, "stops with code 0"),
 ("SR", 11, "for a torn row write released"),
 ("T", 32, "TURN_TERM: 45"), ("T", 33, "TURN_RENEW: 10"), ("T", 46, "not changed for"), ("T", 51, "rewrite one's own turn"),
 ("T", 53, "every changing write"), ("T", 54, "guard {key: <turn>, index: my version}"), ("T", 54, "do not write until a confirmed renewal"), ("T", 56, "End of the pass"),
 ("T", 75, "on SIGTERM"), ("T", 80, "interrupts"), ("T", 83, "cuts off an old write"), ("T", 85, "substitute a newer guard"),
 ("T", 89, "even if the target row did not change"), ("T", 98, "NOT a fence"),
 ("L", 18, "one instance per manifest on every server"), ("L", 85, "WATCHDOG=1"), ("L", 87, "first LOST_AFTER"),
 ("L", 89, "SIGTERM"), ("L", 91, "Restart=always"),
 ("024", 67, "WatchdogSec=360"),
 ("RCK", 100, "delete:"), ("RCK", 101, "not_before"),
 ("OB", 44, "monotonic clock"), ("OB", 52, "age of the observed version"), ("OB", 56, "first observation is fresh"),
 ("SL", 38, "torn:"), ("SL", 45, "SLOT_TERM: 45"), ("SL", 47, "TORN_STILL"),
 ("EF", 121, "HUNG_MOVE_AFTER:"),
 ("PO", 9, "cancellation, shutdown"),
 ("S1", 81, "CLOCK_SKEW"), ("S1", 455, "admitted := max"), ("S1", 460, "MUST be checked against this stored time"),
 ("01C", 7, "CLOCK_SKEW"), ("RC", 4, "PASS_EVERY"), ("RC", 5, "TURN_BUSY_RETRY"),
 ("SF", 5, "non-answer/badkey"), ("SF", 6, "#var age"), ("SF", 14, "#var version"), ("SF", 16, "SLOT_TERM"), ("SF", 17, "LOST_AFTER"),
 ("SR", 7, "used as CAS"), ("SR", 13, "A CAS refusal"),
 ("DF", 28, "HUNG_MOVE_AFTER"),
 ("ADR", 188, "разрушающая чистка откладывается"),
]
here = pathlib.Path(__file__).resolve()
repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=here.parent, check=True, capture_output=True, text=True).stdout.strip()
cache = {}
bad = 0
for alias, line, needle in CHECKS:
    p = A[alias]
    if p not in cache:
        cache[p] = subprocess.run(["git", "show", f"{PIN}:{p}"], cwd=repo, check=True, capture_output=True).stdout.decode("utf8").split("\n")
    got = cache[p][line - 1] if line <= len(cache[p]) else ""
    if needle not in got:
        bad += 1
        print(f"MISMATCH {alias}:{line} !~ {needle!r}: {got[:120]!r}")
print(f"anchors checked: {len(CHECKS)}, mismatches: {bad}")
sys.exit(1 if bad else 0)
