#!/usr/bin/env python3
"""Запуск серии проверок модели P/04 (Quint/Apalache). Правки только внутри этого каталога.

Использование: run.py [--only <подстрока>] [--dry] [--batch N]
Пишет results.tsv, run.log, runs/<id>.out. Проверяет HOLD-файл перед каждым запуском.
Прогоны идут последовательно: одновременно не более одного процесса Apalache.
"""
import argparse, csv, os, pathlib, re, shutil, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
SCRATCH = pathlib.Path("/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p04q")
HOLD = SCRATCH / "HOLD"
WORK = SCRATCH / "work"
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk", PATH="/opt/quint/jdk/bin:" + os.environ.get("PATH", ""))
PORT = 8861
RESULTS = HERE / "results.tsv"
LOG = HERE / "run.log"
RUNS = HERE / "runs"
FILES = {"p04_clock_delete.qnt": [], "p04_pass_watchdog.qnt": [], "p04_turn_race.qnt": [], "p04_slot_fate.qnt": ["p04_forms.qnt"]}

# Спецификации запусков: id, файл, main (инстанс), инвариант, kind, tool, шаги, samples, overrides, expect(pass|violation)
PLAN = []
def add(id, f, main, inv, kind, tool, steps, samples, overrides, expect):
    PLAN.append(dict(id=id, file=f, main=main, invariant=inv, kind=kind, tool=tool, steps=steps, samples=samples, overrides=overrides, expect=expect))

CK = "p04_clock_delete.qnt"
add("clk-01", CK, "clk_premise", "invEndsBound", "property", "verify", 10, 0, "ctrl<=60,leader=0", "pass")
add("clk-02", CK, "clk_premise", "invMadeBound", "property", "verify", 10, 0, "ctrl<=60,leader=0", "pass")
add("clk-03", CK, "clk_premise", "invManualNotDeleted", "property", "verify", 10, 0, "ctrl<=60,leader=0", "pass")
add("clk-04", CK, "clk_premise", "invDaNotEarly", "property", "verify", 10, 0, "ctrl<=60,leader=0,da=mono", "pass")
add("clk-05", CK, "clk_jump", "invEndsBound", "property", "verify", 6, 0, "ctrl unbounded,leader=0; Б1", "violation")
add("clk-06", CK, "clk_jump", "invMadeBound", "property", "verify", 10, 0, "ctrl unbounded,leader=0; строка с made", "pass")
add("clk-07", CK, "clk_jump", "invDaNotEarly", "property", "verify", 10, 0, "ctrl unbounded,leader=0,da=mono", "pass")
add("clk-08", CK, "clk_jump_fix", "invEndsBound", "control", "verify", 10, 0, "предложение Б1: not_before=ends-60, ctrl unbounded, leader=0", "pass")
add("clk-09", CK, "clk_jump_fix_leader", "invEndsBound", "control", "verify", 8, 0, "предложение Б1, leader unbounded (тот же сервер/снимок ВМ)", "violation")
add("clk-10", CK, "clk_jump_leader", "invMadeStrict", "property", "verify", 8, 0, "ctrl unbounded,leader unbounded; точная граница keep-60", "violation")
add("clk-11", CK, "clk_premise_leader", "invEndsBound", "control", "verify", 10, 0, "ctrl<=60,leader<=60", "pass")
add("clk-12", CK, "clk_premise_leader", "invMadeBound", "property", "verify", 10, 0, "ctrl<=60,leader<=60", "pass")
add("clk-13", CK, "clk_mut_no_nb", "invMadeBound", "mutant", "verify", 8, 0, "мутант: без not_before; ctrl unbounded", "violation")
add("clk-14", CK, "clk_mut_manual", "invManualNotDeleted", "mutant", "verify", 8, 0, "мутант: ручная строка удаляется", "violation")
add("clk-15", CK, "clk_jump_da_wall", "invDaNotEarly", "mutant", "verify", 8, 0, "чтение М1: delete_after по стенным часам", "violation")
add("clk-w1", CK, "clk_premise", "witEndsDeleted", "witness", "verify", 8, 0, "", "violation")
add("clk-w2", CK, "clk_premise", "witMadeDeleted", "witness", "verify", 8, 0, "", "violation")
add("clk-w3", CK, "clk_premise", "witDaDeleted", "witness", "verify", 10, 0, "", "violation")
add("clk-w4", CK, "clk_premise", "witManualKept", "witness", "verify", 6, 0, "", "violation")
add("clk-w5", CK, "clk_premise", "witDaAfterRestart", "witness", "verify", 10, 0, "перезапуск, отсчёт заново", "violation")
add("clk-w7", CK, "clk_jump", "witMadeDeleted", "witness", "verify", 10, 0, "невакуумность clk-06", "violation")
add("clk-w8", CK, "clk_jump", "witDaDeleted", "witness", "verify", 10, 0, "невакуумность clk-07", "violation")
add("clk-w9", CK, "clk_jump_fix", "witEndsDeleted", "witness", "verify", 10, 0, "невакуумность clk-08", "violation")
add("clk-w10", CK, "clk_premise_leader", "witEndsDeleted", "witness", "verify", 10, 0, "невакуумность clk-11", "violation")
add("clk-w6", CK, "clk_jump_leader", "witLeaderSkew", "witness", "verify", 4, 0, "", "violation")

