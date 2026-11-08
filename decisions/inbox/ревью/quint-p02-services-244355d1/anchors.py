#!/usr/bin/env python3
"""Сверка якорей модели и отчёта по байтам среза 244355d161139bd6fe65fd68c7e5134598c21ba3.

Запуск из корня worktree: python3 <этот файл>. Читает файлы через `git show <пин>:путь`
(а не из рабочей копии); не пускает рабочие деревья. Для каждого якоря проверяется, что
строка содержит указанную подстроку. Итог — runs/anchors.log, код выхода 0 при полном совпадении.
"""
import os, re, subprocess, sys

PIN = "244355d161139bd6fe65fd68c7e5134598c21ba3"
WT = "/home/pilot/review103-claude-adr0130-p02-quint"
P = "Platform/"
# короткие имена → путь на срезе
FILES = {
    "02.3": P + "02-installer/spec/02.3-installer.norms.md",
    "02.4": P + "02-installer/spec/02.4-installer.norms.md",
    "02.1": P + "02-installer/spec/02.1-installer.norms.md",
    "machine": P + "02-installer/forms/rollout-poll.machine.yaml",
    "pres": P + "common/contracts/presence-lock.md",
    "sc": P + "common/contracts/store-client.md",
    "03.2": P + "03-worker/spec/03.2-worker.norms.md",
    "life": P + "02-installer/lifecycle.md",
}
A = [
    ("02.3", 207, "as the first step, before step 1"),
    ("02.3", 212, "repeat it with a pause of 1 s"),
    ("02.3", 213, "`START_WAIT` = 60 s after the start of the process, do not start with code 1"),
    ("02.3", 228, "The runner is a reader of the view"),
    ("02.3", 229, "within `START_WAIT`"),
    ("02.3", 233, "«Do not start» means to exit with a non-zero code"),
    ("02.3", 234, "RestartPreventExitStatus=2"),
    ("02.3", 372, "The two start codes are checked by reading"),
    ("02.3", 375, "seams of the lesson have no directive"),
    ("02.4", 48, "RestartPreventExitStatus=2 (a start refusal"),
    ("02.4", 49, "RestartSec=2; After=configstore.service (not Wants: the store is not pulled in)"),
    ("02.4", 50, "ProtectSystem=strict"),
    ("02.4", 55, "configstore-admin.socket"),
    ("02.4", 58, "Service=configstore.service"),
    ("02.4", 62, "Type=notify; NotifyAccess=main"),
    ("02.4", 72, "w2c-run.sh worker"),
    ("02.4", 87, "Type=notify; NotifyAccess=main; WatchdogSec=360; TimeoutStopSec = worker.stop_timeout"),
    ("02.4", 88, "20…50, default 20"),
    ("02.4", 102, "Type=oneshot, Restart=no"),
    ("02.4", 104, "OnBootSec 1–2 min"),
    ("02.4", 105, "OnUnitActiveSec 1 min"),
    ("02.4", 115, "the controller sends READY=1 after the schema check"),
    ("02.4", 116, "the worker — after capturing the name"),
    ("02.4", 217, "reads its own series <sub>_workers_wanted"),
    ("02.4", 224, "failed, the last successful collection is older than a minute by the local monotonic clock"),
    ("02.4", 225, "is greater than 60 or −1"),
    ("02.4", 227, "start the missing ones of this set (the smallest first), stop the running ones"),
    ("02.4", 236, "passes are serialised; a number is reserved until start; an uncertain outcome"),
    ("02.4", 238, "exactly one mechanism executes the series on an installation"),
    ("02.4", 239, "stopping — systemctl stop"),
    ("02.4", 395, "wait for its answer GET /v1/status"),
    ("02.4", 530, "a restart of a member by RestartSec=2 keeps it down for 2 s"),
    ("02.4", 533, "install with W2C_HOLD"),
    ("02.4", 534, "also on a repeat of rollout"),
    ("02.4", 558, "the barrier waits no longer than ROLLOUT_WAIT, polling once per 1 s"),
    ("02.4", 560, "ROLLOUT_WAIT: 300 s"),
    ("02.4", 561, "a repeat with the same command is harmless"),
    ("02.4", 563, "does not enable the units of the subsystems of the rollout"),
    ("02.4", 821, "`After` sets the start order, but not the readiness of the store"),
    ("02.1", 235, "`worker.stop_timeout` — an integer from 20 to 50, default 20"),
    ("03.2", 537, "an exclusive blocking flock"),
    ("03.2", 555, "the name is not obtained → writing_allowed = false, no heartbeat"),
    ("03.2", 668, "seek_name()"),
    ("pres", 32, "open(O_CREAT) → an exclusive blocking flock"),
    ("sc", 89, "the answer read limit and the answer wait term — decided by the client implementation"),
    ("machine", 38, "BATCH: 1"),
    ("machine", 39, "READ: 1"),
    ("machine", 40, "ROLLOUT_WAIT: 300"),
    ("machine", 73, "Events of one instant, in this order: read_expired; tick; wait_expired"),
    ("machine", 152, "id: tick-2"),
    ("02.4", 529, "two observations of one voter"),
]
REPORT = "decisions/inbox/ревью/РЕВЬЮ-ADR0130-P02-services-Claude-Quint.md"
TOKEN = r"`(02\.[134]|03\.2|machine|pres|sc):(\d+)`"

def main():
    os.chdir(WT)
    bad = 0
    out = []
    cache = {}
    for short, line, needle in A:
        path = FILES[short]
        if short not in cache:
            data = subprocess.check_output(["git", "show", PIN + ":" + path])
            cache[short] = data.decode("utf8").split("\n")
        lines = cache[short]
        text = lines[line - 1] if line <= len(lines) else ""
        ok = needle in text
        if not ok:
            bad += 1
        out.append("%s\t%s:%d\t%s\t%s" % ("ok" if ok else "BAD", short, line, needle, "" if ok else text[:200]))
    # Каждый якорь отчёта должен быть в списке выше.
    known = {(a[0], a[1]) for a in A}
    unknown = sorted(set(re.findall(TOKEN, open(os.path.join(WT, REPORT), encoding="utf8").read())) - {(a, str(b)) for a, b in known})
    for short, line in unknown:
        bad += 1
        out.append("BAD\tотчёт: якорь вне списка\t%s:%s" % (short, line))
    out.append("bad=%d total=%d report_unknown=%d pin=%s" % (bad, len(A), len(unknown), PIN))
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "runs", "anchors.log"), "w", encoding="utf8") as fh:
        fh.write("\n".join(out) + "\n")
    print(out[-1])
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
