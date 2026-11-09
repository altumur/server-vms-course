#!/usr/bin/env python3
# Runs all checks of the P/08 Quint model; append-only results.tsv and run.log, one row per run.
import subprocess, os, sys, time, threading, queue, shutil
from concurrent.futures import ThreadPoolExecutor
os.chdir(os.path.dirname(os.path.abspath(__file__)))
QUINT = "quint"
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk", PATH="/opt/quint/jdk/bin:" + os.environ["PATH"])
HOLD = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p08q/HOLD"
HEAD = "id\tmodule\tinvariant\tkind\ttool\tmax_steps\tsamples\toverrides\texpect\tactual\tmatch\tsecs\tfile\n"
lock = threading.Lock()
OK, VIO = "ok", "violated"
SAMPLES = {"wit_takeover_conflict": 2000000, "inv_no_overwrite": 2000000}  # a rare interleaving of 8 steps; the random simulation needs more samples
SCR = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p08q"
slock = threading.Lock()

def listening(port):
    import socket
    s = socket.socket(); s.settimeout(1)
    try:
        s.connect(("127.0.0.1", port)); return True
    except OSError:
        return False
    finally:
        s.close()

def ensure_server(port):
    with slock:
        if listening(port): return
        env = dict(ENV, JVM_ARGS="-Xmx4g")
        log = open(f"{SCR}/ap{port}.log", "a")
        subprocess.Popen(["setsid", os.path.expanduser("~/.quint/apalache-dist-0.62.1/apalache/bin/apalache-mc"), "server", f"--port={port}", "--server-type=checker"], cwd=SCR, env=env, stdout=log, stderr=log, start_new_session=True)
        for _ in range(60):
            if listening(port): break
            time.sleep(1)
        with open("run.log", "a", encoding="utf8") as l:
            l.write(f"{time.strftime('%H:%M:%S',time.gmtime())} server restarted on port {port} listening={listening(port)}\n")

# (file, main, invariant, kind, expect, sim_steps, ap_steps, note/overrides)
R = []
def add(f, m, inv, kind, expect, ss, ap, ov=""):
    R.append((f, m, inv, kind, expect, ss, ap, ov or m))

# p08_turn
for inv, e in [("inv_guard", OK), ("inv_no_late_apply", OK), ("inv_no_reorder", OK), ("inv_no_overwrite", OK),
               ("inv_no_drop", VIO), ("inv_no_stale_restore_obj", VIO)]:
    add("p08_turn.qnt", "turn_norm", inv, "property", e, 18, 11)
for w in ["wit_unknown_barrier_refuse", "wit_barrier_only", "wit_takeover_conflict", "wit_takeover_confirm_fails", "wit_sigterm_inflight_refused", "wit_restore_overlap", "wit_applied_write"]:
    add("p08_turn.qnt", "turn_norm", w, "witness", VIO, 18, 11)
add("p08_turn.qnt", "turn_m_nobump", "inv_no_late_apply", "mutant", VIO, 18, 11)
add("p08_turn.qnt", "turn_m_blind", "inv_no_reorder", "mutant", VIO, 18, 11)
add("p08_turn.qnt", "turn_m_get_after", "inv_no_overwrite", "mutant", VIO, 18, 11)
add("p08_turn.qnt", "turn_m_noguard", "inv_guard", "mutant", VIO, 18, 11)
add("p08_turn.qnt", "turn_c_drain", "inv_no_drop", "control", OK, 18, 11)
add("p08_turn.qnt", "turn_c_restore", "inv_no_stale_restore_obj", "control", OK, 18, 11)
# p08_accept
for inv, e in [("inv_mark_points", OK), ("inv_no_dup_gen", OK), ("inv_no_write_over_unreadable", OK), ("inv_503_means_nothing_accepted", VIO)]:
    add("p08_accept.qnt", "accept_norm", inv, "property", e, 14, 12)
for w in ["wit_503_with_mark_then_same", "wit_store_down_reached", "wit_mark_set"]:
    add("p08_accept.qnt", "accept_norm", w, "witness", VIO, 14, 12)
