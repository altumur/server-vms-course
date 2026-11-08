#!/usr/bin/env python3
"""Прогон модели Quint P/01 пп. 9-14 на срезе 244355d1. Запуск: python3 run.py [--only PAT] [--anchors]
Мутанты и варианты конфигурации - подстановка `pure val NAME = ...` во временной копии .qnt в scratchpad.
Два своих сервера Apalache (порты 8931, 8932), Xmx 4g; чужие процессы java не используются."""
import concurrent.futures as cf, hashlib, os, pathlib, re, subprocess, sys, threading, time

HERE = pathlib.Path(__file__).resolve().parent
PIN = "244355d161139bd6fe65fd68c7e5134598c21ba3"
SP = pathlib.Path(os.environ.get("SCRATCH", "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p01q"))
HOLD = SP / "HOLD"
WORK = SP / "work"
RUNS = HERE / "runs"
PORTS = [8931, 8932]
TIMEOUT_V = 1200
TIMEOUT_S = 300
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk", PATH="/opt/quint/jdk/bin:" + os.environ.get("PATH", ""))

def R(module, invariant, kind, expect, steps=10, tool="verify", over=None, name=None, samples=20000):
    return dict(module=module, invariant=invariant, kind=kind, expect=expect, steps=steps, tool=tool,
                over=over or {}, name=name, samples=samples)

P, W, M, C = "property", "witness", "mutant", "control"
RS = []
def prop(mod, invs, steps=10, simsteps=30, simsamples=20000, over=None):
    for i in invs:
        RS.append(R(mod, i, P, "hold", steps, "verify", over))
        RS.append(R(mod, i, P, "hold", simsteps, "sim", over, samples=simsamples))

# ---- admission ----
A = "admission"
prop(A, ["inv_admNonDec", "inv_metaLast", "inv_noBusiness", "inv_oneOkPerId", "inv_idMatchesOk",
         "inv_idOccupied", "inv_expiredSticky", "inv_catchUp", "inv_sameOutcome", "inv_r071", "inv_order"], steps=10)
for w in ["not_w_futureExpired", "not_w_expiredHolds", "not_w_leaderLower", "not_w_snapContinue", "not_w_refusalRaises", "not_w_againLate"]:
    RS.append(R(A, w, W, "violated", 9))
SYNC = {"ALLOW_SKEW": "false", "ALLOW_JUMP": "false", "ALLOW_LEADER_CHANGE": "false"}
RS.append(R(A, "not_w_futureExpired", C, "hold", 9, over=SYNC, name="sync"))
RS.append(R(A, "not_w_expiredHolds", C, "hold", 9, over=SYNC, name="sync"))
RS.append(R(A, "not_w_leaderLower", C, "hold", 9, over=SYNC, name="sync"))
RS.append(R(A, "inv_admNonDec", C, "hold", 9, over={**SYNC, "MUT_NO_MAX": "true"}, name="sync_nomax"))  # мутант ловится только через несинхронные часы
for m, inv in [("MUT_NO_MAX", "inv_admNonDec"), ("MUT_REFUSE_ROLLBACK", "inv_metaLast"), ("MUT_SNAP_NO_ADM", "inv_admNonDec"),
               ("MUT_APPLY_OWN_CLOCK", "inv_sameOutcome"), ("MUT_EXPIRED_TAKES_ID", "inv_idMatchesOk"),
               ("MUT_AGAIN_NEW_VERSION", "inv_noBusiness"), ("MUT_CAS_BEFORE_TIME", "inv_order")]:
    RS.append(R(A, inv, M, "violated", 9, over={m: "true"}, name=m))

AW = "admission_wit"
for w in ["not_w_r071Ante", "not_w_stickyAnte", "not_w_catchUpAnte", "not_w_idAnte"]:
    RS.append(R(AW, w, W, "violated", 9))

# ---- import_group ----
G = "import_group"
prop(G, ["inv_noWriterBeforeDone", "inv_doneComplete", "inv_floorFirst", "inv_floorStableInAttempt"], steps=12, simsteps=40)
for w in ["not_w_stuck", "not_w_refusedAfterDone", "not_w_resumeAfterLeaderLoss", "not_w_allDownUnfinished"]:
    RS.append(R(G, w, W, "violated", 12))
