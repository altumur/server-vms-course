#!/usr/bin/env python3
"""run.py: runs Quint/Apalache over the models of this directory and writes results.tsv (one row per run).
Each run: a variant copy of the module with `// @override` constants replaced, then `quint verify` (Apalache) or
`quint run` (rust simulator). Usage: run.py [--trial OUTDIR] [--only ID[,ID...]] [--kind property,witness,...]
"""
import argparse, csv, os, re, subprocess, sys, time, pathlib
HERE = pathlib.Path(__file__).resolve().parent
ENDPOINT = "localhost:18823"   # own server, not 8822
HOLD = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p06q/HOLD"
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk", PATH="/opt/quint/jdk/bin:" + os.environ["PATH"])

# id, module, invariant, kind, tool, max_steps, samples, overrides, expect, why
R = []
def run(i, mod, inv, kind, tool, steps, samples, ov, expect, why):
    R.append(dict(id=i, module=mod, invariant=inv, kind=kind, tool=tool, max_steps=steps,
                  samples=samples, overrides=ov, expect=expect, why=why))
A = "apalache"; S = "sim"
H = "hold"; V = "violated"

# --- claim_put: PUT continuation (S6, the unit/table equal-revision proof)
m = "claim_put"
run("put-false-success", m, "noFalseSuccess", "property", A, 12, 0, {}, V, "06.1:714: foreign edit at the intended revision reads as own write")
run("put-at-most-once", m, "atMostOneLand", "property", A, 14, 0, {}, V, "landed then foreign edit, continuation re-applies (06.1:714,830)")
run("put-false-success-noforeign", m, "noFalseSuccess", "control", A, 14, 0, {"FOREIGN_MAX": "0"}, H, "without a foreign writer the equal revision can only be own")
run("put-at-most-once-noforeign", m, "atMostOneLand", "control", A, 14, 0, {"FOREIGN_MAX": "0"}, H, "without a foreign writer: one landing")
run("put-repair-content", m, "noFalseSuccess", "control", A, 14, 0, {"REPAIR": "true"}, H, "continuation also proves own content (control of the fix)")
run("put-w-done", m, "w_done_after_unknown", "witness", A, 14, 0, {}, V, "done via continuation after unknown outcome reachable")
run("put-w-takeover", m, "w_takeover_reached", "witness", A, 8, 0, {}, V, "takeover reachable")
run("put-w-foreign", m, "w_foreign_seen", "witness", A, 14, 0, {}, V, "foreign edit and done reachable")
run("put-w-crash", m, "w_done_after_crash", "witness", A, 14, 0, {"FOREIGN_MAX": "0"}, V, "done reachable after the executor crashed (life:92) while the claim was pending")
run("put-w-land", m, "w_land", "witness", A, 6, 0, {}, V, "own write reachable")
run("put-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")
run("put-mut-no-guard", m, "atMostOneLand", "mutant", A, 14, 0, {"MUT": '"no_guard"', "FOREIGN_MAX": "0"}, V, "without the claim guard a late write of A lands after takeover")
run("put-mut-no-intent", m, "atMostOneLand", "mutant", A, 14, 0, {"MUT": '"no_intent"', "FOREIGN_MAX": "0"}, V, "no saved intent: continuation cannot prove own write, the edit lands twice")
run("put-mut-blind", m, "atMostOneLand", "mutant", A, 14, 0, {"MUT": '"takeover_blind"', "FOREIGN_MAX": "0"}, V, "continuation does not look at the target: the edit lands twice")
# --- claim_post: POST (holds; mutants must break)
m = "claim_post"
for inv in ("atMostOneLand", "noFalseSuccess", "noFalse409", "doneMatches"):
    run(f"post-{inv}", m, inv, "property", A, 14, 0, {}, H, "06.1:713,719,763,767: intent, cas, guard")
