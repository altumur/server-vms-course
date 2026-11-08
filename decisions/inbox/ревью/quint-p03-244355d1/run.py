#!/usr/bin/env python3
"""Прогоны модели Quint P/03 (ADR-0130) на срезе 244355d1.

Запуск:  python3 run.py [префикс-id ...]
Создаёт instances.qnt, runs/<id>.out, дополняет results.tsv и run.log.
Без аргументов выполняет всё. Ожидание expect задаётся заранее и в выводе не правится:
несовпадение остаётся строкой с match=no.

Только Quint/Apalache над этими моделями; SUT, native и кандидат не запускаются.
"""
import csv, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk", PATH="/opt/quint/jdk/bin:" + os.environ["PATH"], JVM_ARGS="-Xmx4g")
PORT = "8834"           # свой сервер Apalache (порт вне 8822); запускается отдельно, см. отчёт
HOLD = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p03q/HOLD"
OUT_COLS = ["id", "module", "invariant", "kind", "tool", "max_steps", "samples",
            "overrides", "expect", "actual", "match", "secs", "file"]


def b(v):
    return "true" if v else "false"


# ---- Параметры экземпляров: источник чисел — нормы, см. отчёт и шапки .qnt ----
LEASE_BASE = dict(N=1, HORIZON=3000, DURS="Set(1,149)", POLLS="Set(1)", LATS="Set(0)",
                  WAKES="Set(75)", CEIL=0, FAULTS=0, JUMPS="Set()", WALL_CADENCE=b(False),
                  WALL_AGE=b(False), STANDIN=b(True), STEAL=b(False), FOREIGN=b(False),
                  WRITE_FAULT=b(False), INIT_DELAY="Set(1,75)", POLL_MIN=0, INIT_DUE=b(False), UPFLIP_NOT_BEFORE=0,
                  LAST_AT_ANSWER=b(False), SLOT_AT_ANSWER=b(False), REVIVE_FENCED=b(False),
                  REVIVE_OVERSLEPT=b(False), STANDIN_FROM_CONFIRM=b(False))
LEASE_CONST_ORDER = list(LEASE_BASE.keys())


def lease(**over):
    d = dict(LEASE_BASE)
    for k, v in over.items():
        d[k] = v
    return ("p03_lease", d)


STOP_BASE = dict(STOP_TIMEOUT=240, STEP_DUR="Set(1,12)", LAST_RENEW_AGE="Set(0,100)", ORDER_MUT='"none"',
                 STANDIN_REREAD=b(True), STEP_BUDGET=0)
def stop(**over):
    d = dict(STOP_BASE); d.update(over); return ("p03_stop", d)

PERF_BASE = dict(SKEW=0, FSKEW=0, HANG=b(False), TTL=400, STEPS="Set(1,50,100)", FIRST_EPOCH=b(False),
                 NO_BUSY_CHECK=b(False), NO_TAKEOVER_WAIT=b(False), NO_ORDER=b(False), CLOSE_OWN_BEGUN=b(False))
def perf(**over):
    d = dict(PERF_BASE); d.update(over); return ("p03_perform", d)