BOXO = {"READING_BOX_ONLY": "true"}
RS.append(R(G, "not_w_stuck", C, "hold", 12, over=BOXO, name="reading_box_only"))
RS.append(R(G, "not_w_refusedAfterDone", C, "hold", 12, over=BOXO, name="reading_box_only"))
BOXM = {"BOX": "true", "NODES": 'Set("a")'}
RS.append(R(G, "not_w_stuck", C, "hold", 12, over=BOXM, name="box_single"))
RS.append(R(G, "inv_noWriterBeforeDone", C, "hold", 12, over=BOXM, name="box_single"))
REB = {"ALLOW_REBUILD_GROUP": "true"}
RS.append(R(G, "not_w_resumeAfterFullOutage", W, "violated", 12, over=REB, name="assume_rebuild"))
RS.append(R(G, "not_w_sameGen", W, "violated", 12, over=REB, name="assume_rebuild"))
RS.append(R(G, "not_w_doneAfterOutage", C, "hold", 14, name="literal"))
RS.append(R(G, "not_w_doneAfterOutage", W, "violated", 14, over=BOXO, name="reading_box_only"))
RS.append(R(G, "not_w_doneAfterOutage", W, "violated", 14, over=REB, name="assume_rebuild"))
RS.append(R(G, "not_w_doneAfterOutage", C, "hold", 40, "sim", name="literal", samples=50000))
for m, inv in [("MUT_NO_HOLD", "inv_noWriterBeforeDone"), ("MUT_DONE_EARLY", "inv_doneComplete"), ("MUT_REPLAY_NEW_FLOOR", "inv_floorStableInAttempt")]:
    RS.append(R(G, inv, M, "violated", 12, over={m: "true"}, name=m))

# ---- recover ----
Y = "recover"
prop(Y, ["inv_floorGrows", "inv_completeConsistent"], steps=10)
for w in ["not_w_startOnPartialDump", "not_w_dumpNewWalOld", "not_w_floorOnlyRaised", "not_w_startOnOldWithFloor", "not_w_retryNewGen"]:
    RS.append(R(Y, w, W, "violated", 10))
RS.append(R(Y, "inv_noStartOnPartial_control", C, "hold", 10, over={"ATOMIC_PUBLISH": "true", "REFUSE_ON_PARTIAL": "true"}, name="atomic+refuse"))
RS.append(R(Y, "inv_noStartOnPartial_control", C, "hold", 10, over={"REFUSE_ON_PARTIAL": "true"}, name="refuse_only"))
RS.append(R(Y, "inv_noStartOnPartial_control", C, "violated", 10, over={"ATOMIC_PUBLISH": "true"}, name="atomic_only"))
RS.append(R(Y, "inv_noStartOnPartial_control", C, "violated", 10, name="baseline"))
for m, inv in [("MUT_FLOOR_DOWN", "inv_floorGrows"), ("MUT_COMPLETE_EARLY", "inv_completeConsistent")]:
    RS.append(R(Y, inv, M, "violated", 10, over={m: "true"}, name=m))

# ---- id_memory ----
I = "id_memory"
prop(I, ["inv_forgetBoth", "inv_strictAge", "inv_oneVersionPerLife", "inv_againSameAnswer"], steps=12)
MONO = {"AGE_BASE": '"mono"'}
RS.append(R(I, "inv_forgetBoth", P, "hold", 12, over=MONO, name="base_mono"))
RS.append(R(I, "not_w_ageMetByJump", W, "violated", 12, name="base_wall"))
RS.append(R(I, "not_w_ageMetByJump", C, "hold", 12, over=MONO, name="base_mono"))
RS.append(R(I, "not_w_forgottenNewWrite", W, "violated", 12))
RS.append(R(I, "not_w_earlyReforget", W, "violated", 12, name="base_wall"))
RS.append(R(I, "not_w_earlyReforget", C, "hold", 12, over=MONO, name="base_mono"))
RS.append(R(I, "not_w_ambiguousRetry", W, "violated", 12))
for m, inv in [("MUT_AGE_ONLY", "inv_forgetBoth"), ("MUT_RECORDS_ONLY", "inv_forgetBoth"), ("MUT_FORGET_ANY", "inv_forgetBoth"),
               ("MUT_EQ_AGE", "inv_strictAge"), ("MUT_REPLAY_NEW_VER", "inv_oneVersionPerLife")]:
    RS.append(R(I, inv, M, "violated", 12, over={m: "true"}, name=m))