run("post-w-cont", m, "w_done_cont", "witness", A, 12, 0, {}, V, "done by continuation reachable")
run("post-w-409", m, "w_409_foreign", "witness", A, 8, 0, {}, V, "409 exists for a foreign row reachable")
run("post-w-ok", m, "w_done_ok", "witness", A, 8, 0, {}, V, "normal 201 reachable")
run("post-w-foreign", m, "w_foreign_row", "witness", A, 3, 0, {}, V, "foreign row reachable")
run("post-w-takeover", m, "w_takeover", "witness", A, 8, 0, {}, V, "takeover reachable")
run("post-w-crash", m, "w_done_after_crash", "witness", A, 14, 0, {}, V, "201 reachable after the executor crashed while the claim was pending")
run("post-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")
run("post-mut-no-intent", m, "noFalse409", "mutant", A, 14, 0, {"MUT": '"no_intent"'}, V, "no intent: continuation cannot prove own row")
run("post-mut-fresh-born", m, "noFalse409", "mutant", A, 14, 0, {"MUT": '"fresh_born"'}, V, "takeover drops the intent: own row looks foreign")
run("post-mut-rev-only", m, "noFalseSuccess", "mutant", A, 14, 0, {"MUT": '"rev_only"'}, V, "proof by revision only: a foreign row reads as own")
run("post-mut-no-guard", m, "atMostOneLand", "mutant", A, 14, 0, {"MUT": '"no_guard"'}, V, "no guard: late A write after B's write")
run("post-mut-no-proof", m, "noFalse409", "mutant", A, 14, 0, {"MUT": '"no_proof"'}, V, "own row without the proof of 06.1:713,767 reads as foreign")
# --- claim_retention (S7)
m = "claim_retention"
run("ret-min", m, "removedNotEarly", "property", A, 10, 0, {}, H, "06.1:183: first observation >= save time")
run("ret-bound-restarts", m, "removedInBound", "property", A, 12, 0, {}, V, "restarts reset the observation: cleanup can recede indefinitely")
run("ret-bound-norestart", m, "removedInBound", "control", A, 12, 0, {"MAX_RESTARTS": "0"}, H, "without restarts the fair cleanup removes in KEEP+slack")
run("ret-w-removed", m, "w_removed", "witness", A, 8, 0, {"MAX_RESTARTS": "0"}, V, "cleanup reachable")
run("ret-w-restart", m, "w_restart_used", "witness", A, 8, 0, {}, V, "restart reachable")
run("ret-mut-wall", m, "removedNotEarly", "mutant", A, 10, 0, {"MUT": '"wall_age"', "WALL_JUMP": "86400"}, V, "wall age + forward jump: removal before KEEP of true time")
run("ret-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")
# --- ops_clock (S13)
m = "ops_clock"
fwd = "Set(86405)"
run("clk-cancel-early-fwd", m, "cancelNotEarly", "property", A, 8, 0, {"JUMPS": fwd}, V, "forward jump > RUN_MAX: time-based cancel at true age 0 (06.9:405)")
run("clk-step-depends-fwd", m, "stepNotClockCancelled", "property", A, 8, 0, {"JUMPS": fwd}, V, "06.9:28 'neither a step ... depends' vs round+finish")
run("clk-reap-early-fwd", m, "reapNotEarly", "property", A, 10, 0, {"JUMPS": fwd, "MAX_JUMPS": "1"}, V, "reaper wall jump deletes finished record early (06.9:494)")
run("clk-run-bounded-back", m, "runBounded", "property", A, 12, 0, {"JUMPS": "Set(-86400)"}, V, "backward jump postpones the deadline: roots held beyond OPS_RUN_MAX")
run("clk-cancel-early-nojump", m, "cancelNotEarly", "control", A, 12, 0, {"MAX_JUMPS": "0"}, H, "no jumps: not early")
run("clk-reap-early-nojump", m, "reapNotEarly", "control", A, 12, 0, {"MAX_JUMPS": "0"}, H, "no jumps: KEEP respected")
run("clk-run-bounded-nojump", m, "runBounded", "control", A, 12, 0, {"MAX_JUMPS": "0"}, H, "no jumps: bound holds under fair ticks")
run("clk-mono-early-fwd", m, "cancelNotEarly", "control", A, 12, 0, {"MONO": "true", "JUMPS": fwd}, H, "monotonic age (repair of S13): jump irrelevant")
run("clk-mono-reap-fwd", m, "reapNotEarly", "control", A, 12, 0, {"MONO": "true", "JUMPS": fwd}, H, "monotonic retention")
run("clk-mut-run-ge0", m, "cancelNotEarly", "mutant", A, 8, 0, {"MUT": '"run_ge0"', "MAX_JUMPS": "0"}, V, "mutant cancels regardless of RUN_MAX")
run("clk-mut-reap-nokeep", m, "reapNotEarly", "mutant", A, 10, 0, {"MUT": '"reap_nokeep"', "MAX_JUMPS": "0"}, V, "mutant reaps at once")
run("clk-w-cancel", m, "w_cancel_by_time", "witness", A, 10, 0, {"MAX_JUMPS": "0"}, V, "cancel by true age reachable")
run("clk-w-reap", m, "w_reap", "witness", A, 12, 0, {"MAX_JUMPS": "0"}, V, "reap at KEEP reachable")
run("clk-w-ok-step", m, "w_ok_step", "witness", A, 6, 0, {"MAX_JUMPS": "0"}, V, "a step ok reachable")
run("clk-w-early", m, "w_early_cancel", "witness", A, 6, 0, {"JUMPS": fwd}, V, "witness of early cancel")
run("clk-w-steps", m, "w_steps_cancelled", "witness", A, 8, 0, {"JUMPS": fwd}, V, "steps cancelled by the clock")
run("clk-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")
# --- ops_leader (S5, S6 steps)
m = "ops_leader"
for inv in ("outcomeOnce", "okOnce", "doneHasOutcome", "outcomeOkIsBatch"):
    run(f"lead-{inv}", m, inv, "property", A, 16, 0, {}, H, "06.9:318-321, 440-451: guard+cas")
