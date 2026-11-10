#!/usr/bin/env python3
"""Checks file:line anchors of the models and the report against the bytes of the slice."""
import subprocess, sys
PIN = "ff32d483f6a099d05c9d06df8436e7745c2b4366"
ROOT = "/home/pilot/review103-claude-adr0130-p02-data-quint"
N23 = "Platform/02-installer/spec/02.3-installer.norms.md"
N22 = "Platform/02-installer/spec/02.2-installer.norms.md"
N21 = "Platform/02-installer/spec/02.1-installer.norms.md"
N24 = "Platform/02-installer/spec/02.4-installer.norms.md"
N25 = "Platform/02-installer/spec/02.5-installer.norms.md"
CL = "Platform/common/contracts/store-client.md"
PO = "Platform/common/contracts/production-obligations.md"
P011 = "Platform/01-store/spec/01.1-store.norms.md"
P012 = "Platform/01-store/spec/01.2-store.norms.md"
P013 = "Platform/01-store/spec/01.3-store.norms.md"
REF = "Platform/02-installer/forms/refusals.tsv"
A = [
 (N23, 34, "the mark never decreases"), (N23, 46, "FILES_TOTAL_MAX"), (N23, 53, "`manifest put` with an unreadable row"),
 (N23, 207, "Check the store schema"), (N23, 211, "there is no row/mark"), (N23, 212, "pause of 1 s"), (N23, 213, "`START_WAIT` = 60 s"),
 (N23, 216, "load_catalogue"), (N23, 218, "A mark below the row at start"), (N23, 236, "code 2"), (N23, 239, "code 1"),
 (N23, 242, "The decision between the two codes"), (N23, 244, "**Races.** The installer writes the row"),
 (N23, 248, "The installer, `manifest put <file>`"), (N23, 264, "full confirmed catalogue"), (N23, 266, "`max_value` and `max_body`"),
 (N23, 271, "row of a part is heavier"), (N23, 273, "Read the row, the view of the current form and the mark"),
 (N23, 274, "the same yaml, shell and files"), (N23, 275, "bring the parts up"), (N23, 276, "the row is the same but there is no view"),
 (N23, 282, "Check the weight of the view row"), (N23, 289, "Bring the parts up"), (N23, 291, "re-read the part and repeat"),
 (N23, 293, "Write the row"), (N23, 294, "repeat from step 9"), (N23, 295, "A refusal of step 14a"), (N23, 297, "On `toolarge`"),
 (N23, 300, "Write the view"), (N23, 301, "re-read the row and the view"), (N23, 305, "Bring the mark up"), (N23, 306, "re-read the mark"),
 (N23, 307, "Remove the parts"), (N23, 308, "digests outside its files"), (N23, 311, "not less often than once in 30 s"),
 (N23, 314, "The rev of the mark".lower().replace("the rev of the mark","the rev of the mark")), (N23, 315, "A mark below the remembered"),
 (N23, 320, "not a change"), (N23, 326, "The parts are written before the row"), (N23, 327, "503"),
 (N23, 329, "brought up by the next"), (N23, 350, "The installation profile admits"),
 (N22, 760, "heavier than the ceiling"), (N22, 773, "nothing is written"), (N22, 778, "If the view is not written"),
 (N22, 793, "installation window"), (N22, 794, "START_WAIT"),
 (N21, 1174, "the catalogue is checked whole"), (N21, 1190, "The catalogue is all manifests"),
 (N24, 28, "Q2: secret and recovery file"), (N24, 457, "atomic rename"),
 (N25, 184, "atomic rename"), (CL, 41, "guard:"), (CL, 47, "ROW_CEILING"), (CL, 80, "503 `unavailable`"), (CL, 81, "503 `ambiguous`"),
 (CL, 94, "the repeat answers"), (CL, 96, "at least two minutes"), (CL, 102, "ADR-0130 Addendum (10), Q4"),
 (PO, 9, "finite positive budgets"),
 (P011, 290, "413 toolarge"), (P011, 552, "the way JSON strings are escaped"), (P012, 241, "start refused, code 2"), (P013, 136, "restore"), (REF, 31, "put_part_over_ceiling"),
 (REF, 32, "put_row_over_ceiling"),
 ("Platform/01-store/forms/daemon-flags.tsv", 38, "524288"), ("Platform/01-store/forms/daemon-flags.tsv", 39, "1048576"),
 ("Platform/01-store/spec/01.3-store.norms.md", 298, "max_value, max_body"),
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