add("p08_accept.qnt", "accept_m_norepeat", "inv_no_dup_gen", "mutant", VIO, 14, 12)
add("p08_accept.qnt", "accept_m_absent", "inv_no_write_over_unreadable", "mutant", VIO, 14, 12)
add("p08_accept.qnt", "accept_m_markfirst", "inv_mark_points", "mutant", VIO, 14, 12)
# p08_locks
for inv, e in [("inv_e2_wait_le_deadline", OK), ("inv_r2_wait_le_deadline", VIO), ("inv_no_stale_after_release", OK), ("inv_section_bounded", VIO)]:
    add("p08_locks.qnt", "locks_text", inv, "property", e, 20, 14)
for w in ["wit_freeze_blocks_then_calledoff", "wit_r2_waits_long", "wit_e2_waits_nonzero", "wit_e2_wait_tight", "wit_section_io_alive_old"]:
    add("p08_locks.qnt", "locks_text", w, "witness", VIO, 20, 14)
add("p08_locks.qnt", "locks_dep30", "inv_e2_wait_le_deadline", "property", OK, 20, 14)
add("p08_locks.qnt", "locks_dep30", "wit_frozen_then_e2_refused", "witness", VIO, 20, 14)
add("p08_locks.qnt", "locks_dep120", "inv_e2_wait_le_deadline", "property", OK, 20, 14)
add("p08_locks.qnt", "locks_text", "wit_frozen_then_e2_refused", "control", OK, 20, 14)
add("p08_locks.qnt", "locks_c_budget", "inv_r2_wait_le_deadline", "control", OK, 20, 14)
add("p08_locks.qnt", "locks_c_budget", "wit_r2_refused_by_budget", "witness", VIO, 20, 14)
add("p08_locks.qnt", "locks_c_budget", "wit_r2_budget_tight", "witness", VIO, 20, 14)
add("p08_locks.qnt", "locks_c_budget", "inv_section_bounded", "control", OK, 20, 14, "bounded by construction (restart assumed), see report")
add("p08_locks.qnt", "locks_c_budget", "inv_no_stale_after_release", "property", OK, 20, 14)
add("p08_locks.qnt", "locks_m_nocalloff", "inv_e2_wait_le_deadline", "mutant", VIO, 20, 14)
add("p08_locks.qnt", "locks_m_release", "inv_no_stale_after_release", "mutant", VIO, 20, 14)
# p08_parts
add("p08_parts.qnt", "parts_text", "inv_claim_complete", "property", VIO, 14, 14, "SILENT_CONTINUE branch of the text-silent point")
add("p08_parts.qnt", "parts_text", "inv_answer_by_deadline", "property", OK, 14, 14)
add("p08_parts.qnt", "parts_text", "wit_claim_after_failed_part", "witness", VIO, 14, 14)
add("p08_parts.qnt", "parts_text_slow", "inv_answer_by_deadline", "property", VIO, 14, 14)
add("p08_parts.qnt", "parts_text_slow", "wit_past_deadline_running", "witness", VIO, 14, 14)
add("p08_parts.qnt", "parts_text_slow", "inv_answered_within", "property", VIO, 14, 14)
add("p08_parts.qnt", "parts_text_slow", "wit_claim_past_deadline", "witness", VIO, 14, 14)
add("p08_parts.qnt", "parts_text", "inv_answered_within", "property", OK, 14, 14)
add("p08_parts.qnt", "parts_incremental_abort", "inv_no_mixed_visible", "property", VIO, 14, 14)
add("p08_parts.qnt", "parts_incremental_abort", "inv_claim_complete", "property", OK, 14, 14)
add("p08_parts.qnt", "parts_incremental_abort", "wit_part_failed_then_mix", "witness", VIO, 14, 14)
add("p08_parts.qnt", "parts_incremental_abort", "wit_abort_clean", "witness", VIO, 14, 14)
for inv, e, k in [("inv_claim_complete", OK, "control"), ("inv_no_mixed_visible", OK, "control"), ("inv_answer_by_deadline", OK, "control"), ("wit_claim_full", VIO, "witness")]:
    add("p08_parts.qnt", "parts_c_fetchfirst", inv, k, e, 14, 14)
