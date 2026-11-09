#!/usr/bin/env python3
"""Runs the P/10 Quint models one at a time, strictly sequentially.

Apalache: one server only, started outside this script (port 18827, -Xmx4g).
Results: results.tsv and run.log are appended line by line; ITF traces in runs/.
A HOLD file (see HOLD_FILE) stops new runs.
Usage: run.py [--out DIR] [ID-prefix ...]
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SP = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p10q"
HOLD_FILE = SP + "/HOLD"
ENDPOINT = "localhost:18827"
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk",
           PATH="/opt/quint/jdk/bin:" + os.environ["PATH"])
TIMEOUT = 900
FIELDS = "id module invariant kind tool max_steps samples overrides expect actual match secs file".split()


def v(state, name):
    """Value of a variable in an ITF state, ignoring the module prefix."""
    for k, x in state.items():
        if k == name or k.endswith("::" + name):
            return dec(x)
    raise KeyError(name)


def dec(x):
    if isinstance(x, dict):
        if "#bigint" in x:
            return int(x["#bigint"])
        if "#map" in x:
            return {dec(a): dec(b) for a, b in x["#map"]}
        if "#set" in x:
            return [dec(a) for a in x["#set"]]
        if "#tup" in x:
            return tuple(dec(a) for a in x["#tup"])
        return {k: dec(a) for k, a in x.items()}
    return x


# Ordered-event checks on the LAST state of a witness trace: the claim of the
# witness, re-derived from the trace independently of the Quint predicate.
CHECKS = {
    "S05": lambda s: v(s, "tRefused") > v(s, "tLastStall") >= 0,
    "S06": lambda s: any(w == "exp" for w in v(s, "why").values()),
    "D03": lambda s: v(s, "tTerm") < v(s, "tBreak") < v(s, "tApplied"),
    "D04": lambda s: 0 <= v(s, "tApplied") < v(s, "tTerm") < v(s, "tBreak"),
    "E06": lambda s: 0 <= v(s, "t502")[1] < v(s, "tApply")[1],
    "E07": lambda s: v(s, "t502")[1] >= 0 and v(s, "lost") and v(s, "effects") == 0,
    "E08": lambda s: v(s, "effects") >= 2 and 0 <= v(s, "t502")[1] < v(s, "tApply")[2],
    "E10": lambda s: 0 <= v(s, "tBegin")[1] < v(s, "t409"),
    "E11": lambda s: 0 <= v(s, "t502")[1] < v(s, "tApply")[1] and v(s, "procAns")[2] == "replay" and v(s, "effects") == 1,
    "E12": lambda s: 0 <= v(s, "t502")[1] < v(s, "tApply")[1] and v(s, "clientAns")[2] == "412" and v(s, "effects") == 1,
    "A02": lambda s: 0 <= v(s, "tMark1") < v(s, "tCleanM1") < v(s, "tMiss") and v(s, "nMarkAfterRead") >= 2 and v(s, "outcome") == "unreadable",
    "A09": lambda s: v(s, "outcome") == "503" and v(s, "m2") != v(s, "m1"),
    "A10": lambda s: v(s, "outcome") == "page" and v(s, "pageGen") == v(s, "m2") != v(s, "m1"),
    "A11": lambda s: v(s, "outcome") == "unreadable" and v(s, "m1") in v(s, "lost"),
    "K03": lambda s: v(s, "jumped") and v(s, "real") - v(s, "jumpAt") > 5,
    "J02": lambda s: v(s, "tStuck") >= 0 and all(p == "wait" for p in v(s, "phase").values()),
    "J08": lambda s: v(s, "tLost") > v(s, "tStuck") >= 0,
}

def R(id_, module, inv, kind, expect, steps, tool="verify", samples=""):
    return dict(id=id_, module=module, invariant=inv, kind=kind, expect=expect, max_steps=steps, tool=tool, samples=samples)

F = {"stream": "stream_lane.qnt", "shutdown": "shutdown.qnt", "edit502": "edit_after_502.qnt",
     "alarmrace": "alarms_mark_race.qnt", "alarmcomp": "alarms_completeness.qnt",
     "clock": "silence_clock.qnt", "journal": "journal_lock.qnt"}

V, OK = "violation", "ok"
RUNS = [
    # stream_lane (C5)
    R("S01", "stream_norm", "inv_lane_cap", "property", OK, 8),
    R("S02", "stream_norm", "inv_stalled_hold_bounded", "property", OK, 12),
    R("S03", "stream_norm", "inv_open_hold_bounded", "property", OK, 8),
    R("S04", "stream_norm_h450", "inv_stalled_hold_bounded", "witness", V, 8),
    R("S05", "stream_norm", "wit_lane_full_of_stalled_refuses", "witness", V, 8),
    R("S06", "stream_norm", "wit_stalled_closed_by_exp", "witness", V, 8),
    R("S07", "stream_ctrl_term", "inv_stalled_hold_bounded", "control", OK, 8),
    R("S08", "stream_ctrl_term", "wit_stalled_closed_by_term", "witness", V, 8),
    R("S09", "stream_mut_noexp", "inv_stalled_hold_bounded", "mutant", V, 8),
    R("S10", "stream_mut_nocap", "inv_lane_cap", "mutant", V, 8),
    # shutdown (C6)
    R("D01", "shutdown_norm", "inv_no_early_502", "property", OK, 10),
    R("D02", "shutdown_norm", "inv_no_break_on_applied", "witness", V, 8),
    R("D03", "shutdown_norm", "wit_term_break_then_applied", "witness", V, 8),
    R("D04", "shutdown_norm", "wit_applied_then_term_break", "witness", V, 8),
    R("D05", "shutdown_norm", "inv_stop_bounded", "witness", V, 8),
    R("D06", "shutdown_norm", "wit_stop_hangs_on_stream", "witness", V, 8),
    R("D07", "shutdown_ctrl", "inv_stop_bounded", "control", OK, 10),
    R("D08", "shutdown_ctrl", "inv_no_break_on_applied", "control", OK, 10),
    R("D09", "shutdown_ctrl", "inv_edit_answered_at_exit", "control", OK, 10),
    R("D10", "shutdown_ctrl", "wit_drained_exit", "witness", V, 10),
    R("D11", "shutdown_mut_short", "inv_edit_answered_at_exit", "mutant", V, 10),
    R("D12", "shutdown_mut_short", "inv_no_break_on_applied", "mutant", V, 10),
    # edit_after_502 (C7)
    R("E01", "edit502_keyed", "inv_one_effect", "property", OK, 14),
    R("E02", "edit502_ifmatch", "inv_one_effect", "property", OK, 12),
    R("E03", "edit502_bare_noretry", "inv_one_effect", "property", OK, 12),
    R("E04", "edit502_keyed", "inv_no_late_answer", "property", OK, 12),
    R("E05", "edit502_keyed", "inv_502_not_early", "property", OK, 12),
    R("E06", "edit502_keyed", "wit_applied_after_502", "witness", V, 10),
    R("E07", "edit502_keyed", "wit_502_never_applied", "witness", V, 10),
    R("E08", "edit502_bare", "wit_double_effect_after_502", "witness", V, 12),
    R("E09", "edit502_bare", "inv_one_effect", "witness", V, 12),
    R("E10", "edit502_keyed", "wit_retry_409_in_flight", "witness", V, 12),
    R("E11", "edit502_keyed", "wit_retry_replay_one_effect", "witness", V, 12),
    R("E12", "edit502_ifmatch", "wit_retry_412", "witness", V, 12),
    R("E13", "edit502_mut_nomem", "inv_one_effect", "mutant", V, 12),
    R("E14", "edit502_mut_nobatch", "inv_one_effect", "mutant", V, 12),
    R("E15", "edit502_mut_late", "inv_no_late_answer", "mutant", V, 12),
    R("E16", "edit502_bare_noretry", "wit_applied_after_502", "witness", V, 10),
    # alarms_mark_race (C8)
    R("A01", "alarmrace_norm", "inv_no_false_unreadable", "witness", V, 12),
    R("A02", "alarmrace_norm", "wit_false_unreadable_ordered", "witness", V, 12),
    R("A03", "alarmrace_norm_shortgap", "inv_no_false_unreadable", "property", OK, 14),
    R("A04", "alarmrace_norm_every1", "inv_no_false_unreadable", "witness", V, 12),
    R("A05", "alarmrace_ctrl", "inv_no_false_unreadable", "control", OK, 20),
    R("A06", "alarmrace_ctrl", "inv_reread_once", "control", OK, 16),
    R("A07", "alarmrace_ctrl", "inv_page_named", "control", OK, 16),
    R("A08", "alarmrace_ctrl", "inv_changed_never_unreadable", "control", OK, 16),
    R("A09", "alarmrace_ctrl", "wit_503_changed_marker", "witness", V, 18),
    R("A10", "alarmrace_ctrl", "wit_fresh_after_reread", "witness", V, 12),
    R("A11", "alarmrace_ctrl", "wit_genuine_unreadable", "witness", V, 8),
    R("A12", "alarmrace_norm", "inv_page_named", "property", OK, 12),
    R("A13", "alarmrace_mut_keep1", "inv_no_false_unreadable", "mutant", V, 10),
    R("A14", "alarmrace_mut_nocmp", "inv_no_false_unreadable", "mutant", V, 18),
    R("A15", "alarmrace_mut_loop", "inv_reread_once", "mutant", V, 10),
    R("A16", "alarmrace_mut_markfirst", "inv_no_false_unreadable", "mutant", V, 8),
    R("A17", "alarmrace_norm", "wit_page_served", "witness", V, 6),
    R("A18", "alarmrace_norm_shortgap", "wit_one_mark_in_gap", "witness", V, 8),
    R("A19", "alarmrace_norm_shortgap", "inv_at_most_one_mark_in_gap", "property", OK, 14),
    # alarms_completeness (C11, not a race)
    R("C01", "alarmcomp_norm", "inv_complete_is_whole", "witness", V, 6),
    R("C02", "alarmcomp_norm", "wit_complete_with_unknown_history", "witness", V, 6),
    R("C03", "alarmcomp_norm", "wit_complete_with_unreadable_history", "witness", V, 6),
    R("C04", "alarmcomp_norm", "wit_complete_true_reachable", "witness", V, 6),
    R("C05", "alarmcomp_ctrl_unk503", "inv_complete_is_whole", "control", V, 6),
    R("C06", "alarmcomp_ctrl_unk503", "wit_complete_with_unknown_history", "control", OK, 6),
    R("C07", "alarmcomp_ctrl_field", "inv_complete_is_whole", "control", OK, 6),
    R("C08", "alarmcomp_ctrl_field", "wit_complete_true_reachable", "witness", V, 6),
    # silence_clock (C13)
    R("K01", "clock_sep", "inv_no_false_silent", "witness", V, 6),
    R("K02", "clock_sep", "wit_mass_false_silent", "witness", V, 6),
    R("K03", "clock_sep", "wit_false_silent_persists", "witness", V, 8),
    R("K04", "clock_nojump", "inv_no_false_silent", "control", OK, 8),
    R("K05", "clock_nojump", "inv_no_false_ok", "control", OK, 8),
    R("K06", "clock_nojump", "wit_true_silent_seen", "witness", V, 8),
    R("K07", "clock_sep_40", "inv_no_false_silent", "control", OK, 8),
    R("K08", "clock_sep_41", "inv_no_false_silent", "witness", V, 8),
    R("K09", "clock_co", "inv_false_silent_transient", "property", OK, 10),
    R("K10", "clock_co", "inv_no_false_silent", "witness", V, 8),
    R("K11", "clock_co_back", "wit_false_ok_hides_silence", "witness", V, 8),
    R("K12", "clock_sep_back", "wit_false_ok_hides_silence", "witness", V, 8),
    R("K13", "clock_sep", "inv_false_silent_transient", "witness", V, 8),
    # journal_lock (C15)
    R("J01", "journal_norm", "inv_wait_bounded", "witness", V, 8),
    R("J02", "journal_norm", "wit_stuck_blocks_both", "witness", V, 8),
    R("J03", "journal_norm", "inv_no_silent_loss", "witness", V, 8),
    R("J04", "journal_norm", "wit_io_then_403_lost", "witness", V, 8),
    R("J05", "journal_norm", "wit_line_written_answered", "witness", V, 8),
    R("J06", "journal_budget", "inv_wait_bounded", "property", OK, 10),
    R("J07", "journal_budget", "inv_no_silent_loss", "witness", V, 10),
    R("J08", "journal_budget", "wit_timeout_then_403_lost", "witness", V, 10),
    R("J09", "journal_ctrl", "inv_no_silent_loss", "control", OK, 10),
    R("J10", "journal_ctrl", "inv_wait_bounded", "control", OK, 12),
    R("J11", "journal_mut_unenforced", "inv_wait_bounded", "mutant", V, 10),
    R("J12", "journal_ctrl", "wit_line_written_answered", "witness", V, 8),
    R("J13", "journal_ctrl", "wit_timeout_503", "witness", V, 10),
    # simulation, secondary evidence only (one thread, one at a time)
    R("Z01", "stream_norm", "inv_stalled_hold_bounded", "property", OK, 25, "run", 3000),
    R("Z02", "shutdown_ctrl", "inv_no_break_on_applied", "control", OK, 25, "run", 3000),
    R("Z03", "edit502_keyed", "inv_one_effect", "property", OK, 25, "run", 3000),
    R("Z04", "alarmrace_norm_shortgap", "inv_no_false_unreadable", "property", OK, 25, "run", 3000),
    R("Z05", "alarmrace_ctrl", "inv_no_false_unreadable", "control", OK, 25, "run", 3000),
    R("Z06", "clock_nojump", "inv_no_false_silent", "control", OK, 25, "run", 3000),
    R("Z07", "journal_ctrl", "inv_no_silent_loss", "control", OK, 25, "run", 3000),
    R("Z08", "alarmcomp_ctrl_field", "inv_complete_is_whole", "control", OK, 12, "run", 3000),
]


def fname(module):
    for k, f in F.items():
        if module.startswith(k):
            return f
    raise KeyError(module)


def execute(run, out):
    os.makedirs(os.path.join(out, "runs"), exist_ok=True)
    qnt = os.path.join(HERE, fname(run["module"]))
    itf = os.path.join(out, "runs", run["id"] + ".itf.json")
    if run["tool"] == "verify":
        cmd = ["quint", "verify", "--server-endpoint", ENDPOINT, "--main", run["module"],
               "--max-steps", str(run["max_steps"]), "--invariant", run["invariant"],
               "--out-itf", itf, qnt]
    else:
        cmd = ["quint", "run", "--backend=rust", "--n-threads=1", "--main", run["module"],
               "--max-samples", str(run["samples"]), "--max-steps", str(run["max_steps"]),
               "--invariant", run["invariant"], qnt]
    t0 = time.time()
    try:
        cp = subprocess.run(cmd, cwd=SP, env=ENV, capture_output=True, text=True, timeout=TIMEOUT)
        rc, text = cp.returncode, cp.stdout + cp.stderr
    except subprocess.TimeoutExpired as e:
        rc, text = -1, "TIMEOUT " + str(e)
    secs = round(time.time() - t0, 1)
    if rc == 0:
        actual = "ok"
    elif rc == 1 and ("violation" in text.lower() or "counterexample" in text.lower() or os.path.exists(itf)):
        actual = "violation"
    elif rc == -1:
        actual = "timeout"
    else:
        actual = "error"
    return actual, secs, cmd, rc, text, itf


def main():
    args = sys.argv[1:]
    out = HERE
    if args and args[0] == "--out":
        out = args[1]; args = args[2:]
    os.makedirs(out, exist_ok=True)
    res_path = os.path.join(out, "results.tsv")
    log_path = os.path.join(out, "run.log")
    if not os.path.exists(res_path):
        with open(res_path, "w") as f:
            f.write("\t".join(FIELDS) + "\n")
    done = set()
    with open(res_path) as f:
        for line in f:
            done.add(line.split("\t", 1)[0])
    log = open(log_path, "a")
    total = 0
    for run in RUNS:
        if run["id"] in done:
            continue
        if args and not any(run["id"].startswith(a) for a in args):
            continue
        if os.path.exists(HOLD_FILE):
            log.write("HOLD file present, stopping before %s\n" % run["id"]); log.flush()
            print("HOLD: stopped"); return
        actual, secs, cmd, rc, text, itf = execute(run, out)
        total += 1
        check_note = ""
        if actual == "violation" and run["id"] in CHECKS and os.path.exists(itf):
            d = json.load(open(itf))
            last = d["states"][-1]
            try:
                good = bool(CHECKS[run["id"]](last))
            except Exception as e:
                good = False; check_note = "; trace-check error: " + repr(e)
            if not good:
                actual = "witness-without-order"
                check_note += "; trace check of the ordered claim failed"
            else:
                check_note = "; trace check of the ordered claim ok"
        match = "yes" if actual == run["expect"] else "NO"
        row = dict(run, overrides="", actual=actual, match=match, secs=secs,
                   file=fname(run["module"]), samples=run["samples"] or "")
        with open(res_path, "a") as f:
            f.write("\t".join(str(row[k]) for k in FIELDS) + "\n")
        log.write("[%s] %s %s %s rc=%s %ss expect=%s actual=%s match=%s%s\n" % (
            time.strftime("%H:%M:%S", time.gmtime()), run["id"], run["module"], run["invariant"],
            rc, secs, run["expect"], actual, match, check_note))
        tail = [l for l in text.splitlines() if l.strip()][-3:]
        log.write("    cmd: " + " ".join(cmd) + "\n    out: " + " | ".join(tail)[:400] + "\n")
        log.flush()
        print(run["id"], actual, secs, match, flush=True)
        if actual == "error" and "connect" in text.lower():
            log.write("server not reachable, stopping\n"); log.flush(); return
    print("done", total)


if __name__ == "__main__":
    main()