WD = "p04_pass_watchdog.qnt"
add("wd-01", WD, "wd_norm", "invNoKill", "property", "verify", 8, 0, "норма без бюджета; opCost 1..400", "violation")
add("wd-02", WD, "wd_norm", "invNoKillIfOpFits", "property", "verify", 10, 0, "сумма операций, не одна операция > WD", "violation")
add("wd-03", WD, "wd_norm", "invCompletedPassWithinWd", "property", "verify", 16, 0, "завершённый проход всегда <= WD: граница фактически сторожевая", "pass")
add("wd-04", WD, "wd_norm", "invIdleAfterPassReleased", "property", "verify", 16, 0, "после завершающего действия ход сдан", "pass")
add("wd-05", WD, "wd_budget", "invNoKill", "control", "verify", 12, 0, "предложение С1: бюджет B*c+2c<=WD", "pass")
add("wd-06", WD, "wd_notify_each", "invNoKillIfOpFits", "control", "verify", 14, 0, "WATCHDOG=1 на каждое решение", "pass")
add("wd-w1", WD, "wd_norm", "witCompletion", "witness", "verify", 6, 0, "завершённый проход достижим", "violation")
add("wd-w2", WD, "wd_norm", "witKilled", "witness", "verify", 8, 0, "убийство сторожем достижимо", "violation")
add("wd-w3", WD, "wd_norm", "witTwoKillsNoReport", "witness", "verify", 14, 0, "2 убийства, 0 финальных отчётов", "violation")
add("wd-w4", WD, "wd_norm", "witTwoKillsNoJudgement", "witness", "verify", 16, 0, "2 убийства, неживой судьбы нет", "violation")
add("wd-w5", WD, "wd_norm", "witNonAlive", "witness", "verify", 12, 0, "неживая судьба достижима без убийства", "violation")
add("wd-w6", WD, "wd_norm", "witBusyAfterKill", "witness", "verify", 12, 0, "ход занят после убийства", "violation")
add("wd-w8", WD, "wd_budget", "witCompletion", "witness", "verify", 8, 0, "невакуумность wd-05", "violation")
add("wd-w9", WD, "wd_notify_each", "witCompletion", "witness", "verify", 8, 0, "невакуумность wd-06", "violation")
add("wd-w7", WD, "wd_notify_each", "witLongPassNoKill", "witness", "verify", 14, 0, "проход длиннее WD без убийства при notify на решение", "violation")

