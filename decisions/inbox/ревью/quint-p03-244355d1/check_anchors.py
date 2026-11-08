#!/usr/bin/env python3
"""Сверяет якоря отчёта и моделей с байтами среза 244355d1 (git show <пин>:<путь>).

Запуск из корня worktree: python3 decisions/inbox/ревью/quint-p03-244355d1/check_anchors.py
Строка считается совпавшей, если подстрока найдена в указанной строке файла на срезе.
"""
import subprocess, sys

PIN = "244355d161139bd6fe65fd68c7e5134598c21ba3"
S = "Platform/03-worker/spec/"
F = "Platform/03-worker/forms/"
C = "Platform/common/contracts/"

ANCHORS = [
    (F + "runtime-constants.tsv", 4, "LEASE_TTL\t30"),
    (F + "runtime-constants.tsv", 5, "LEASE_MARGIN\t5"),
    (F + "runtime-constants.tsv", 20, "PERFORM_TIMEOUT\t10"),
    (F + "runtime-constants.tsv", 21, "PERFORM_GRACE_MS\t200"),
    (F + "README.md", 114, "One ordered transition is one row"),
    (F + "README.md", 120, "reads and local calendar-day computation are inputs"),
    (F + "README.md", 125, "Actions are executed in row order"),
    (F + "contender-writer.machine.yaml", 96, "choose_phase"),
    (F + "contender-writer.traces.tsv", 15, "same-state-since-survives-clock-backward"),
    (S + "03.2-worker.norms.md", 45, "LEASE_EVERY: (LEASE_TTL - LEASE_MARGIN) / 3"),
    (S + "03.2-worker.norms.md", 46, "again: the slot renewal got no answer"),
    (S + "03.2-worker.norms.md", 51, "WRITE_WINDOW: SLOT_TERM - HOLD_SKEW"),
    (S + "03.2-worker.norms.md", 90, "RENEW_EVERY: LEASE_EVERY"),
    (S + "03.2-worker.norms.md", 112, "monotonic moment of sending the last"),
    (S + "03.2-worker.norms.md", 114, "Its own term ends SLOT_TERM after this moment"),
    (S + "03.2-worker.norms.md", 160, "silent:"),
    (S + "03.2-worker.norms.md", 161, "lost:"),
    (S + "03.2-worker.norms.md", 162, "may_act:"),
    (S + "03.2-worker.norms.md", 163, "lost and the slot term"),
    (S + "03.2-worker.norms.md", 165, "may_write:"),
    (S + "03.2-worker.norms.md", 166, "unconfirmed_max:"),
    (S + "03.2-worker.norms.md", 171, "The moment of a request is before the first send"),
    (S + "03.2-worker.norms.md", 408, "every RENEW_EVERY"),
    (S + "03.2-worker.norms.md", 411, "the store did not answer"),
    (S + "03.2-worker.norms.md", 428, "the stand-in re-reads the slot before renewing"),
    (S + "03.2-worker.norms.md", 430, "a released slot the place can no longer"),
    (S + "03.2-worker.norms.md", 496, "t0 = now (monotonic)"),
    (S + "03.2-worker.norms.md", 499, "overslept"),
    (S + "03.2-worker.norms.md", 500, "last = max(last, t0)"),
    (S + "03.2-worker.norms.md", 503, "the store did not answer"),
    (S + "03.2-worker.norms.md", 504, "already silent"),
    (S + "03.2-worker.norms.md", 512, "With silent, actions stop by the end of the window"),
    (S + "03.2-worker.norms.md", 513, "unconfirmed_max"),
    (S + "03.2-worker.norms.md", 568, "1. renew the slot"),
    (S + "03.2-worker.norms.md", 574, "read platform/epoch_floor"),
    (S + "03.2-worker.norms.md", 575, "lost = those without may_write"),
    (S + "03.2-worker.norms.md", 592, "nothing is lost until the ceiling"),
    (S + "03.2-worker.norms.md", 850, "the silence"),
    (S + "03.3-worker.norms.md", 42, "POLL: implementation choice"),
    (S + "03.3-worker.norms.md", 82, "the reconciliation pass"),
    (S + "03.3-worker.norms.md", 102, "the pump"),
    (S + "03.3-worker.norms.md", 104, "start_of_previous_lease_step"),
    (S + "03.3-worker.norms.md", 105, "HEARTBEAT_EVERY"),
    (S + "03.3-worker.norms.md", 106, "pause until POLL"),
    (S + "03.3-worker.norms.md", 107, "guarded(step name)"),
    (S + "03.3-worker.norms.md", 112, "One loop thread"),
    (S + "03.4-worker.norms.md", 168, "STALL:"),
    (S + "03.4-worker.norms.md", 169, "WAKE:"),
    (S + "03.4-worker.norms.md", 374, "STALL < age <= FOR"),
    (S + "03.4-worker.norms.md", 378, "confirming read of the epoch row"),
    (S + "03.4-worker.norms.md", 385, "age <= STALL: no stand-in actions"),
    (S + "03.4-worker.norms.md", 412, "the stand-in — stop"),
    (S + "03.4-worker.norms.md", 413, "before_stop_all"),
    (S + "03.4-worker.norms.md", 415, "let go of the place"),
    (S + "03.4-worker.norms.md", 416, "give away the slot"),
    (S + "03.4-worker.norms.md", 421, "a crash is silent"),
    (S + "03.4-worker.norms.md", 508, "stop_timeout"),
    (S + "03.4-worker.norms.md", 510, "WRITE_WINDOW"),
    (S + "03.6-worker.norms.md", 77, "under may_write and before the last heartbeat"),
    (S + "03.6-worker.norms.md", 259, "while a call into the group is busy"),
    (S + "03.6-worker.norms.md", 275, "PERFORM_TIMEOUT"),
    (S + "03.6-worker.norms.md", 278, "If the deadline has passed"),
    (S + "03.6-worker.norms.md", 288, "valid_until"),
    (S + "03.6-worker.norms.md", 305, "no answer"),
    (S + "03.6-worker.norms.md", 315, "not more than one unfinished call"),
    (S + "03.6-worker.norms.md", 317, "PERFORM_TIMEOUT"),
    (S + "03.6-worker.norms.md", 318, "calls of two holders can overlap"),
    (C + "slot.md", 45, "SLOT_TERM: 45"),
    (C + "env-file.md", 120, "FOR:"),
    (C + "store-client.md", 87, "no_reply:"),
    (C + "store-client.md", 89, "wait:"),
    (C + "observation.md", 98, "HOLD_SKEW: 5"),
    ("Platform/02-installer/spec/02.1-installer.norms.md", 235, "stop_timeout"),
]


def main():
    cache = {}
    bad = 0
    for path, line, needle in ANCHORS:
        if path not in cache:
            p = subprocess.run(["git", "show", f"{PIN}:{path}"], capture_output=True)
            if p.returncode != 0:
                print("NOFILE", path)
                bad += 1
                cache[path] = None
                continue
            cache[path] = p.stdout.decode("utf-8", "replace").split("\n")
        lines = cache[path]
        if lines is None or line > len(lines) or needle not in lines[line - 1]:
            print(f"MISMATCH {path}:{line} needle={needle!r} got={(lines[line-1] if lines and line<=len(lines) else '')[:100]!r}")
            bad += 1
    print(f"anchors checked: {len(ANCHORS)}, mismatches: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