INSTANCES = {
    "F_ok": ("p03_forms", dict(MUT_FORM='"none"')),
    # --- Аренда: цикл, заместитель ---
    # С5-уточнение: ни один шаг не стоит дольше STALL, но их сумма перекрывает окно
    "L_stepsum": lease(DURS="Set(1,149)"),
    "L_stepsum_ctl": lease(DURS="Set(1,33)", POLLS="Set(1,33)"),
    # Зависший шаг, WAKE на границе допуска (75 тиков = 25/4 с)
    "L_hung": lease(DURS="Set(1,90,1800)", WAKES="Set(75)"),
    "L_hung_ctl_fix": lease(DURS="Set(1,90,1800)", WAKES="Set(75)", STANDIN_FROM_CONFIRM=b(True)),
    # С5: N единиц, ответы медленные, но есть
    "L_slowN": lease(N=4, DURS="Set(1,33)", POLLS="Set(1,33)", LATS="Set(60)", WAKES="Set(75)", INIT_DELAY="Set(75)"),
    "L_slowN_noStandin": lease(N=4, DURS="Set(1,33)", POLLS="Set(1,33)", LATS="Set(60)", STANDIN=b(False)),
    "L_slowN_ctl": lease(N=4, DURS="Set(1,33)", POLLS="Set(1,33)", LATS="Set(12)", INIT_DELAY="Set(75)"),
    # R041: тишина, последовательное чтение: N и ожидание без ответа
    "L_silN": lease(N=2, CEIL=-1, DURS="Set(1,20)", POLLS="Set(1,20)", LATS="Set(60)", FAULTS=1, INIT_DELAY="Set(75)"),
    "L_silN_ctl": lease(N=1, CEIL=-1, DURS="Set(1,20)", POLLS="Set(1,20)", LATS="Set(60)", FAULTS=1, INIT_DELAY="Set(75)"),
    # Потолок: off/конечный при мелких шагах (без эффекта суммы шагов)
    "L_silOff": lease(N=1, CEIL=0, DURS="Set(1,20)", POLLS="Set(1,20)", LATS="Set(0,12)", FAULTS=1, HORIZON=2000),
    "L_silCeil": lease(N=1, CEIL=120, DURS="Set(1,20)", POLLS="Set(1,20)", LATS="Set(0,12)", FAULTS=1, HORIZON=2000),
    "L_recover": lease(N=1, CEIL=-1, DURS="Set(1,20)", POLLS="Set(1,20)", LATS="Set(0,12)", FAULTS=2, UPFLIP_NOT_BEFORE=150),
    # С13: стенные часы
    "L_wallCad": lease(DURS="Set(1,33)", POLLS="Set(1,33)", JUMPS="Set(-360)", WALL_CADENCE=b(True)),
    "L_wallCad_ctl": lease(DURS="Set(1,33)", POLLS="Set(1,33)", JUMPS="Set(-360)"),
    "L_wallAge": lease(DURS="Set(1,1800)", WAKES="Set(12)", JUMPS="Set(-360)", WALL_AGE=b(True), INIT_DELAY="Set(12)"),
    "L_wallAge_ctl": lease(DURS="Set(1,1800)", WAKES="Set(12)", JUMPS="Set(-360)", INIT_DELAY="Set(12)"),
    # С15: шаги аренды при мгновенном отказе хранилища (no_reply: отказ в соединении, store-client:87)
    "L_zeno": lease(DURS="Set(0)", POLLS="Set(0)", LATS="Set(0)", FAULTS=1, STANDIN=b(False), INIT_DELAY="Set(75)", INIT_DUE=b(True)),
    "L_zeno_ctl": lease(DURS="Set(0)", POLLS="Set(1)", LATS="Set(0)", FAULTS=1, STANDIN=b(False), POLL_MIN=1, INIT_DELAY="Set(75)", INIT_DUE=b(True)),
    # Все штатные события (без захвата слота: он кончает шаг)
    "L_any": lease(N=2, DURS="Set(1,20,100,160)", POLLS="Set(1,20)", LATS="Set(0,60)", FAULTS=2, STEAL=b(True),
                   WRITE_FAULT=b(True), CEIL=120),
    "L_small": lease(N=1, DURS="Set(1,100)", POLLS="Set(1)", LATS="Set(0,60)", FAULTS=1, STEAL=b(True), WRITE_FAULT=b(True),
                     CEIL=120, INIT_DELAY="Set(75)"),
    "L_foreign": lease(N=2, DURS="Set(1,20)", POLLS="Set(1)", LATS="Set(0)", FOREIGN=b(True)),
    "L_writefault": lease(N=1, DURS="Set(1,100)", POLLS="Set(1)", LATS="Set(0)", WRITE_FAULT=b(True), STANDIN=b(False)),
    # Мутанты
    "L_m_lastAns": lease(DURS="Set(1,149,300)", LATS="Set(0,60)", STANDIN=b(False), LAST_AT_ANSWER=b(True)),
    "L_m_slotAns": lease(DURS="Set(1,100)", LATS="Set(0,60)", WRITE_FAULT=b(True), STANDIN=b(False), SLOT_AT_ANSWER=b(True)),
    "L_m_fenced": lease(STEAL=b(True), DURS="Set(1,100)", STANDIN=b(False), REVIVE_FENCED=b(True)),
    "L_m_oversleep": lease(DURS="Set(1,149)", STANDIN=b(False), REVIVE_OVERSLEPT=b(True)),
    # --- Остановка ---
    "S_ok": stop(),
    "S_hang": stop(STEP_DUR="Set(1,12,600)"),
    "S_hang50": stop(STOP_TIMEOUT=600, STEP_DUR="Set(1,12,1800)"),
    "S_budget_ctl": stop(STEP_DUR="Set(1,12,600)", STEP_BUDGET=12),
    "S_flush": stop(STOP_TIMEOUT=600, STEP_DUR="Set(1,400)"),
    "S_flush_ctl": stop(STOP_TIMEOUT=240, STEP_DUR="Set(1,12)"),
    "S_age_stuck": stop(LAST_RENEW_AGE="Set(0,100,225)"),
    "S_m_slotfirst": stop(ORDER_MUT='"slot_before_place"'),
    "S_m_standin": stop(ORDER_MUT='"standin_after_release"', STANDIN_REREAD=b(False)),
    "S_standin_reread_ctl": stop(ORDER_MUT='"standin_after_release"', STANDIN_REREAD=b(True)),
    # --- Действия ---
    "P_ok": perf(),
    "P_hang": perf(HANG=b(True)),
    "P_hang_noexpire": perf(HANG=b(True), TTL=10000, STEPS="Set(50,102,500)"),
    "P_skew": perf(SKEW=150),
    "P_fskew": perf(FSKEW=-150),
    "P_m_busy": perf(NO_BUSY_CHECK=b(True)),
    "P_m_wait": perf(NO_TAKEOVER_WAIT=b(True)),
    "P_m_order": perf(NO_ORDER=b(True)),
    "P_m_selfclose": perf(CLOSE_OWN_BEGUN=b(True)),
}