SF = "p04_slot_fate.qnt"
add("fate-01", SF, "fate_notorn", "invTrueAgeBelowTermAlive", "property", "verify", 10, 0, "без torn", "pass")
add("fate-02", SF, "fate_notorn", "invConflictThenAlive", "property", "verify", 10, 0, "без torn", "pass")
add("fate-03", SF, "fate_notorn", "invNoReleaseOverwrite", "property", "verify", 10, 0, "без torn", "pass")
add("fate-04", SF, "fate_notorn", "invFreshMovesNothing", "property", "verify", 10, 0, "читаемые строки", "pass")
add("fate-05", SF, "fate_base", "invFreshMovesNothing", "property", "verify", 8, 0, "с torn: уточнение текста N:324", "violation")
add("fate-06", SF, "fate_base", "witTornMoveAtZero", "witness", "verify", 6, 0, "torn и gone при первом взгляде", "violation")
add("fate-m1", SF, "fate_nocas", "invNoReleaseOverwrite", "mutant", "verify", 10, 0, "мутант: release без cas", "violation")
add("fate-m2", SF, "fate_noreset", "invConflictThenAlive", "mutant", "verify", 10, 0, "мутант: новая версия не сбрасывает age", "violation")
add("fate-m3", SF, "fate_until", "invTrueAgeBelowTermAlive", "mutant", "verify", 8, 0, "мутант: возраст из until пишущего", "violation")
for n in range(1, 17):
    add(f"fate-w{n}", SF, "fate_base", f"witR{n}", "witness", "sim", 30, 200000, "строка формы slot-fate", "violation")
add("fate-w20", SF, "fate_base", "witRel2", "witness", "verify", 12, 0, "slot-release: conflict", "violation")
add("fate-w21", SF, "fate_base", "witRel5", "witness", "verify", 10, 0, "slot-release: ok", "violation")
add("fate-w22", SF, "fate_base", "witConflict", "witness", "verify", 12, 0, "", "violation")
add("fate-w23", SF, "fate_base", "witReleased", "witness", "verify", 10, 0, "", "violation")
add("fate-w25", SF, "fate_notorn", "witReleased", "witness", "verify", 10, 0, "невакуумность fate-03", "violation")
add("fate-w26", SF, "fate_notorn", "witR3", "witness", "sim", 30, 200000, "невакуумность fate-04", "violation")
add("fate-w24", SF, "fate_base", "witGrantAfterRelease", "witness", "verify", 10, 0, "", "violation")