add("p08_parts.qnt", "parts_c_fetchfirst_slow", "inv_answer_by_deadline", "control", OK, 14, 14)
add("p08_parts.qnt", "parts_c_fetchfirst_slow", "inv_answered_within", "control", OK, 14, 14)
add("p08_parts.qnt", "parts_c_fetchfirst_slow", "wit_refusal_before_deadline", "witness", VIO, 14, 14)
add("p08_parts.qnt", "parts_c_fetchfirst", "inv_answered_within", "control", OK, 14, 14)
add("p08_parts.qnt", "parts_c_fetchfirst_slow", "wit_claim_full", "control", OK, 14, 14, "no complete claim when the sum of reads exceeds the deadline")
add("p08_parts.qnt", "parts_m_claimearly", "inv_claim_complete", "mutant", VIO, 14, 14)
# p08_partgc
add("p08_partgc.qnt", "gc_text_memory", "inv_no_gc_under_young_fetch", "property", VIO, 24, 16, "memory accounting (not named at the pin) + restart")
add("p08_partgc.qnt", "gc_text_memory", "wit_restart_gc_read", "witness", VIO, 24, 16)
add("p08_partgc.qnt", "gc_c_durable", "inv_no_gc_under_young_fetch", "control", OK, 24, 16)
add("p08_partgc.qnt", "gc_c_durable", "wit_gc_happens", "witness", VIO, 24, 16)
add("p08_partgc.qnt", "gc_m_ignore", "inv_no_gc_under_young_fetch", "mutant", VIO, 24, 16)
# p08_gather
add("p08_gather.qnt", "gather_text", "inv_deleted_not_returned", "property", VIO, 8, 8, "second move, limit of 08.8:517")
add("p08_gather.qnt", "gather_text", "wit_del_move_back", "witness", VIO, 8, 8)
add("p08_gather.qnt", "gather_text", "wit_merge_reachable", "witness", VIO, 8, 8)
add("p08_gather.qnt", "gather_one_move", "inv_deleted_not_returned", "property", OK, 8, 8)
add("p08_gather.qnt", "gather_c_keep", "inv_deleted_not_returned", "control", OK, 8, 8)
add("p08_gather.qnt", "gather_m_ignore", "inv_deleted_not_returned", "mutant", VIO, 8, 8)
# p08_clock
for inv, m, e, k in [("inv_hold_covers_token", "hold_j0_slow", OK, "property"),
                     ("inv_hold_covers_token", "hold_j0_checker_behind60", VIO, "property"),
                     ("inv_hold_covers_token", "hold_j60_checker_true", VIO, "property"),
                     ("inv_hold_covers_token", "hold_j600", VIO, "property"),
                     ("inv_hold_covers_token", "hold_j600_anytime", VIO, "property"),
                     ("inv_hold_covers_token", "hold_c_q6", OK, "control"),
                     ("inv_hold_covers_token", "hold_m_noskew", VIO, "mutant"),
                     ("wit_jump_free_alive", "hold_j600", VIO, "witness"),
                     ("wit_free_after_issue", "hold_j0_slow", VIO, "witness")]:
    add("p08_clock.qnt", m, inv, k, e, 12, 12)
for inv, m, e, k in [("inv_assembly_after_real_window", "books_nojump", OK, "property"), ("inv_assembly_after_real_window", "books_forward", VIO, "property"),
                     ("wit_assembly_blocked_past_3x", "books_back", VIO, "witness"), ("wit_assembly_blocked_past_3x", "books_nojump", OK, "control"),
                     ("inv_wait_le_skew", "rev_nojump", OK, "property"), ("wit_waited", "rev_nojump", VIO, "witness"), ("wit_waited_tight", "rev_nojump", VIO, "witness"), ("inv_wait_le_skew", "rev_jump_big", VIO, "property")]:
    add("p08_clock.qnt", m, inv, k, e, 12, 12)