run("lead-w-done-ok", m, "w_done_ok", "witness", A, 10, 0, {}, V, "normal completion reachable")
run("lead-w-sigterm-handover", m, "w_after_sigterm_handover", "witness", A, 16, 0, {}, V, "operation completes on another leader after SIGTERM with two calls")
run("lead-w-second-call", m, "w_handover_by_second_call", "witness", A, 16, 0, {}, V, "after SIGTERM of the holder the other leader issues its own call and the step ends ok")
run("lead-w-sigterm-done", m, "w_sigterm_then_done", "witness", A, 14, 0, {}, V, "done with a process gone")
run("lead-w-two-calls", m, "w_two_calls", "witness", A, 16, 0, {}, V, "two calls of one step key after handover")
run("lead-w-cancel", m, "w_cancel", "witness", A, 8, 0, {}, V, "cancel path")
run("lead-w-fail", m, "w_fail", "witness", A, 14, 0, {}, V, "fail not_run path")
run("lead-w-handover-gen", m, "w_handover_gen", "witness", A, 14, 0, {}, V, "operation finished in generation 2")
run("lead-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")
run("lead-sim-allSafe", m, "allSafe", "property", S, 40, 3000, {}, H, "simulation: deeper traces")
run("lead-mut-no-cas", m, "outcomeOnce", "mutant", A, 16, 0, {"MUT": '"no_outcome_cas"'}, V, "without cas two outcomes land")
run("lead-mut-finish-nocas", m, "outcomeOnce", "mutant", A, 16, 0, {"MUT": '"finish_no_cancel_cas"'}, V, "finish overwrites outcome")
run("lead-noStaleLanding", m, "noStaleLanding", "property", A, 12, 0, {}, H, "06.9:320,399,508: a batch under an older generation does not land after the bump")
run("lead-sim-noStale", m, "noStaleLanding", "property", S, 40, 3000, {}, H, "simulation: deeper traces than the 12-step SMT bound (16 steps took 27 min)")
run("lead-c-allsafe-nogen", m, "allSafe", "control", A, 16, 0, {"MUT": '"no_gen_guard"'}, H, "the at-most-one outcome rests on cas of the outcome; the generation guard is a second layer")
run("lead-mut-no-gen", m, "noStaleLanding", "mutant", A, 16, 0, {"MUT": '"no_gen_guard"'}, V, "without the guard a stale ticket lands after the bump")
run("lead-mut-no-bump", m, "noStaleLanding", "mutant", A, 16, 0, {"MUT": '"no_bump"'}, V, "without the epoch rewrite a former leader's batch still passes the guard")
# --- feed (S15)
m = "feed"
run("feed-noskip", m, "noSilentSkip", "property", A, 12, 0, {"MODE": '"burst"'}, H, "06.1:555,994-1002: eviction gives reset, not a gap")
run("feed-known", m, "knownSound", "property", A, 12, 0, {}, H, "client knowledge sound")
run("feed-loop-rate257", m, "noResetLoop", "property", A, 14, 0, {"RATE": "257", "D": "1"}, V, "sustained rate*D > H: reset loop")
run("feed-loop-rate129-d2", m, "noResetLoop", "property", A, 14, 0, {"RATE": "129", "D": "2"}, V, "sustained rate*D > H at D=2")
run("feed-loop-ok-rate128-d2", m, "noResetLoop", "control", A, 14, 0, {"RATE": "128", "D": "2"}, H, "boundary: rate*D <= H: no loop")
run("feed-loop-ok-rate256-d1", m, "noResetLoop", "control", A, 14, 0, {"RATE": "256", "D": "1"}, H, "boundary at D=1")
run("feed-loop-ok-burst", m, "noResetLoop", "control", A, 14, 0, {"MODE": '"burst"', "BURST": "257", "RESTARTS_MAX": "0"}, H, "one burst, no restarts: one reset per client, no loop")
run("feed-storm-burst", m, "noStorm", "property", A, 8, 0, {"MODE": '"burst"', "BURST": "257"}, V, "both clients reset in one tick: synchronous full re-read")
run("feed-w-reset", m, "w_reset", "witness", A, 6, 0, {"MODE": '"burst"'}, V, "reset reachable")
run("feed-w-delivered", m, "w_delivered", "witness", A, 6, 0, {"RATE": "1"}, V, "delivery reachable")
run("feed-w-allread", m, "w_all_read", "witness", A, 8, 0, {"MODE": '"burst"'}, V, "both clients in re-read")
run("feed-mut-no-reset", m, "noSilentSkip", "mutant", A, 10, 0, {"MUT": '"no_reset"', "MODE": '"burst"'}, V, "without the reset the feed silently skips evicted numbers")
run("feed-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")
# --- lanes (S2)
m = "lanes"
run("lane-deadlock", m, "noDeadlock", "property", A, 8, 0, {}, H, "06.5:255: callback lane separate")
run("lane-callback", m, "callbackEverAdmissible", "property", A, 8, 0, {}, H, "06.5:824: L_CB >= L_COMMON")
run("lane-mut-common", m, "noDeadlock", "mutant", A, 8, 0, {"MUT": '"callback_on_common"'}, V, "callbacks on the common lane deadlock")
run("lane-c-cb-small", m, "callbackEverAdmissible", "control", A, 8, 0, {"L_CB": "1", "L_COMMON": "2"}, V, "L_CB < L_COMMON breaks the admissibility (06.5:824 is needed)")
run("lane-w-common-full", m, "w_common_full_stalled", "witness", A, 6, 0, {}, V, "stalled readers can occupy the common lane and refuse operators")
run("lane-w-pass", m, "w_pass_ok", "witness", A, 4, 0, {}, V, "normal pass")
run("lane-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")
# --- reseal (S12)
m = "reseal"
run("reseal-noedit-lost", m, "noEditLost", "property", A, 10, 0, {}, H, "06.2:215 cas of the read version")
run("reseal-w-done", m, "w_done", "witness", A, 8, 0, {}, V, "both consoles complete")
run("reseal-w-edit", m, "w_edit_and_seal", "witness", A, 8, 0, {}, V, "edit and reseal both happen")
run("reseal-mut-no-cas", m, "noEditLost", "mutant", A, 8, 0, {"MUT": '"no_cas"'}, V, "reseal without cas loses a concurrent edit")
run("reseal-c-false", m, "c_false", "control", A, 2, 0, {}, V, "tool control: a false invariant is reported as violated")