TR = "p04_turn_race.qnt"
add("turn-01", TR, "turn_base", "invCapacity", "property", "verify", 7, 0, "2 контроллера, 2 ед., 2 рабочих; глубина мала: см. отчёт", "pass")
add("turn-02", TR, "turn_base", "invOneAssign", "property", "verify", 7, 0, "", "pass")
add("turn-03", TR, "turn_base", "invIdleConsistent", "property", "verify", 7, 0, "", "pass")
add("turn-04", TR, "turn_base", "invNoStaleApplied", "property", "verify", 7, 0, "", "pass")
add("turn-f1", TR, "turn_base_focus", "invCapacity", "property", "verify", 10, 0, "фокус без шума: подмножество поведений; глубже Apalache", "pass")
add("turn-f2", TR, "turn_base_focus", "invOneAssign", "property", "verify", 10, 0, "фокус", "pass")
add("turn-f3", TR, "turn_base_focus", "invIdleConsistent", "property", "verify", 10, 0, "фокус", "pass")
add("turn-s1", TR, "turn_base", "invCapacity", "property", "sim", 40, 300000, "симуляция", "pass")
add("turn-s2", TR, "turn_base", "invOneAssign", "property", "sim", 40, 300000, "симуляция", "pass")
add("turn-s3", TR, "turn_base", "invIdleConsistent", "property", "sim", 40, 300000, "симуляция", "pass")
add("turn-s4", TR, "turn_base", "invNoNewWhileActive", "property", "sim", 40, 300000, "симуляция", "pass")
add("turn-s5", TR, "turn_base", "invNoStaleApplied", "property", "sim", 40, 300000, "симуляция", "pass")
add("turn-s6", TR, "turn_base", "invNoEarlyCapture", "property", "sim", 40, 300000, "симуляция", "pass")
add("turn-s7", TR, "turn_sigterm_release", "invCapacity", "control", "sim", 40, 300000, "SIGTERM сдаёт ход (С4), симуляция", "pass")
add("turn-s8", TR, "turn_sigterm_release", "invIdleConsistent", "control", "sim", 40, 300000, "SIGTERM сдаёт ход (С4), симуляция", "pass")
add("turn-w1", TR, "turn_base", "witTakeoverActive", "witness", "sim", 40, 200000, "захват чужого активного intent", "violation")
add("turn-w2", TR, "turn_base", "witStaleRefused", "witness", "sim", 40, 200000, "опоздавшая запись 412", "violation")
add("turn-w3", TR, "turn_base", "witBothPlaced", "witness", "sim", 40, 200000, "", "violation")
add("turn-w4", TR, "turn_base", "witCommitWithRecover", "witness", "sim", 40, 200000, "", "violation")
add("turn-w5", TR, "turn_base", "witGone", "witness", "sim", 40, 100000, "SIGTERM достижим", "violation")
add("turn-w6", TR, "turn_base", "witTwoCaptures", "witness", "sim", 40, 100000, "", "violation")
add("turn-w7", TR, "turn_sigterm_release", "witTwoCaptures", "witness", "sim", 40, 100000, "", "violation")
add("turn-m1", TR, "turn_noguard", "invNoStaleApplied", "mutant", "sim", 40, 200000, "мутант: запись без guard", "violation")
add("turn-m2", TR, "turn_noguard", "invIdleConsistent", "mutant", "sim", 40, 1000000, "мутант: запись без guard", "violation")
add("turn-m3", TR, "turn_nofresh_focus", "invCapacity", "mutant", "sim", 45, 300000, "мутант: решение по старому снимку (фокус)", "violation")
add("turn-m4", TR, "turn_skipintent", "invNoNewWhileActive", "mutant", "sim", 40, 200000, "мутант: новое решение при активном intent", "violation")
add("turn-m5", TR, "turn_skipintent", "invIdleConsistent", "mutant", "sim", 40, 1000000, "мутант", "violation")
add("turn-m6", TR, "turn_addfirst_focus", "invOneAssign", "mutant", "sim", 45, 300000, "мутант: добавление без снятия (фокус)", "violation")
add("turn-m7", TR, "turn_nobump", "invNoLateApplied", "mutant", "sim", 40, 1000000, "мутант: барьер без смены версии, опоздавшая запись применена после барьера (T:83)", "violation")
add("turn-s9", TR, "turn_base", "invNoLateApplied", "property", "sim", 40, 300000, "T:83: после барьера опоздавшая запись не применяется", "pass")
add("turn-m8", TR, "turn_noage", "invNoEarlyCapture", "mutant", "sim", 30, 100000, "мутант: захват чужого раньше TURN_TERM", "violation")
add("turn-w9", TR, "turn_base", "witLatePending", "witness", "sim", 40, 200000, "барьер при записи в пути", "violation")
add("turn-w8", TR, "turn_sigterm_release", "witFastAfterSigterm", "witness", "sim", 40, 100000, "SIGTERM со сдачей: захват без ожидания TURN_TERM", "violation")
add("turn-c1", TR, "turn_noage", "invCapacity", "control", "sim", 40, 1000000, "захват без возраста: безопасность размещения держится на guard", "pass")
add("turn-c2", TR, "turn_noage", "invIdleConsistent", "control", "sim", 40, 1000000, "то же", "pass")