# ---- stop ----
S = "stop"
prop(S, ["inv_noAdmitAfterStop", "inv_copyNoLock", "inv_exitClean", "inv_workClassified", "inv_pinsMatchCopy", "inv_rank"], steps=10, simsteps=30)
for w in ["not_w_stopNoCopy", "not_w_stop503", "not_w_stopReset", "not_w_stalledCancel", "not_w_ambiguousAtStop"]:
    RS.append(R(S, w, W, "violated", 12))
for m, inv in [("MUT_ADMIT_AFTER_STOP", "inv_noAdmitAfterStop"), ("MUT_COPY_HOLDS_LOCK", "inv_copyNoLock"),
               ("MUT_EXIT_WITH_INFLIGHT", "inv_exitClean"), ("MUT_LEAK_PIN_ON_CANCEL", "inv_pinsMatchCopy"), ("MUT_DROP_ADMITTED", "inv_workClassified")]:
    RS.append(R(S, inv, M, "violated", 12, over={m: "true"}, name=m))

# ---- door ----
D = "door"
prop(D, ["inv_idAtMostOne", "inv_unavailableNotApplied", "inv_voter503NotApplied", "inv_ambigWindow"], steps=12, simsteps=30)
for w in ["not_w_ambigNotForwarded", "not_w_noIdDouble", "not_w_allVotersDown503", "not_w_voter503", "not_w_reachedAmbig"]:
    RS.append(R(D, w, W, "violated", 12))
RS.append(R(D, "not_w_ambigNotForwarded", C, "hold", 12, over={"T_ATTEMPT": "3", "LEADER_WAIT": "3"}, name="T=L"))
RS.append(R(D, "not_w_ambigNotForwarded", C, "hold", 12, over={"T_ATTEMPT": "3", "LEADER_WAIT": "2"}, name="T>L"))
RS.append(R(D, "not_w_noIdDouble", C, "hold", 12, over={"ALLOW_NO_ID": "false"}, name="only_id"))
RS.append(R(D, "inv_idAtMostOne", M, "violated", 12, over={"MUT_DOUBLE_APPLY_WITH_ID": "true"}, name="MUT_DOUBLE_APPLY_WITH_ID"))
RS.append(R(D, "not_w_ambigNotForwarded", M, "violated", 12, over={"T_ATTEMPT": "3", "LEADER_WAIT": "3", "MUT_VOTER_NEVER_ANSWERS": "true"}, name="MUT_VOTER_NEVER_ANSWERS"))

def runid(r):
    parts = [r["module"], r["invariant"], r["tool"]]
    if r["name"]: parts.insert(2, r["name"])
    return "__".join(parts)

lock = threading.Lock()
results = []
log_fh = None
def logw(msg):
    line = f"{time.strftime('%H:%M:%SZ', time.gmtime())} {msg}"
    with lock:
        print(line, flush=True)
        log_fh.write(line + "\n"); log_fh.flush()

def patched_source(r):
    src = (HERE / f"{r['module']}.qnt").read_text(encoding="utf8")
    for name, val in r["over"].items():
        src2, n = re.subn(rf"^(\s*pure val {re.escape(name)} = )[^/\n]*", lambda m: m.group(1) + val + "  ", src, flags=re.M)
        if n != 1: raise SystemExit(f"override {name} for {r['module']} matched {n} times")
        src = src2
    return src