# p08_age
for inv, m, e, k in [("inv_not_early", "idem_restart_frequent", OK, "property"), ("inv_cleaned_by_2keep", "idem_restart_frequent", VIO, "property"),
                     ("wit_full_stale_past_keep", "idem_restart_frequent", VIO, "witness"), ("inv_cleaned_by_2keep", "idem_restart_rare", OK, "property"),
                     ("wit_cleaned", "idem_restart_rare", VIO, "witness"), ("inv_cleaned_by_2keep", "idem_c_survive", OK, "control"),
                     ("inv_cleaned_by_2keep", "quiet_restart_frequent", VIO, "property"), ("inv_cleaned_by_2keep", "quiet_restart_rare", OK, "property"),
                     ("inv_not_early", "idem_m_early", VIO, "mutant")]:
    add("p08_age.qnt", m, inv, k, e, 20, 14)
# p08_storm
for inv, m, e, k in [("inv_camera_admitted", "storm_text", OK, "property"), ("inv_whole_srv_le_rate", "storm_text", VIO, "property"), ("inv_sigwork_le_rate", "storm_text", VIO, "property"),
                     ("wit_whole_burst", "storm_text", VIO, "witness"), ("wit_camera_refused_with_sig", "storm_text", VIO, "witness"),
                     ("inv_whole_srv_le_rate", "storm_c_servers", OK, "control"), ("inv_camera_admitted", "storm_m_nothreshold", VIO, "mutant")]:
    add("p08_storm.qnt", m, inv, k, e, 10, 10)

def run(tool, port, spec, idx):
    f, m, inv, kind, expect, ss, ap, ov = spec
    rid = f"r{idx:03d}-{tool[0]}"
    out = f"runs/{rid}-{m}-{inv}.txt"
    t0 = time.time()
    if tool == "sim":
        n = SAMPLES.get(inv, 100000)
        cmd = [QUINT, "run", "--backend=rust", f"--main={m}", f"--invariant={inv}", f"--max-steps={ss}", f"--max-samples={n}", f]
        steps, samples = ss, n
        to = 600
    else:
        cmd = [QUINT, "verify", f"--server-endpoint=localhost:{port}", f"--main={m}", f"--invariant={inv}", f"--max-steps={ap}", f]
        steps, samples = ap, "-"
        to = 1500
    if tool != "sim":
        ensure_server(port)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=to, env=ENV)
        o = p.stdout + p.stderr
        if "deadlock" in o: act = "deadlock"
        elif "[ok]" in o: act = OK
        elif "[violation]" in o: act = VIO
        else: act = "error"
    except subprocess.TimeoutExpired as e:
        o = f"TIMEOUT after {to}s"; act = "timeout"
    open(out, "w", encoding="utf8").write(" ".join(cmd) + "\n\n" + o)
    secs = round(time.time() - t0, 1)
    row = [rid, m, inv, kind, "quint-run-rust" if tool == "sim" else "apalache", steps, samples, ov, expect, act, "yes" if act == expect else "NO", secs, os.path.join("runs", os.path.basename(out))]
    with lock:
        with open("results.tsv", "a", encoding="utf8") as t:
            t.write("\t".join(map(str, row)) + "\n")
        with open("run.log", "a", encoding="utf8") as l:
            l.write(f"{time.strftime('%H:%M:%S',time.gmtime())} {rid} {m} {inv} {tool} expect={expect} actual={act} {secs}s\n")

def main():
    if os.path.exists(HOLD):
        print("HOLD present, no runs"); return
    if not os.path.exists("results.tsv") or os.path.getsize("results.tsv") == 0:
        open("results.tsv", "w", encoding="utf8").write(HEAD)
    done = set()
    if os.path.exists("results.tsv"):
        for line in open("results.tsv", encoding="utf8").read().splitlines()[1:]:
            done.add(line.split("\t")[0])
    specs = list(enumerate(R, 1))
    def task(a):
        tool, port, idx, spec = a
        rid = f"r{idx:03d}-{tool[0]}"
        if rid in done: return
        if os.path.exists(HOLD): return
        run(tool, port, spec, idx)
    # sim first (cheap, sequential), then apalache on 2 own servers
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(task, [("sim", None, i, s) for i, s in specs]))
    # one Apalache process, one at a time (Architect limit after the OOM of 2026-11-08/09): port 18825 only
    ap = [("apalache", 18825, i, s) for i, s in specs]
    with ThreadPoolExecutor(max_workers=1) as ex:
        list(ex.map(task, ap))

if __name__ == "__main__":
    main()