def variant(src, ov, dst):
    s = open(src, encoding="utf8").read()
    for k, v in ov.items():
        pat = re.compile(r"^(\s*pure val %s(?:: [^=]+)? =)[^/\n]*(// @override.*)$" % re.escape(k), re.M)
        s, n = pat.subn(lambda m: f"{m.group(1)} {v}  {m.group(2)}", s)
        if n != 1:
            sys.exit(f"override {k} not found in {src}")
    open(dst, "w", encoding="utf8").write(s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial")
    ap.add_argument("--only")
    ap.add_argument("--kind")
    ap.add_argument("--modules")
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument("--part", help="k/n: run the k-th of n partitions (0-based)")
    a = ap.parse_args()
    outdir = pathlib.Path(a.trial) if a.trial else HERE / "runs"
    outdir.mkdir(parents=True, exist_ok=True)
    rows = list(R)
    if a.only:
        ids = set(a.only.split(",")); rows = [r for r in rows if r["id"] in ids]
    if a.kind:
        kinds = set(a.kind.split(",")); rows = [r for r in rows if r["kind"] in kinds]
    if a.modules:
        mods = set(a.modules.split(",")); rows = [r for r in rows if r["module"] in mods]
    if a.part:
        k, n = map(int, a.part.split("/"))
        rows = [r for i, r in enumerate(rows) if i % n == k]
    tsv = outdir / "results.tsv" if a.trial else HERE / "results.tsv"
    log = open(outdir / "run.log" if a.trial else HERE / "run.log", "a", encoding="utf8")
    # a single header: two partitions race on tsv.exists(); run.py callers sort and de-duplicate afterwards (see report)
    new = not tsv.exists()
    f = open(tsv, "a", encoding="utf8", newline="")
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    if new:
        w.writerow("id module invariant kind tool max_steps samples overrides expect actual match secs file".split())
    for r in rows:
        if os.path.exists(HOLD):
            print("HOLD present: stopping", flush=True); log.write("HOLD present: stopping\n"); break
        v = outdir / f"{r['id']}.qnt"
        variant(HERE / f"{r['module']}.qnt", r["overrides"], v)
        out = outdir / f"{r['id']}.out"
        t0 = time.time()
        if r["tool"] == A:
            cmd = ["quint", "verify", v.name, f"--main={r['module']}", f"--server-endpoint={a.endpoint}", f"--max-steps={r['max_steps']}", f"--invariant={r['invariant']}"]
        else:
            cmd = ["quint", "run", v.name, f"--main={r['module']}", "--backend=rust", f"--max-steps={r['max_steps']}", f"--max-samples={r['samples']}", "--n-threads=4", f"--invariant={r['invariant']}"]
        retries = 0
        while True:
            p = subprocess.run(cmd, cwd=outdir, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1800)
            o = p.stdout
            if "Connection dropped" in o and retries < 2:
                retries += 1
                log.write(f"{r['id']}: retry {retries} after server Connection dropped\n"); log.flush()
                t0 = time.time()
                continue
            break
        secs = round(time.time() - t0, 1)
        open(out, "w", encoding="utf8").write(o)
        if "reached a deadlock" in o:
            act = "deadlock"
        elif "[violation]" in o or "found a counterexample" in o or "Invariant violation" in o:
            act = "violated"
        elif "[ok]" in o or "No violation found" in o:
            act = "hold"
        else:
            act = "error"
        match = "yes" if act == r["expect"] else "no"
        ov = ";".join(f"{k}={v}" for k, v in sorted(r["overrides"].items()))
        rel = out.relative_to(HERE) if not a.trial else out
        w.writerow([r["id"], r["module"], r["invariant"], r["kind"], r["tool"] + (" (bounded)" if r["tool"] == A else ""), r["max_steps"], r["samples"], ov, r["expect"], act, match, secs, rel])
        f.flush()
        log.write(f"{time.strftime('%H:%M:%S')} {r['id']} expect={r['expect']} actual={act} match={match} secs={secs} why={r['why']}\n"); log.flush()
        print(f"{r['id']:<28} {r['invariant']:<26} {r['kind']:<9} expect={r['expect']:<9} actual={act:<9} {match} {secs}s", flush=True)

if __name__ == "__main__":
    main()
