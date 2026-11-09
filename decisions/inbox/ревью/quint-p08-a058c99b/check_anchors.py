#!/usr/bin/env python3
# Checks every anchor used by the model and the report against the bytes of the pin.
import subprocess, sys
PIN = "a058c99b05116c5e77f2ce62ec0685e7b01efe65"
S = "Platform/08-domain/spec/"
C = "Platform/common/contracts/"
K = "Platform/08-domain/forms/runtime-constants.tsv"
A = [
 (C+"accept.md", 92, "LOST_AFTER (45 s)"),
 (C+"accept.md", 217, "after the signature check"),
 (C+"accept.md", 218, "class server does not get it"),
 (C+"accept.md", 219, "from class camera in the last second"),
 (C+"accept.md", 289, "one at a time"),
 (C+"accept.md", 292, "same (write nothing"),
 (C+"accept.md", 307, "write reports/<rev>"),
 (C+"turn.md", 32, "TURN_TERM: 45"),
 (C+"turn.md", 33, "TURN_RENEW: 10"),
 (C+"turn.md", 81, "changes the version"),
 (C+"turn.md", 83, "cuts off an old write"),
 (C+"turn.md", 98, "NOT a fence"),
 (C+"production-obligations.md", 9, "lock acquisition and lock holding"),
 (C+"production-obligations.md", 9, "shutdown and accepted-work completion"),
 (C+"production-obligations.md", 11, "A stalled dependency cannot indefinitely hold"),
 (C+"store-client.md", 102, "Exactly one declared level owns retries"),
 (C+"domain-token.md", 45, "TOKEN_SKEW:    60"),
 (C+"domain-token.md", 86, "now > exp + TOKEN_SKEW"),
 (S+"08.0-domain.norms.md", 154, "An unknown outcome of the batch is a barrier"),
 (S+"08.1-domain.norms.md", 98, "After a restart of the same holder"),
 (S+"08.1-domain.norms.md", 101, "the new holder has no marks"),
 (S+"08.1-domain.norms.md", 707, "A failure of a read or of a write of a part of the pass"),
 (S+"08.2-domain.norms.md", 78, "the change waits until"),
 (S+"08.2-domain.norms.md", 80, "emergency"),
 (S+"08.2-domain.norms.md", 81, "floor(now) + TOKEN_SKEW + 1"),
 (S+"08.2-domain.norms.md", 83, "premise: the wall clocks of the holders"),
 (S+"08.3-domain.norms.md", 109, "after until it is cleaned up"),
 (S+"08.3-domain.norms.md", 685, "did not answer"),
 (S+"08.3-domain.norms.md", 686, "503 `{error: \"unavailable\"}`"),
 (S+"08.3-domain.norms.md", 687, "The write of step 7 failed"),
 (S+"08.3-domain.norms.md", 702, "is a barrier"),
 (S+"08.3-domain.norms.md", 704, "rolled back"),
 (S+"08.4-domain.norms.md", 79, "at + TOKEN_LIFETIME + TOKEN_SKEW"),
 (S+"08.4-domain.norms.md", 80, "at — the moment the mark is written"),
 (S+"08.5-domain.norms.md", 55, "by the wall clock of the process"),
 (S+"08.8-domain.norms.md", 203, "a fetch not older than BACKUP_FETCH"),
 (S+"08.8-domain.norms.md", 204, "writes domain/backup-taken when it has all parts"),
 (S+"08.8-domain.norms.md", 205, "GET /api/backup of the same cluster gives the head"),
 (S+"08.8-domain.norms.md", 206, "behind"),
 (S+"08.8-domain.norms.md", 299, "the answer deadline 90 s"),
 (S+"08.8-domain.norms.md", 301, "expired"),
 (S+"08.8-domain.norms.md", 308, "writer priority"),
 (S+"08.8-domain.norms.md", 308, "the waiting goes into the common deadline"),
 (S+"08.8-domain.norms.md", 385, "Release only after that work has completed"),
 (S+"08.8-domain.norms.md", 385, "This local exclusion does not replace"),
 (S+"08.8-domain.norms.md", 393, "deadline 90 s"),
 (S+"08.8-domain.norms.md", 408, "a split"),
 (S+"08.8-domain.norms.md", 414, "the neighbours"),
 (S+"08.8-domain.norms.md", 445, "did not give it"),
 (S+"08.8-domain.norms.md", 463, "the state = the copy"),
 (S+"08.8-domain.norms.md", 484, "objects — by value"),
 (S+"08.8-domain.norms.md", 517, "removed of the first gathering does not survive the second move"),
 (S+"08.8-domain.norms.md", 520, "removed:" if False else "domain/partial/<part>"),
 (S+"08.8-domain.norms.md", 541, "after a start the count begins anew"),
 (S+"08.8-domain.norms.md", 543, "the worst 2 GiB"),
 (S+"08.8-domain.norms.md", 810, "the rest of its state is already the copy's"),
 (S+"08.8-domain.norms.md", 923, "is not modelled yet"),
 (S+"08.10-domain.norms.md", 66, "by the local monotonic"),
 (S+"08.10-domain.norms.md", 67, "a new process counts anew: the term is only longer"),
 (S+"08.10-domain.norms.md", 69, "at the ceiling"),
 (S+"08.10-domain.norms.md", 70, "503"),
 (S+"08.10-domain.norms.md", 87, "on SIGTERM the active process gives up the turn"),
 (S+"08.10-domain.norms.md", 90, "every write of the domain process to a row"),
 (S+"08.10-domain.norms.md", 98, "get_at of the object"),
 (S+"08.10-domain.norms.md", 99, "put_at by the index read BEFORE the confirmation"),
 (S+"08.10-domain.norms.md", 101, "get_at after the confirmation"),
 (S+"08.10-domain.norms.md", 208, "On SIGTERM at the active process"),
 (S+"08.10-domain.norms.md", 210, "does not repeat the write"),
 (S+"08.10-domain.norms.md", 211, "an unknown outcome"),
 ("Platform/08-domain/lifecycle.md", 74, "`SIGTERM`"),
 (K, 14, "TOKEN_LIFETIME\t900"),
 (K, 30, "IDEM_KEEP\t86400"),
 (K, 31, "IDEM_MAX\t4096"),
 (K, 36, "REPORT_RATE\t200"),
 (K, 46, "BACKUP_EVERY_MIN\t30"),
 (K, 48, "BACKUP_FETCH\t600"),
 (K, 49, "BACKUP_HEADS\t5"),
 (K, 50, "PARTIAL_QUIET\t10800"),
]
bad = 0
cache = {}
for path, line, text in A:
    if path not in cache:
        cache[path] = subprocess.run(["git", "show", f"{PIN}:{path}"], capture_output=True, check=True).stdout.decode("utf8").split("\n")
    got = cache[path][line - 1]
    if text not in got:
        bad += 1
        print(f"MISS {path}:{line} want {text!r} got {got[:160]!r}")
print(f"anchors checked: {len(A)}, missing: {bad}")
sys.exit(1 if bad else 0)