# (id, instance, invariant, kind, tool, max_steps, samples, expect)
RUNS = [
    # ===== p03_forms: трассы форм (20 трасс из *.traces.tsv) и инварианты =====
    ("forms-01-traces", "traces_ok", "traces-all", "control", "test", None, None, "holds"),
    ("forms-02-inv-sim", "F_ok", "FormsInv", "property", "sim", 40, 5000, "holds"),
    ("forms-02b-inv-verify", "F_ok", "FormsInv", "property", "verify", 10, None, "holds"),
    ("forms-w1-cooldown", "F_ok", "W_cooldown", "witness", "sim", 30, 20000, "violated"),
    ("forms-w2-nameless", "F_ok", "W_namelessPublished", "witness", "sim", 20, 5000, "violated"),
    ("forms-m1-since-reset", "traces_since_reset", "traces-all", "mutant", "test", None, None, "violated"),
    ("forms-m2-no-back", "traces_no_back", "traces-all", "mutant", "test", None, None, "violated"),
    ("forms-m3-persist-early", "traces_persist_early", "traces-all", "mutant", "test", None, None, "violated"),
    # ===== p03_lease =====
    ("lease-01-stepsum-sim", "L_stepsum", "NoLost", "property", "sim", 40, 5000, "violated"),
    ("lease-01b-stepsum-verify", "L_stepsum", "NoLost", "property", "verify", 18, None, "violated"),
    ("lease-02-stepsum-ctl-sim", "L_stepsum_ctl", "NoLost", "control", "sim", 60, 5000, "holds"),
    ("lease-02b-stepsum-ctl-verify", "L_stepsum_ctl", "NoLost", "control", "verify", 16, None, "holds"),
    ("lease-03-hung", "L_hung", "NoLost", "property", "sim", 40, 5000, "violated"),
    ("lease-04-hung-fix-ctl", "L_hung_ctl_fix", "NoLost", "control", "sim", 40, 5000, "holds"),
    ("lease-05-slowN", "L_slowN", "NoLost", "property", "sim", 60, 5000, "violated"),
    ("lease-06-slowN-noStandin", "L_slowN_noStandin", "NoLost", "property", "sim", 60, 5000, "violated"),
    ("lease-07-slowN-ctl", "L_slowN_ctl", "NoLost", "control", "sim", 60, 5000, "holds"),
    ("lease-08-silN", "L_silN", "LostOnlyPastCeiling", "property", "sim", 60, 5000, "violated"),
    ("lease-09-silN-ctl", "L_silN_ctl", "LostOnlyPastCeiling", "control", "sim", 60, 5000, "holds"),
    ("lease-10-silOff", "L_silOff", "LostOnlyPastCeiling", "property", "sim", 60, 5000, "holds"),
    ("lease-11-silCeil", "L_silCeil", "LostOnlyPastCeiling", "property", "sim", 60, 5000, "holds"),
    ("lease-12-wallCad", "L_wallCad", "NoLost", "property", "sim", 100, 8000, "violated"),
    ("lease-13-wallCad-ctl", "L_wallCad_ctl", "NoLost", "control", "sim", 100, 5000, "holds"),
    ("lease-14-wallAge", "L_wallAge", "NoLost", "property", "sim", 80, 5000, "violated"),
    ("lease-15-wallAge-ctl", "L_wallAge_ctl", "NoLost", "control", "sim", 80, 5000, "holds"),
    ("lease-16-zeno", "L_zeno", "NoZenoAgain", "property", "verify", 18, None, "violated"),
    ("lease-17-zeno-ctl", "L_zeno_ctl", "StepsBounded", "control", "verify", 18, None, "holds"),
    ("lease-17b-zeno-ctl-sim", "L_zeno_ctl", "StepsBounded", "control", "sim", 200, 2000, "holds"),
    ("lease-20-window", "L_any", "ActWithinWindowFromSend", "property", "sim", 80, 8000, "holds"),
    ("lease-20b-window-verify", "L_small", "ActWithinWindowFromSend", "property", "verify", 12, None, "holds"),
    ("lease-21-slotterm", "L_any", "ActWithinSlotTerm", "property", "sim", 80, 8000, "holds"),
    ("lease-22-fencedstays", "L_any", "FencedStays", "property", "sim", 80, 8000, "holds"),
    ("lease-23-loststays", "L_any", "LostStays", "property", "sim", 80, 8000, "holds"),
    ("lease-24-missedlost", "L_any", "MissedIsLost", "property", "sim", 80, 8000, "holds"),
    ("lease-25-writealg", "L_small", "WriteOnlyInWindowOrCeiling", "property", "verify", 12, None, "holds"),
    ("lease-w1-lost", "L_any", "W_lost", "witness", "sim", 80, 8000, "violated"),
    ("lease-w2-silent", "L_any", "W_silent", "witness", "sim", 80, 8000, "violated"),
    ("lease-w3-recovered", "L_recover", "W_recovered", "witness", "sim", 100, 8000, "violated"),
    ("lease-w4-standin", "L_any", "W_standin", "witness", "sim", 80, 8000, "violated"),
    ("lease-w5-fenced", "L_any", "W_fenced", "witness", "sim", 80, 8000, "violated"),
    ("lease-w6-nobody", "L_foreign", "W_nobody", "witness", "sim", 60, 3000, "violated"),
    ("lease-w7-slotterm", "L_writefault", "W_slot_term_over", "witness", "sim", 100, 8000, "violated"),
    ("lease-w8-silent-ctl-nonvacuous", "L_silCeil", "W_silent", "witness", "sim", 60, 5000, "violated"),
    ("lease-w9-silN-silent", "L_silN", "W_silent", "witness", "sim", 60, 5000, "violated"),
    ("lease-w10-lost-silOff", "L_silOff", "W_lost", "witness", "sim", 80, 8000, "violated"),
    ("lease-w11-lost-silCeil", "L_silCeil", "W_lost", "witness", "sim", 100, 8000, "violated"),
    ("lease-w12-steps-ctl", "L_stepsum_ctl", "W_leaseStep", "witness", "sim", 60, 3000, "violated"),
    ("lease-w13-silent-silN-ctl", "L_silN_ctl", "W_silent", "witness", "sim", 60, 3000, "violated"),
    ("lease-w14-standin-fix", "L_hung_ctl_fix", "W_standin", "witness", "sim", 40, 3000, "violated"),
    ("lease-m1-last-at-answer", "L_m_lastAns", "ActWithinWindowFromSend", "mutant", "sim", 40, 5000, "violated"),
    ("lease-m2-slot-at-answer", "L_m_slotAns", "ActWithinSlotTerm", "mutant", "sim", 100, 8000, "violated"),
    ("lease-m3-revive-fenced", "L_m_fenced", "FencedStays", "mutant", "sim", 40, 5000, "violated"),
    ("lease-m4-revive-oversleep", "L_m_oversleep", "MissedIsLost", "mutant", "sim", 40, 5000, "violated"),
    # ===== p03_stop =====
    ("stop-01-ok-verify", "S_ok", "NoWriteAfterRelease", "property", "verify", 12, None, "holds"),
    ("stop-02-order", "S_ok", "PlaceBeforeSlot", "property", "verify", 12, None, "holds"),
    ("stop-03-standin", "S_ok", "NoStandinWriteAfterRelease", "property", "verify", 12, None, "holds"),
    ("stop-04-done", "S_ok", "DoneReleased", "property", "verify", 12, None, "holds"),
    ("stop-05-hang-killed", "S_hang", "KilledImpliesReleased", "property", "verify", 12, None, "violated"),
    ("stop-06-hang50-killed", "S_hang50", "KilledImpliesReleased", "property", "verify", 12, None, "violated"),
    ("stop-07-budget-ctl", "S_budget_ctl", "KilledImpliesReleased", "control", "verify", 12, None, "holds"),
    ("stop-08-budget-used", "S_budget_ctl", "W_budget_used", "witness", "verify", 12, None, "violated"),
    ("stop-09-flush", "S_flush", "FinalFlushInMayWrite", "property", "verify", 12, None, "violated"),
    ("stop-10-flush-ctl", "S_flush_ctl", "FinalFlushInMayWrite", "control", "verify", 12, None, "holds"),
    ("stop-11-budget-healthy", "S_ok", "PlaceBudgetGuaranteed", "property", "verify", 4, None, "holds"),
    ("stop-12-budget-stuck", "S_age_stuck", "PlaceBudgetGuaranteed", "property", "verify", 4, None, "violated"),
    ("stop-w1-done", "S_ok", "W_done", "witness", "verify", 12, None, "violated"),
    ("stop-w2-killed", "S_hang", "W_killed", "witness", "verify", 12, None, "violated"),
    ("stop-m1-slot-first", "S_m_slotfirst", "NoWriteAfterRelease", "mutant", "verify", 12, None, "violated"),
    ("stop-m1b-slot-first-order", "S_m_slotfirst", "PlaceBeforeSlot", "mutant", "verify", 12, None, "violated"),
    ("stop-m2-standin-noreread", "S_m_standin", "NoStandinWriteAfterRelease", "mutant", "verify", 12, None, "violated"),
    ("stop-c1-standin-reread", "S_standin_reread_ctl", "NoStandinWriteAfterRelease", "control", "verify", 12, None, "holds"),
    # ===== p03_perform =====
    ("perf-01-one-per-group", "P_ok", "OnePerGroupOfHolder", "property", "verify", 12, None, "holds"),
    ("perf-01b-one-per-group-sim", "P_ok", "OnePerGroupOfHolder", "property", "sim", 60, 10000, "holds"),
    ("perf-02-takeover-wait", "P_ok", "TakeoverWaitHonored", "property", "sim", 60, 10000, "holds"),
    ("perf-02b-takeover-wait-verify", "P_ok", "TakeoverWaitHonored", "property", "verify", 12, None, "holds"),
    ("perf-03-order", "P_ok", "OrderInGroup", "property", "sim", 60, 10000, "holds"),
    ("perf-04-noearly-close-0skew", "P_ok", "NoEarlyForeignClose", "control", "sim", 60, 10000, "holds"),
    ("perf-05-early-close-skew", "P_skew", "NoEarlyForeignClose", "property", "sim", 60, 10000, "violated"),
    ("perf-06-noearly-expire-0", "P_ok", "NoEarlyExpire", "control", "sim", 60, 10000, "holds"),
    ("perf-07-early-expire-filer", "P_fskew", "NoEarlyExpire", "property", "sim", 60, 10000, "violated"),
    ("perf-08-noself-close", "P_ok", "NoSelfForeignClose", "property", "sim", 60, 10000, "holds"),
    ("perf-09-hung-blocks", "P_hang_noexpire", "HungDoesNotBlockForever", "property", "sim", 60, 10000, "violated"),
    ("perf-w1-overlap", "P_ok", "W_overlap", "witness", "sim", 60, 20000, "violated"),
    ("perf-w2-late", "P_ok", "W_late", "witness", "sim", 60, 20000, "violated"),
    ("perf-w3-second-expired-during-hang", "P_hang", "W_secondExpiredDuringHang", "witness", "sim", 60, 20000, "violated"),
    ("perf-w4-begun", "P_ok", "W_begun", "witness", "sim", 30, 2000, "violated"),
    ("perf-w5-unknown", "P_ok", "W_unknown", "witness", "sim", 60, 10000, "violated"),
    ("perf-w6-performed", "P_ok", "W_performed", "witness", "sim", 30, 2000, "violated"),
    ("perf-w7-taken", "P_ok", "W_taken", "witness", "sim", 10, 500, "violated"),
    ("perf-w8-foreign-close", "P_ok", "W_foreignClose", "witness", "sim", 60, 20000, "violated"),
    ("perf-w9-expired", "P_ok", "W_expired", "witness", "sim", 60, 10000, "violated"),
    ("perf-m1-no-busy", "P_m_busy", "OnePerGroupOfHolder", "mutant", "sim", 40, 5000, "violated"),
    ("perf-m2-no-wait", "P_m_wait", "TakeoverWaitHonored", "mutant", "sim", 60, 10000, "violated"),
    ("perf-m3-order", "P_m_order", "OrderInGroup", "mutant", "sim", 40, 5000, "violated"),
    ("perf-m4-self-close", "P_m_selfclose", "NoSelfForeignClose", "mutant", "sim", 60, 10000, "violated"),
]