def single_instance(src: pathlib.Path, main: str) -> str:
    text = src.read_text(encoding="utf8")
    out = []
    for line in text.splitlines():
        if re.match(r"module \w+ \{ import ", line) and not line.startswith(f"module {main} "):
            continue
        out.append(line)
    # многострочные инстансы (clk_*)
    joined = "\n".join(out)
    def drop(m):
        return m.group(0) if m.group(1) == main else ""
    joined = re.sub(r"^module (\w+) \{\n(?:  //[^\n]*\n)?  import [^\n]*\n\}\n", drop, joined, flags=re.M)
    return joined + "\n"


def run_one(r, seen_ids):
    if HOLD.exists():
        print("HOLD: остановка новых запусков", flush=True)
        return "held", None, 0.0
    WORK.mkdir(parents=True, exist_ok=True)
    rdir = WORK / r["id"]
    rdir.mkdir(parents=True, exist_ok=True)
    src = HERE / r["file"]
    tmp = rdir / r["file"]
    tmp.write_text(single_instance(src, r["main"]), encoding="utf8")
    for dep in FILES[r["file"]]:
        shutil.copy(HERE / dep, rdir / dep)
    if r["tool"] == "verify":
        cmd = ["quint", "verify", f"--main={r['main']}", f"--invariant={r['invariant']}", f"--max-steps={r['steps']}", f"--server-endpoint=localhost:{PORT}", r["file"]]
        timeout = 420
    else:
        cmd = ["quint", "run", "--backend=rust", f"--main={r['main']}", f"--invariant={r['invariant']}", f"--max-steps={r['steps']}", f"--max-samples={r['samples']}", r["file"]]
        timeout = 600
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=rdir, env=ENV, capture_output=True, text=True, timeout=timeout)
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout.decode() if e.stdout else "") + "\nTIMEOUT\n"
    secs = time.time() - t0
    actual = "unknown"
    if "[ok] No violation" in out:
        actual = "pass"
    elif "[violation]" in out or "Invariant violated" in out or "found a counterexample" in out:
        actual = "violation"
    elif "TIMEOUT" in out:
        actual = "timeout"
    # журнал вывода (обрезаем: отчётный след, не архив)
    (RUNS / f"{r['id']}.out").write_text(out[-40000:], encoding="utf8")
    return actual, out, secs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    plan = [r for r in PLAN if (args.only is None or args.only in r["id"])]
    if args.dry:
        for r in plan:
            print(r)
        print(len(plan))
        return
    RUNS.mkdir(exist_ok=True)
    results = {}
    if RESULTS.exists():
        with open(RESULTS, newline="", encoding="utf8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                results[row["id"]] = row
    log = open(LOG, "a", encoding="utf8")
    for r in plan:
        actual, out, secs = run_one(r, results)
        if actual == "held":
            log.write(f"HOLD before {r['id']}\n")
            break
        match = "1" if actual == r["expect"] else "0"
        row = dict(id=r["id"], module=r["main"], invariant=r["invariant"], kind=r["kind"], tool=r["tool"], max_steps=r["steps"], samples=r["samples"], overrides=r["overrides"], expect=r["expect"], actual=actual, match=match, secs=f"{secs:.1f}", file=r["file"])
        results[r["id"]] = row
        line = "\t".join(str(row[k]) for k in ["id", "module", "invariant", "kind", "tool", "max_steps", "samples", "overrides", "expect", "actual", "match", "secs", "file"])
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)
        # записываем результаты после каждого прогона
        with open(RESULTS, "w", newline="", encoding="utf8") as f:
            cols = ["id", "module", "invariant", "kind", "tool", "max_steps", "samples", "overrides", "expect", "actual", "match", "secs", "file"]
            w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n")
            w.writeheader()
            order = [p["id"] for p in PLAN if p["id"] in results]
            for k in order:
                w.writerow({c: results[k][c] for c in cols})
    log.close()
    print("done", len(results))


if __name__ == "__main__":
    main()