def run_one(r, port):
    rid = runid(r)
    if HOLD.exists():
        res = dict(r, id=rid, actual="not_run_HOLD", secs=0, file="", detail="HOLD")
        logw(f"HOLD: skip {rid}")
        return res
    WORK.mkdir(parents=True, exist_ok=True)
    src = patched_source(r)
    tmp = WORK / f"{rid}.qnt"
    tmp.write_text(src, encoding="utf8")
    if r["module"] == "admission_wit":
        (WORK / "admission.qnt").write_text((HERE / "admission.qnt").read_text(encoding="utf8"), encoding="utf8")
    if r["tool"] == "verify":
        cmd = ["quint", "verify", f"--server-endpoint=localhost:{port}", f"--max-steps={r['steps']}",
               f"--invariant={r['invariant']}", f"--main={r['module']}", str(tmp)]
        to = TIMEOUT_V
    else:
        cmd = ["quint", "run", "--backend=rust", f"--max-steps={r['steps']}", f"--max-samples={r['samples']}",
               f"--invariant={r['invariant']}", f"--main={r['module']}", "--seed=0xadc0130", str(tmp)]
        to = TIMEOUT_S
    t0 = time.time()
    for attempt in range(3):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=to, env=ENV, cwd=WORK)
            out = (p.stdout or "") + (p.stderr or "")
            rc = p.returncode
        except subprocess.TimeoutExpired as e:
            out = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) + "\n[TIMEOUT]"
            rc = -1
        if "Connection dropped" in out and attempt < 2:
            logw(f"retry after transient server error: {rid}")
            time.sleep(3)
            continue
        break
    secs = round(time.time() - t0, 1)
    if "[TIMEOUT]" in out: actual = "timeout"
    elif re.search(r"\[violation\]|found a counterexample|Invariant violated", out): actual = "violated"
    elif "[ok]" in out and rc == 0: actual = "hold"
    else: actual = f"error(rc={rc})"
    fn = RUNS / f"{rid}.txt"
    trimmed = out if len(out) < 24000 else out[:12000] + f"\n...[{len(out)-20000} bytes trimmed]...\n" + out[-8000:]
    fn.write_text(f"# cmd: {' '.join(cmd)}\n# overrides: {r['over']}\n# sha256(.qnt run): {hashlib.sha256(src.encode()).hexdigest()}\n# secs: {secs}, rc: {rc}\n\n{trimmed}", encoding="utf8")
    res = dict(r, id=rid, actual=actual, secs=secs, file=f"runs/{rid}.txt", detail="")
    logw(f"{r['tool']} {rid}: expect={r['expect']} actual={actual} ({secs}s)")
    return res

def main():
    global log_fh
    args = sys.argv[1:]
    only = None
    if "--only" in args: only = args[args.index("--only") + 1]
    RUNS.mkdir(exist_ok=True)
    log_fh = open(HERE / "run.log", "a", encoding="utf8")
    selected = [r for r in RS if not only or re.search(only, runid(r))]
    logw(f"START {len(selected)} runs, HOLD={HOLD.exists()}, pin={PIN}")
    # verify-runs use a queue of two ports; sim-runs run sequentially between (no Apalache).
    q = list(PORTS)
    qlock = threading.Lock()
    def worker(r):
        with qlock: port = q.pop()
        try:
            return run_one(r, port)
        finally:
            with qlock: q.append(port)
    verify = [r for r in selected if r["tool"] == "verify"]
    sim = [r for r in selected if r["tool"] == "sim"]
    res = []
    for r in sim:
        res.append(run_one(r, 0))
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        res.extend(ex.map(worker, verify))
    results.extend(res)
    write_results()
    match = sum(1 for r in res if r["actual"] == r["expect"])
    logw(f"DONE {len(res)} runs, match={match}, mismatch={len(res)-match}")

def write_results():
    rows = sorted(results, key=lambda x: runid(x))
    path = HERE / "results.tsv"
    existing = {}
    if path.exists():
        for line in path.read_text(encoding="utf8").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 11: existing[parts[0]] = line
    with path.open("w", encoding="utf8") as f:
        f.write("id\tmodule\tinvariant\tkind\ttool\tmax_steps\tsamples\toverrides\texpect\tactual\tmatch\tsecs\tfile\n")
        merged = dict(existing)
        for r in rows:
            ov = ",".join(f"{k}={v}" for k, v in r["over"].items()) or "-"
            mt = "ok" if r["actual"] == r["expect"] else "MISMATCH"
            merged[runid(r)] = "\t".join(map(str, [runid(r), r["module"], r["invariant"], r["kind"], r["tool"], r["steps"], r["samples"] if r["tool"]=="sim" else "-", ov, r["expect"], r["actual"], mt, r["secs"], r["file"]]))
        for k in sorted(merged): f.write(merged[k] + "\n")

if __name__ == "__main__":
    main()
