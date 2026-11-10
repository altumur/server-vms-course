#!/usr/bin/env python3
"""Runs the P/02 data models one at a time, strictly sequentially.

Apalache: one server only, started outside this script (port 18828, -Xmx4g).
Results: results.tsv and run.log are appended line by line; ITF traces in runs/.
A HOLD file (see HOLD_FILE) stops new runs. Each instance is generated into instances/NAME.qnt
from the table MODS below (Apalache's JSON limit does not allow all instances in one file).
Usage: run.py [--out DIR] [ID-prefix ...]
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SP = "/tmp/claude-1001/-home-pilot-review103-claude/8c59e25c-bfa6-49af-82e9-3a98557bbf75/scratchpad/p02q"
HOLD_FILE = SP + "/HOLD"
ENDPOINT = "localhost:18828"
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk",
           PATH="/opt/quint/jdk/bin:" + os.environ["PATH"])
TIMEOUT = 900
FIELDS = "id module invariant kind tool max_steps samples overrides expect actual match secs file".split()

# module -> (core module, file, parameter string); parameter strings are recorded verbatim in results.tsv.
R = "put_race.qnt"
def race(n=2, d2=3, d3=3, vf=False, a19=False, clean="norm", post=False, seq=False, crash=False, foreign=False,
         budget=-1, mc=True, enf=True, mid=False, coarse=False):
    fl = lambda b: "true" if b else "false"
    return ("race_core", R, f'N={n}, D2={d2}, D3={d3}, VIEW_FIRST={fl(vf)}, ATOMIC19={fl(a19)}, CLEAN="{clean}", POSTPARTS={fl(post)}, '
            f'SEQ={fl(seq)}, CRASH={fl(crash)}, FOREIGN={fl(foreign)}, BUDGET={budget}, MARK_CAS={fl(mc)}, ENFORCE={fl(enf)}, MID={fl(mid)}, COARSE={fl(coarse)}')

CAT = "catalogue_window.qnt"; OUT = "put_outcome.qnt"; WGT = "put_weight.qnt"; ST = "reader_start.qnt"; MK = "reader_mark.qnt"
HD = "reader_herd.qnt"; PB = "file_publish.qnt"; CS = "put_cost.qnt"
MV = 524288; MB = 1048576  # daemon-flags.tsv:38-39

MODS = {
    # race (C6, view order, C2, C10)
    "race_norm": race(coarse=True),
    "race_atomic19": race(a19=True, coarse=True),
    "race_seq": race(a19=True, seq=True),
    "race_known": race(clean="known", a19=True, coarse=True),
    "race_known_revert": race(clean="known", d2=1, a19=True, coarse=True),
    "race_guard_post": race(clean="guard", post=True, coarse=True),
    "race_guard_post_rev": race(clean="guard", post=True, d2=1, coarse=True),
    "race_mut_guard_only": race(clean="guard", coarse=True),
    "race_mut_post_only": race(post=True, coarse=True),
    "race_nomark_cas": race(a19=True, mc=False),
    "race_fine": race(),
    "race_three_full_rowfirst": race(n=3, d2=3, d3=4, a19=True),
    "race_three_mid_rowfirst": race(n=2, d2=3, d3=4, a19=True, mid=True),
    "race_three_mid_viewfirst": race(n=2, d2=3, d3=4, vf=True, a19=True, mid=True),
    "race_foreign": race(n=1, a19=True, foreign=True),
    "race_foreign_budget": race(n=1, a19=True, foreign=True, budget=3),
    "race_foreign_budget_mut": race(n=1, a19=True, foreign=True, budget=3, enf=False),
    "race_two_budget": race(a19=True, budget=3, coarse=True),
    "race_break": race(d2=2, a19=True, seq=True, crash=True),
    "race_break_other": race(a19=True, seq=True, crash=True),
    # catalogue window (C7)
    "cat_norm": ("cat_core", CAT, "WINDOW=false, REVALIDATE=false, LOCK=false, CRASH=false"),
    "cat_window": ("cat_core", CAT, "WINDOW=true, REVALIDATE=false, LOCK=false, CRASH=false"),
    "cat_recheck": ("cat_core", CAT, "WINDOW=false, REVALIDATE=true, LOCK=false, CRASH=false"),
    "cat_lock": ("cat_core", CAT, "WINDOW=false, REVALIDATE=false, LOCK=true, CRASH=false"),
    "cat_lock_crash": ("cat_core", CAT, "WINDOW=false, REVALIDATE=false, LOCK=true, CRASH=true"),
    # outcome (C3)
    "out_silent": ("out_core", OUT, 'REACT="silent", MEM=true, RERUN=true'),
    "out_silent_nomem": ("out_core", OUT, 'REACT="silent", MEM=false, RERUN=true'),
    "out_ctrl": ("out_core", OUT, 'REACT="ctrl", MEM=true, RERUN=true'),
    "out_ctrl_nomem": ("out_core", OUT, 'REACT="ctrl", MEM=false, RERUN=true'),
    "out_silent_norerun": ("out_core", OUT, 'REACT="silent", MEM=true, RERUN=false'),
    "out_ctrl_norerun": ("out_core", OUT, 'REACT="ctrl", MEM=true, RERUN=false'),
    "out_ctrl_nomem_norerun": ("out_core", OUT, 'REACT="ctrl", MEM=false, RERUN=false'),
    "out_mut_continue": ("out_core", OUT, 'REACT="continue", MEM=true, RERUN=false'),
    # weight (C4, C5)
    "wgt_raised": ("wgt_core", WGT, f"MV=1048576, MB={MB}, ENV=256, PRECHECK=false, NEWDIG=true, CRASH=false, VW=1048500, RW=1000, VE=64, RE=64"),
    "wgt_default_view": ("wgt_core", WGT, f"MV={MV}, MB={MB}, ENV=256, PRECHECK=false, NEWDIG=true, CRASH=false, VW=524288, RW=1000, VE=524288, RE=64"),
    "wgt_row413": ("wgt_core", WGT, f"MV={MV}, MB={MB}, ENV=256, PRECHECK=false, NEWDIG=true, CRASH=false, VW=1000, RW=600000, VE=64, RE=64"),
    "wgt_row413_crash": ("wgt_core", WGT, f"MV={MV}, MB={MB}, ENV=256, PRECHECK=false, NEWDIG=true, CRASH=true, VW=1000, RW=600000, VE=64, RE=64"),
    "wgt_ctrl": ("wgt_core", WGT, f"MV=1048576, MB={MB}, ENV=256, PRECHECK=true, NEWDIG=true, CRASH=false, VW=1048500, RW=1000, VE=64, RE=64"),
    "wgt_ctrl_row": ("wgt_core", WGT, f"MV={MV}, MB={MB}, ENV=256, PRECHECK=true, NEWDIG=true, CRASH=false, VW=1000, RW=600000, VE=64, RE=64"),
    "wgt_ctrl_crash": ("wgt_core", WGT, f"MV={MV}, MB={MB}, ENV=256, PRECHECK=true, NEWDIG=true, CRASH=true, VW=1000, RW=1000, VE=64, RE=64"),
    "wgt_fine": ("wgt_core", WGT, f"MV={MV}, MB={MB}, ENV=256, PRECHECK=false, NEWDIG=true, CRASH=false, VW=1000, RW=1000, VE=64, RE=64"),
    # start (C9, M1)
    "start_mono": ("start_core", ST, 'START_WAIT=60, CLOCK="mono", JUMP=100, DTS=Set(1, 30, 60)'),
    "start_wall_fw": ("start_core", ST, 'START_WAIT=60, CLOCK="wall", JUMP=100, DTS=Set(1, 30, 60)'),
    "start_wall_back": ("start_core", ST, 'START_WAIT=60, CLOCK="wall", JUMP=-100, DTS=Set(1, 30, 60)'),
    # mark (M5, M1)
    "mark_norm": ("mark_core", MK, 'CMP_DIG=false, CLOCK="mono", PERIOD=30, JUMP=-100, DTS=Set(1, 30)'),
    "mark_ctrl": ("mark_core", MK, 'CMP_DIG=true, CLOCK="mono", PERIOD=30, JUMP=-100, DTS=Set(1, 30)'),
    "mark_wall": ("mark_core", MK, 'CMP_DIG=false, CLOCK="wall", PERIOD=30, JUMP=-100, DTS=Set(1, 30, 40)'),
    # herd (C8); the period 30 s scaled to 4, see report
    "herd_norm": ("herd_core", HD, "NP=3, PERIOD=4, STAGGER=0, DOWN=1, OFFSETS=Set(0, 3)"),
    "herd_stagger": ("herd_core", HD, "NP=3, PERIOD=4, STAGGER=5, DOWN=1, OFFSETS=Set(0, 3)"),
    "herd_mut_zero": ("herd_core", HD, "NP=3, PERIOD=4, STAGGER=0, DOWN=1, OFFSETS=Set(0, 3)"),
    # publish (M4)
    "pub_norm": ("pub_core", PB, "FS_EMPTY=true, BARRIER_DATA=false, BARRIER_DIR=false"),
    "pub_noempty": ("pub_core", PB, "FS_EMPTY=false, BARRIER_DATA=false, BARRIER_DIR=false"),
    "pub_ctrl": ("pub_core", PB, "FS_EMPTY=true, BARRIER_DATA=true, BARRIER_DIR=true"),
    "pub_mut_nodata": ("pub_core", PB, "FS_EMPTY=true, BARRIER_DATA=false, BARRIER_DIR=true"),
    "pub_mut_nodir": ("pub_core", PB, "FS_EMPTY=true, BARRIER_DATA=true, BARRIER_DIR=false"),
}

def cost(name, s, p, w, d, c, u):
    fl = "true" if u else "false"
    MODS[name] = ("cost_core", CS, f"S={s}, P={p}, W={w}, D={d}, C={c}, UNCHANGED={fl}")
    return name, s, p, w, d, c, u

COST = [
    cost("cost_s2_p4", 2, 4, 4, 4, 0, False),
    cost("cost_s8_p4", 8, 4, 4, 4, 0, False),
    cost("cost_s64_p4", 64, 4, 4, 4, 0, False),
    cost("cost_s2_p32", 2, 32, 32, 32, 0, False),
    cost("cost_s2_p128", 2, 128, 128, 128, 0, False),
    cost("cost_s8_p128_c3", 8, 128, 128, 128, 3, False),
    cost("cost_s64_p128_unch", 64, 128, 0, 0, 0, True),
]

def v(state, name):
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


def s(state):
    return v(state, "s")


# Ordered-event checks on the LAST state of a witness trace: the claim of the
# witness, re-derived from the trace independently of the Quint predicate.
def cost_check(name, s_, p, w, d, c, u):
    expected_reads = (1 + s_) + 1 + (3 + p) * (c + 1) + (0 if u else 2)
    expected_writes = (w if u else w + (c + 1) + 2)
    def f(st):
        return v(st, "reads") == expected_reads and v(st, "writes") == expected_writes and v(st, "deletes") == d and v(st, "cmp") == s_ * s_
    return f


CHECKS = {
    "R02": lambda st: (x := s(st)) and x["tDel"][1] >= 0 and 0 <= x["tParts"][2] < x["tDel"][1] < x["tRow"][2] and x["rowDig"] == 3 and 3 not in x["parts"],
    "R03": lambda st: (x := s(st)) and x["markRev"] == x["rowRev"] and x["rowDig"] == 3 and 3 not in x["parts"] and x["tDel"][1] >= 0,
    "R04": lambda st: (x := s(st)) and x["rowDig"] == 3 and 3 not in x["parts"],
    "R17": lambda st: (x := s(st)) and x["rowDig"] == 1 and x["markRev"] == x["rowRev"] and 1 not in x["parts"],
    "R33": lambda st: (x := s(st)) and x["viewFell"] and x["viewRev"] < x["rowRev"] and x["viewRev"] < x["markRev"] and x["markRev"] == x["rowRev"],
    "R32": lambda st: (x := s(st)) and x["viewFell"] and 0 <= x["tRow"][2] < x["viewFellAt"],
    "B06": lambda st: (x := s(st)) and x["pc"][1] == "dead" and x["rowRev"] == 3 and x["markRev"] == 3,
    "W02": lambda st: (x := v(st, "cat")) and "a2" in x and "b" in x and "b" not in v(st, "seen")["a"] and "a2" not in v(st, "seen")["b"],
    "G02": lambda st: v(st, "failed") == "view413" and v(st, "rowRev") > v(st, "viewRev"),
    "G08": lambda st: v(st, "failed") == "view413" and v(st, "rowRev") >= 3 and v(st, "markRev") == 1,
    "M04": lambda st: v(st, "markRev") == v(st, "memRev") and v(st, "markDig") != v(st, "memDig") and v(st, "pollsSinceChange") >= 1,
}

RUNS = []
def run(id_, module, inv, kind, expect, steps, tool="verify", samples=""):
    RUNS.append(dict(id=id_, module=module, invariant=inv, kind=kind, expect=expect, max_steps=steps, tool=tool, samples=samples))

V, OK = "violation", "ok"
# --- race: C6 (two installers of one name), depths chosen after the trial
run("R01", "race_norm", "inv_row_names_parts", "witness", V, 8)
run("R02", "race_norm", "wit_foreign_parts_deleted", "witness", V, 9)
run("R03", "race_norm", "wit_published_row_no_parts", "witness", V, 11)
run("R04", "race_atomic19", "inv_row_names_parts", "witness", V, 8)
run("R05", "race_fine", "inv_mark_le_row", "property", OK, 9)
run("R06", "race_fine", "inv_mark_never_fell", "property", OK, 9)
run("R07", "race_fine", "inv_view_never_fell", "property", OK, 9)
run("R08", "race_atomic19", "inv_quiescent_published", "property", OK, 11)
run("R09", "race_seq", "wit_two_installers_finish", "witness", V, 15)
run("R10", "race_atomic19", "wit_lagging_mark_not_lowered", "witness", V, 10)
run("R11", "race_nomark_cas", "inv_mark_never_fell", "mutant", V, 13)
# controls of C6
run("R12", "race_known", "inv_row_names_parts", "control", V, 11)
run("R13", "race_known_revert", "inv_row_names_parts", "control", V, 9)
run("R14", "race_guard_post", "inv_published_whole", "control", OK, 11)
run("R15", "race_guard_post", "inv_row_names_parts", "witness", V, 9)
run("R16", "race_guard_post_rev", "inv_published_whole", "control", OK, 11)
run("R17", "race_known_revert", "inv_published_whole", "control", V, 11)
run("R18", "race_mut_guard_only", "inv_published_whole", "mutant", V, 10)
run("R19", "race_mut_post_only", "inv_row_names_parts", "mutant", V, 10)
run("R20", "race_guard_post", "wit_step19_race", "witness", V, 9)
# view order
run("R30", "race_three_full_rowfirst", "wit_mid_state", "witness", V, 8)
run("R31", "race_three_mid_rowfirst", "inv_view_never_fell", "witness", V, 9)
run("R32", "race_three_mid_rowfirst", "wit_three_install_order", "witness", V, 9)
run("R33", "race_three_mid_rowfirst", "wit_view_fell_mark_row", "witness", V, 11)
run("R34", "race_three_mid_viewfirst", "inv_view_never_fell", "control", OK, 11)
run("R35", "race_three_mid_viewfirst", "inv_mark_le_row", "property", OK, 9)
run("R36", "race_three_mid_rowfirst", "inv_mark_never_fell", "property", OK, 9)
# C2
run("R40", "race_foreign", "wit_conflicts_3", "witness", V, 13)
run("R41", "race_foreign", "wit_conflicts_5", "witness", V, 21)
run("R42", "race_foreign_budget", "inv_conflicts_bounded", "control", OK, 16)
run("R43", "race_foreign_budget", "wit_refused_by_budget", "witness", V, 13)
run("R44", "race_foreign_budget_mut", "inv_conflicts_bounded", "mutant", V, 17)
run("R45", "race_foreign", "inv_mark_le_row", "property", OK, 12)
run("R46", "race_two_budget", "inv_mark_never_fell", "property", OK, 10)
# C10 breaks and recovery (sequential)
run("B01", "race_break", "inv_prev_whole", "property", OK, 10)
run("B02", "race_break", "inv_recovered", "property", OK, 13)
run("B03", "race_break_other", "inv_recovered", "property", OK, 13)
run("B04", "race_break", "wit_row_without_mark_after_break", "witness", V, 7)
run("B05", "race_break", "wit_view_without_mark_after_break", "witness", V, 8)
run("B06", "race_break", "wit_recovery_rev_jumps", "witness", V, 13)
run("B07", "race_break", "wit_recovery_unchanged", "witness", V, 11)
run("B08", "race_break", "wit_old_parts_left_unchanged", "witness", V, 13)
# --- catalogue window (C7)
run("W01", "cat_norm", "inv_catalogue_valid", "witness", V, 8)
run("W02", "cat_norm", "wit_both_checked_clean", "witness", V, 8)
run("W03", "cat_norm", "wit_reader_code2", "witness", V, 8)
run("W04", "cat_window", "inv_catalogue_valid", "property", OK, 10)
run("W05", "cat_window", "wit_second_refused", "witness", V, 6)
run("W06", "cat_recheck", "inv_bad_reported", "control", OK, 10)
run("W07", "cat_recheck", "inv_catalogue_valid", "control", V, 8)
run("W08", "cat_lock", "inv_no_bad_writes_with_lock", "control", OK, 10)
run("W09", "cat_lock_crash", "wit_lock_stuck", "witness", V, 8)
run("W10", "cat_norm", "wit_all_ok_no_report", "witness", V, 8)
# --- outcome (C3, C10 non-conflict)
run("O01", "out_silent", "inv_no_false_success", "witness", V, 10)
run("O02", "out_silent", "wit_code0_row_applied_mark_missing", "witness", V, 10)
run("O03", "out_silent", "wit_code0_parts_only", "witness", V, 8)
run("O04", "out_silent", "inv_mark_le_row", "property", OK, 12)
run("O05", "out_silent", "inv_view_le_row", "property", OK, 12)
run("O06", "out_silent", "inv_parts_before_row", "property", OK, 12)
run("O07", "out_silent", "inv_rerun_converges", "witness", V, 14)
run("O08", "out_ctrl", "inv_no_false_success", "control", OK, 14)
run("O09", "out_ctrl", "inv_rerun_converges", "control", OK, 14)
run("O10", "out_ctrl", "wit_ambiguous_applied_retry", "witness", V, 8)
run("O11", "out_ctrl", "wit_rerun_after_exit1", "witness", V, 16)
run("O12", "out_ctrl_nomem_norerun", "inv_rev_one_step", "witness", V, 14)
run("O13", "out_ctrl_norerun", "inv_rev_one_step", "property", OK, 14)
run("O14", "out_mut_continue", "inv_mark_le_row", "mutant", V, 10)
run("O15", "out_mut_continue", "wit_mark_above_row", "mutant", V, 10)
run("O16", "out_silent_norerun", "inv_rev_one_step", "property", OK, 12)
run("O17", "out_ctrl", "inv_rev_one_step", "witness", V, 14)
# --- weight (C4, C5)
run("G01", "wgt_raised", "inv_nothing_on_toolarge", "witness", V, 8)
run("G02", "wgt_raised", "wit_view413_after_row", "witness", V, 8)
run("G03", "wgt_default_view", "wit_view413_after_row", "witness", V, 8)
run("G04", "wgt_ctrl", "inv_nothing_on_toolarge", "control", OK, 8)
run("G05", "wgt_ctrl", "inv_no_row_without_view", "control", OK, 8)
run("G06", "wgt_ctrl", "wit_refused_precheck", "witness", V, 6)
run("G07", "wgt_raised", "inv_no_row_without_view", "witness", V, 8)
run("G08", "wgt_raised", "wit_rev_climbs", "witness", V, 12)
run("G09", "wgt_row413", "wit_row413_after_parts", "witness", V, 6)
run("G10", "wgt_row413", "inv_orphans_le_1", "witness", V, 14)
run("G11", "wgt_row413", "inv_orphans_le_2", "witness", V, 18)
run("G12", "wgt_ctrl_row", "inv_no_orphan_at_all", "control", OK, 12)
run("G13", "wgt_ctrl_crash", "wit_crash_orphan", "witness", V, 6)
run("G14", "wgt_ctrl_crash", "inv_no_orphan_at_all", "witness", V, 6)
run("G15", "wgt_ctrl_crash", "wit_orphans_cleared", "witness", V, 14)
run("G16", "wgt_fine", "wit_published", "witness", V, 8)
# --- start (C9, M1)
run("T01", "start_mono", "inv_no_serve_unconfirmed", "property", OK, 8)
run("T02", "start_mono", "inv_code1_only_after_wait", "property", OK, 8)
run("T03", "start_mono", "inv_wait_real_bounded", "property", OK, 8)
run("T04", "start_mono", "inv_code2_confirmed", "property", OK, 8)
run("T05", "start_mono", "wit_serve_after_outage", "witness", V, 8)
run("T06", "start_mono", "wit_code1", "witness", V, 8)
run("T07", "start_mono", "wit_code2", "witness", V, 6)
run("T08", "start_wall_fw", "inv_code1_only_after_wait", "witness", V, 6)
run("T09", "start_wall_fw", "wit_wall_jump_premature_code1", "witness", V, 6)
run("T10", "start_wall_back", "inv_wait_real_bounded", "witness", V, 8)
run("T11", "start_wall_back", "wit_wall_jump_long_wait", "witness", V, 8)
# --- mark (M5, M1)
run("M01", "mark_norm", "wit_stale_after_restore_lower", "witness", V, 8)
run("M02", "mark_norm", "wit_new_differs", "witness", V, 9)
run("M03", "mark_norm", "wit_stop_on_rise", "witness", V, 10)
run("M04", "mark_norm", "wit_equal_rev_other_content", "witness", V, 12)
run("M05", "mark_norm", "inv_no_stale_at_equal_rev", "witness", V, 12)
run("M06", "mark_ctrl", "inv_no_stale_at_equal_rev", "control", OK, 14)
run("M07", "mark_ctrl", "wit_stops_on_equal_rev_ctrl", "witness", V, 12)
run("M08", "mark_ctrl", "wit_stale_after_restore_lower", "witness", V, 8)
run("M09", "mark_wall", "wit_poll_delayed_by_backward_jump", "witness", V, 8)
run("M10", "mark_norm", "inv_stop_within_period", "property", OK, 10)
# --- herd (C8)
run("H01", "herd_norm", "wit_all_at_once", "witness", V, 8)
run("H02", "herd_norm", "inv_burst_le_1", "witness", V, 8)
run("H03", "herd_stagger", "inv_burst_le_1", "control", OK, 23)
run("H04", "herd_stagger", "wit_spread_max_one", "witness", V, 23)
run("H05", "herd_mut_zero", "inv_burst_le_1", "mutant", V, 8)
# --- publish (M4)
run("P01", "pub_norm", "inv_no_empty_after_crash", "witness", V, 5)
run("P02", "pub_norm", "wit_empty_file_after_crash", "witness", V, 5)
run("P03", "pub_noempty", "inv_no_empty_after_crash", "property", OK, 6)
run("P04", "pub_norm", "wit_lost_publication", "witness", V, 6)
run("P05", "pub_ctrl", "inv_no_empty_after_crash", "control", OK, 6)
run("P06", "pub_ctrl", "inv_reported_survives", "control", OK, 6)
run("P07", "pub_ctrl", "wit_normal_publish", "witness", V, 6)
run("P08", "pub_mut_nodata", "inv_no_empty_after_crash", "mutant", V, 5)
run("P09", "pub_mut_nodir", "inv_reported_survives", "mutant", V, 6)
# --- cost of manifest put (C1)
for i, c in enumerate(COST, 1):
    name, s_, p, w, d, cc, u = c
    run("K%d" % i, name, "wit_done", "witness", V, 10 + 3 * cc)
    CHECKS["K%d" % i] = cost_check(name, s_, p, w, d, cc, u)
    run("L%d" % i, name, "inv_reads_expected", "property", OK, 10 + 3 * cc)
    run("Q%d" % i, name, "inv_writes_expected", "property", OK, 10 + 3 * cc)
# --- simulation, secondary evidence only (one thread, sequential)
run("Z01", "race_norm", "inv_mark_never_fell", "property", OK, 40, "run", 3000)
run("Z02", "race_norm", "inv_mark_le_row", "property", OK, 40, "run", 3000)
run("Z03", "race_guard_post", "inv_published_whole", "control", OK, 40, "run", 3000)
run("Z04", "race_guard_post_rev", "inv_published_whole", "control", OK, 40, "run", 3000)
run("Z05", "race_three_mid_viewfirst", "inv_view_never_fell", "control", OK, 40, "run", 3000)
run("Z06", "race_break", "inv_recovered", "property", OK, 40, "run", 3000)
run("Z07", "race_known", "inv_row_names_parts", "control", OK, 40, "run", 3000)


def module_file(module):
    core, f, params = MODS[module]
    os.makedirs(os.path.join(HERE, "instances"), exist_ok=True)
    path = os.path.join(HERE, "instances", module + ".qnt")
    base = f[:-4]
    text = f'module {module} {{\n  import {core}({params}).* from "../{base}"\n}}\n'
    if not os.path.exists(path) or open(path).read() != text:
        open(path, "w").write(text)
    return path


def execute(run, out):
    os.makedirs(os.path.join(out, "runs"), exist_ok=True)
    qnt = module_file(run["module"])
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
        row = dict(run, overrides=MODS[run["module"]][2], actual=actual, match=match, secs=secs,
                   file=MODS[run["module"]][1], samples=run["samples"] or "")
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