def inst_file(name):
    return os.path.join("inst", name + ".qnt")


def write_instances():
    os.makedirs(os.path.join(HERE, "inst"), exist_ok=True)
    for name, (mod, conf) in INSTANCES.items():
        params = ", ".join(f"{k}={v}" for k, v in conf.items())
        src = (f"// Сформировано run.py: экземпляр {name}. Не редактировать вручную.\n"
               f"module {name} {{\n  import {mod}({params}).* from \"../{mod}\"\n}}\n")
        with open(os.path.join(HERE, inst_file(name)), "w", encoding="utf-8") as f:
            f.write(src)


def run_one(r):
    rid, inst, inv, kind, tool, steps, samples, expect = r
    out_file = os.path.join("runs", rid + ".out")
    cmd = ["quint"]
    infile = inst_file(inst)
    if tool == "test":
        cmd += ["test", f"--main={inst}", "--max-samples=1", "--match=^t_", inst + ".qnt"]
    elif tool == "sim":
        cmd += ["run", "--backend=rust", f"--main={inst}", f"--max-samples={samples}",
                f"--max-steps={steps}", f"--invariant={inv}", infile]
    else:
        cmd += ["verify", f"--main={inst}", f"--max-steps={steps}", f"--invariant={inv}",
                f"--server-endpoint=localhost:{PORT}", infile]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=HERE, env=ENV, capture_output=True, text=True, timeout=900)
        out = p.stdout + p.stderr
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() + (e.stderr or b"").decode() + "\nTIMEOUT"
        rc = 124
    secs = round(time.time() - t0, 1)
    with open(os.path.join(HERE, out_file), "w", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\nexit {rc}\n\n{out}")
    if tool == "test":
        passing = re.search(r"(\d+) passing", out)
        failing = re.search(r"(\d+) failing", out)
        if failing or (rc != 0 and passing):
            actual = "violated"
        elif rc == 0 and passing:
            actual = "holds"
        else:
            actual = "error"
    elif re.search(r"\[violation\]|Found an issue", out):
        actual = "violated"
    elif re.search(r"\[ok\]|No violation found", out) and rc == 0:
        actual = "holds"
    elif rc == 124:
        actual = "timeout"
    else:
        actual = "error"
    match = "yes" if actual == expect else "no"
    if tool == "test":
        overrides = "MUT_FORM=" + inst[len("traces_"):]
    else:
        conf = INSTANCES[inst][1]
        base = {"p03_lease": LEASE_BASE, "p03_stop": STOP_BASE, "p03_perform": PERF_BASE, "p03_forms": {}}[INSTANCES[inst][0]]
        interesting = {k: v for k, v in conf.items() if v != base.get(k)}
        overrides = ";".join(f"{k}={v}" for k, v in interesting.items())
    row = dict(id=rid, module=inst, invariant=inv, kind=kind, tool={"verify": "quint-verify", "sim": "quint-run-rust", "test": "quint-test"}[tool],
               max_steps=steps if steps else "", samples=samples if samples else "", overrides=overrides,
               expect=expect, actual=actual, match=match, secs=secs, file=out_file)
    return row


def load_results():
    path = os.path.join(HERE, "results.tsv")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f, delimiter="\t")}


def save_results(res):
    with open(os.path.join(HERE, "results.tsv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, OUT_COLS, delimiter="\t")
        w.writeheader()
        for r in RUNS:
            if r[0] in res:
                w.writerow(res[r[0]])


def main():
    write_instances()
    prefixes = sys.argv[1:]
    res = load_results()
    with open(os.path.join(HERE, "run.log"), "a", encoding="utf-8") as log:
        for r in RUNS:
            if prefixes and not any(r[0].startswith(p) for p in prefixes):
                continue
            if os.path.exists(HOLD):
                msg = f"HOLD: {r[0]} не запускается"
                print(msg)
                log.write(msg + "\n")
                sys.exit(3)
            row = run_one(r)
            res[r[0]] = row
            save_results(res)
            line = f"{time.strftime('%H:%M:%S')} {r[0]} {row['kind']} {row['tool']} expect={row['expect']} actual={row['actual']} match={row['match']} {row['secs']}s"
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()


if __name__ == "__main__":
    main()
