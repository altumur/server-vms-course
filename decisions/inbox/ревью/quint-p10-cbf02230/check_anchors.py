#!/usr/bin/env python3
"""Checks file:line anchors of the models and the report against the bytes of the slice."""
import subprocess, sys
PIN = "cbf02230bf9a6a2cb69fb72bdbee7704b94914f7"
ROOT = "/home/pilot/review103-claude-adr0130-p10-quint"
N = "Platform/10-domain-console/spec/10-domain-console.norms.md"
C = "Platform/common/contracts/"
A = [
 (N, 57, "audit/domainconsole"), (N, 66, "next to the process `domain`"), (N, 90, "by the wall clock of the console"),
 (N, 175, "the domain console is a door"), (N, 186, "502 on a break and on silence"), (N, 343, "silent_after"),
 (N, 407, "discards a broken witness"), (N, 410, "whose read the store did not confirm"), (N, 412, "`last_report` is `received_at`"),
 (N, 416, "`page: \"garbled\"`"), (N, 433, "now − last_report > silent_after"), (N, 442, "complete = all ok"),
 ("Platform/10-domain-console/forms/runtime-constants.tsv", 4, "LOST_AFTER\t45"),
 ("Platform/10-domain-console/lifecycle.md", 63, "## Signals and readiness"),
 ("Platform/10-domain-console/lifecycle.md", 68, "The readiness is the port"),
 (C+"gate-and-pass.md", 168, "403 → the journal access.denied"),
 (C+"gate-and-pass.md", 596, "a stream has no limit"),
 (C+"gate-and-pass.md", 614, "close:"), (C+"gate-and-pass.md", 615, "exp has come"),
 (C+"gate-and-pass.md", 644, "takes the stream lane"), (C+"gate-and-pass.md", 646, "PASS_STREAMS_MAX: 256"), (C+"gate-and-pass.md", 647, "PASS_TICKET_CHECK: 5"),
 (C+"forwarding.md", 85, "no answer within FORWARD_WAIT"), (C+"forwarding.md", 89, "the default 5 s"),
 (C+"forwarding.md", 123, "A stream has neither"), (C+"forwarding.md", 239, "`/domain/alarms`"),
 (C+"forwarding.md", 278, "Streaming and pass retain"), (C+"domain-token.md", 47, "exp = iat + TOKEN_LIFETIME"),
 ("Platform/08-domain/forms/runtime-constants.tsv", 14, "TOKEN_LIFETIME\t900"),
 (C+"production-obligations.md", 9, "shutdown and accepted-work completion"),
 (C+"production-obligations.md", 11, "A stalled dependency cannot indefinitely hold a shared lock"),
 ("Platform/08-domain/spec/08.0-domain.norms.md", 130, "Idempotency-Key is optional"),
 ("Platform/08-domain/spec/08.0-domain.norms.md", 134, "a repeat after a lost answer"),
 ("Platform/08-domain/spec/08.0-domain.norms.md", 142, "the same print — the former answer"),
 ("Platform/08-domain/spec/08.0-domain.norms.md", 144, "409 in flight"),
 ("Platform/08-domain/spec/08.0-domain.norms.md", 145, "in one batch"),
 ("Platform/08-domain/spec/08.0-domain.norms.md", 156, "does not carry the memory"),
 (C+"accept.md", 63, "REPORT_EVERY:   5"), (C+"accept.md", 71, "The mark is the boundary"), (C+"accept.md", 73, "bounded marker reread"),
 (C+"accept.md", 271, "1 … 3600"), (C+"accept.md", 376, "MB2"), (C+"accept.md", 378, "MB3"),
 ("Platform/common/vectors/production-obligations/README.md", 25, "**MB3**"),
 (C+"event-journal.md", 92, "all processes of this role"), (C+"event-journal.md", 93, "LOCK_EX"), (C+"event-journal.md", 188, "fsync of the line"),
 (C+"event-journal.md", 202, "the caller decides"), (C+"event-journal.md", 222, "Common finite budgets"),
 ("Platform/08-domain/spec/08.9-domain.norms.md", 262, "the history lines of this"),
 ("Platform/08-domain/spec/08.1-domain.norms.md", 219, "MUST carry its"),
 ("Platform/02-installer/spec/02.4-installer.norms.md", 707, "one active per cluster"),
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
