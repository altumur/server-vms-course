#!/usr/bin/env python3
"""Runs the P/07 models one at a time, strictly sequentially (form copied from the P/02 data project).

Apalache: one server only, started outside this script (port 18828, -Xmx4g).
Results: results.tsv and run.log are appended line by line; ITF traces in runs/.
HOLD file stops new runs. Each instance is generated into instances/NAME.qnt from MODS.
Usage: run.py [--out DIR] [ID-prefix ...]
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SP = "/tmp/claude-1001/-home-pilot-review103-claude/8c59e25c-bfa6-49af-82e9-3a98557bbf75/scratchpad/p07q"
HOLD_FILE = SP + "/HOLD"
ENDPOINT = "localhost:18828"
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk", PATH="/opt/quint/jdk/bin:" + os.environ["PATH"])
TIMEOUT = 900
FIELDS = "id module invariant kind tool max_steps samples overrides expect actual match secs file".split()
fl = lambda b: "true" if b else "false"

def load(policy, nc=3, nw=2, hang=False, dl=False, rearm=False, dele=False):
    return ("load_core", "load_overlap.qnt", f'POLICY="{policy}", NC={nc}, NW={nw}, HANG={fl(hang)}, DEADLINE={fl(dl)}, REARM={fl(rearm)}, DEL={fl(dele)}')
def api(door, rule, ifm=True, key=False, late=False, fo=False, same=False):
    return ("api_core", "api_outcome.qnt", f'DOOR="{door}", IFMATCH={fl(ifm)}, KEY={fl(key)}, LATE={fl(late)}, RULE="{rule}", FOREIGN={fl(fo)}, FOREIGN_SAME={fl(same)}')
def deadline(t, ont, rule, ds="Set(90)", gw=100, lost=False, maxt=200, bound=150):
    return ("deadline_core", "door_deadline.qnt", f'T={t}, ONTIMEOUT="{ont}", RULE="{rule}", DS={ds}, GW={gw}, LOST={fl(lost)}, MAXT={maxt}, BOUND={bound}')
def sess(policy, shared=True, ct=True, age=False, idk="named", keep=False, reload_=False):
    return ("session_core", "retry_session.qnt", f'POLICY="{policy}", SHARED={fl(shared)}, CANCEL_TOAST={fl(ct)}, AGE_LIMIT={fl(age)}, IDKIND="{idk}", KEEP_EXP={fl(keep)}, RELOAD={fl(reload_)}')
def budget(kinds='Set("409")', lats="Set(0)", ras="Set()", cap=-1, pol="refuse", bud=-1, lim=3600):
    return ("budget_core", "retry_budget.qnt", f'KINDS={kinds}, LATS={lats}, RAS={ras}, CAP={cap}, POLICY409="{pol}", BUDGET={bud}, TAKEOVER=30, LIM={lim}')
def storm(reconn=5, down=1, stag=0, lane=2, nt=3):
    return ("storm_core", "storm.qnt", f'NT={nt}, RECONN={reconn}, DOWN={down}, STAGGER={stag}, PERIOD=5, LANE={lane}, OFFSETS=Set(1, 2, 3)')
def backoff(period=5, ra=10, follow=False):
    return ("backoff_core", "read_backoff.qnt", f'PERIOD={period}, RA={ra}, FOLLOW={fl(follow)}')
def walk(pages=3, fault="none", det="none", bud=-1, lim=4):
    return ("walk_core", "domain_walk.qnt", f'PAGES={pages}, FAULT="{fault}", DETECT="{det}", BUDGET={bud}, LIM={lim}, POLL=5')
def stall(dl=-1, parse="empty_ok", mark=False, up=False, lim=4):
    return ("stall_core", "read_stall.qnt", f'K=3, DEADLINE={dl}, PARSE="{parse}", MARK={fl(mark)}, MANIFEST_UP={fl(up)}, MAXT=20, LIM={lim}')
def conn(nt=2, l=2, pick="fifo", timer="call", mh=-1, dur=6, gap=1):
    return ("conn_core", "conn_limit.qnt", f'NT={nt}, L={l}, PICK="{pick}", TIMER="{timer}", MAX_HELD={mh}, DUR={dur}, CALLS=Set(1), OFFSETS=Set(15), WAIT=15, GAP={gap}, DEADLINE=20')
def lead(atomic=False, lease=False):
    return ("leader_core", "feed_leader.qnt", f'NT=2, ATOMIC={fl(atomic)}, LEASE={fl(lease)}')
def mount(policy):
    return ("mount_core", "mount_life.qnt", f'POLICY="{policy}", NM=2')
def clock(c="mono", jump=0, t=20, d=1000, skew=0, age="server_time", slp=0, waf=False):
    return ("clock_core", "timer_clock.qnt", f'CLOCK="{c}", JUMP={jump}, T={t}, D={d}, SKEW={skew}, AGE="{age}", SLEEP={slp}, WAKE_ANSWER_FIRST={fl(waf)}')
def cost(s, sc, pf, f, pg, sh, m):
    return ("cost_core", "cycle_cost.qnt", f'S={s}, SC={sc}, PF={pf}, F={f}, PG={pg}, SH={sh}, M={m}')

MODS = {
    "load_free": load("free"),
    "load_latest": load("latest"),
    "load_revguard": load("revguard"),
    "load_revguard_del": load("revguard", dele=True),
    "load_single": load("single"),
    "load_single_nomerge": load("single_nomerge"),
    "load_single_hang": load("single", hang=True),
    "load_free_hang": load("free", hang=True),
    "load_single_dl_rearm": load("single", hang=True, dl=True, rearm=True),
    "load_single_dl_norearm": load("single", hang=True, dl=True, rearm=False),
    "api_val_late": api("put", "value_eq", late=True),
    "api_val": api("put", "value_eq"),
    "api_val_foreign": api("put", "value_eq", fo=True),
    "api_rev_foreign": api("put", "rev_moved", fo=True),
    "api_pos_late_same": api("put", "positive_only", late=True, fo=True, same=True),
    "api_pos_late": api("put", "positive_only", late=True, fo=True),
    "api_unk_late_same": api("put", "unknown", late=True, fo=True, same=True),
    "api_marks_val": api("marks", "value_eq", late=True, fo=True, same=True, ifm=False),
    "api_marks_unk": api("marks", "unknown", late=True, fo=True, same=True, ifm=False),
    "api_put_unk_nokey": api("put", "unknown"),
    "api_put_unk_key": api("put", "unknown", key=True, late=True, fo=True),
    "api_put_unk_noifm": api("put", "unknown", ifm=False),
    "dl_20_refused": deadline(20, "refused", "naive"),
    "dl_20_reread_naive": deadline(20, "unknown_reread", "naive", lost=True),
    "dl_20_reread_after": deadline(20, "unknown_reread", "afterdl", lost=True),
    "dl_none_lost": deadline(-1, "refused", "naive", lost=True),
    "dl_none": deadline(-1, "refused", "naive"),
    "dl_105": deadline(105, "unknown_reread", "naive", lost=True, bound=105),
    "dl_95": deadline(95, "unknown_reread", "naive", lost=True, bound=95),
    "dl_90": deadline(90, "unknown_reread", "naive", lost=True, bound=90),
    "dl_105_ok": deadline(105, "unknown_reread", "naive", ds="Set(1, 90)", lost=False, bound=105),
    "s_norm_shared": sess("norm"),
    "s_norm_noshare": sess("norm", shared=False),
    "s_cancel_shared": sess("cancel_seen"),
    "s_cancel_noshare": sess("cancel_seen", shared=False),
    "s_cancel_notoast": sess("cancel_seen", shared=False, ct=False),
    "s_recheck_shared": sess("recheck"),
    "s_bound_shared": sess("bound"),
    "s_cancel_numeric_exp": sess("cancel_seen", shared=False, idk="numeric", keep=True),
    "s_norm_named_exp": sess("norm", idk="named", keep=True),
    "s_age_numeric_exp": sess("cancel_seen", shared=False, age=True, idk="numeric", keep=True),
    "s_reload_numeric": sess("cancel_seen", shared=False, age=True, idk="numeric", reload_=True),
    "s_reload_named": sess("norm", idk="named", reload_=True),
    "b_m5": budget(),
    "b_m5_unknown": budget(pol="unknown"),
    "b_ra15": budget(ras="Set(15)"),
    "b_ra15_bud20": budget(ras="Set(15)", bud=20, pol="unknown"),
    "b_ra15_bud60": budget(ras="Set(15)", bud=60, pol="unknown"),
    "b_timeouts": budget(kinds='Set("409", "lost")', lats="Set(0, 20)"),
    "b_huge": budget(kinds='Set("503")', ras="Set(3600)", lim=3600),
    "b_huge_cap10": budget(kinds='Set("503")', ras="Set(3600)", cap=10, lim=30),
    "b_ra1": budget(kinds='Set("503")', ras="Set(1)"),
    "b_ra15_cap5": budget(ras="Set(15)", cap=5),
    "b_ra15_cap10": budget(ras="Set(15)", cap=10),
    "st_norm": storm(),
    "st_reconn1": storm(reconn=1),
    "st_down7": storm(down=7),
    "st_stag": storm(stag=2),
    "st_mut": storm(stag=0),
    "ba_norm": backoff(),
    "ba_follow": backoff(follow=True),
    "ba_ra1": backoff(ra=1),
    "w_none_repeat": walk(fault="repeat"),
    "w_none_clean": walk(),
    "w_last_repeat": walk(fault="repeat", det="last"),
    "w_last_cycle": walk(fault="cycle", det="last"),
    "w_set_cycle": walk(fault="cycle", det="set"),
    "w_bud5_cycle": walk(fault="cycle", bud=5, lim=5),
    "w_bud2_clean": walk(bud=2),
    "w_bud5_clean": walk(bud=5, lim=5),
    "w_bud5_set_cycle": walk(fault="cycle", det="set", bud=5, lim=5),
    "w_none_cycle": walk(fault="cycle"),
    "r_text": stall(),
    "r_ctrl_parse": stall(parse="refuse"),
    "r_ctrl_dl": stall(dl=3, parse="refuse"),
    "r_ctrl_mark": stall(dl=3, parse="refuse", mark=True),
    "c_norm": conn(),
    "c_l3": conn(l=3),
    "c_dur1": conn(dur=1),
    "c_any": conn(pick="any", dur=1, gap=0),
    "c_any_start": conn(pick="any", timer="start", dur=1, gap=0),
    "c_held1": conn(mh=1),
    "c_mut_held_eq_l": conn(mh=2),
    "f_nonatomic": lead(),
    "f_atomic": lead(atomic=True),
    "f_atomic_lease": lead(atomic=True, lease=True),
    "m_norm": mount("norm"),
    "m_refuse": mount("refuse"),
    "m_replace": mount("replace"),
    "k_wall_up": clock("wall", jump=100, d=25),
    "k_mono_up": clock("mono", jump=100, d=25),
    "k_wall_down": clock("wall", jump=-100),
    "k_mono_down": clock("mono", jump=-100),
    "k_age_browser": clock(age="browser", skew=30, d=25),
    "k_age_server": clock(age="server_time", skew=30, d=25),
    "k_sleep": clock(d=25, slp=60),
    "k_sleep_ctrl": clock(d=25, slp=60, waf=True),
    "q_small": cost(1, 1, 0, 0, 1, 1, 0),
    "q_mid": cost(4, 8, 3, 1, 2, 8, 0),
    "q_feed": cost(2, 2, 0, 0, 1, 2, 2),
}

def v(state, name):
    for k, x in state.items():
        if k == name or k.endswith("::" + name):
            return dec(x)
    raise KeyError(name)

def dec(x):
    if isinstance(x, dict):
        if "#bigint" in x: return int(x["#bigint"])
        if "#map" in x: return {dec(a): dec(b) for a, b in x["#map"]}
        if "#set" in x: return [dec(a) for a in x["#set"]]
        if "#tup" in x: return tuple(dec(a) for a in x["#tup"])
        return {k: dec(a) for k, a in x.items()}
    return x

def s(st): return v(st, "s")

CHECKS = {
    "L02": lambda st: (x := s(st)) and x["sv"] >= 1 and x["shownSeq"] < x["sv"] and x["inflight"] == 0 and not x["dirty"] and x["rolledBack"],
    "L18": lambda st: (x := s(st)) and x["hungN"] >= 1 and x["pendingMerge"] and x["sv"] > x["shownSeq"],
    "L22": lambda st: (x := s(st)) and x["startsAfterHang"] >= 1,
    "A01": lambda st: (x := s(st)) and x["report"] == "not_applied" and x["effects"] == 1 and x["readDone"],
    "A04": lambda st: (x := s(st)) and x["report"] == "not_applied" and x["effects"] == 1 and x["rowVal"] == 2,
    "A05": lambda st: (x := s(st)) and x["report"] == "applied" and x["effects"] == 0 and x["foreignDone"],
    "A12": lambda st: (x := s(st)) and x["report"] == "applied" and x["effects"] == 0 and x["marks"] >= 1,
    "A15": lambda st: (x := s(st)) and x["report"] == "conflict" and x["effects"] >= 1 and not x["foreignDone"],
    "D01": lambda st: (x := s(st)) and x["t"] == 20 and x["report"] == "not_handed" and x["door"] == "run",
    "D03": lambda st: (x := s(st)) and x["report"] == "not_handed" and x["door"] == "run" and x["rereadAt"] >= 20,
    "D10": lambda st: (x := s(st)) and x["report"] == "not_handed" and x["door"] == "run" and x["rereadAt"] >= 90,
    "S01": lambda st: (x := s(st)) and x["cross"] and x["rowBy"] == "B",
    "S03": lambda st: (x := s(st)) and x["cross"] and x["seen"] == "A",
    "S06": lambda st: (x := s(st)) and x["cross"],
    "S08": lambda st: (x := s(st)) and x["rows"] == 2 and x["memExpired"],
    "B01": lambda st: (x := s(st)) and x["t"] == 10 and x["report"] == "refused409",
    "B06": lambda st: (x := s(st)) and x["report"] == "ok" and x["t"] >= 30,
    "B08": lambda st: (x := s(st)) and x["t"] >= 3600,
    "B10": lambda st: (x := s(st)) and x["t"] == 3 and x["report"] in ("unknown", "refused409"),
    "H02": lambda st: v(st, "feedBurst") == 3,
    "H05": lambda st: v(st, "feedBurst") == 3 and v(st, "firstUpTick") == 10,
    "C01": lambda st: (x := s(st)) and x["w"] == "timeout" and x["callAt"] == 1 and x["startAt"] >= 14,
    "C02": lambda st: (x := s(st)) and x["w"] == "run" and x["startAt"] - x["callAt"] >= 14,
    "Q1": lambda st: v(st, "req") == 13,
    "Q2": lambda st: v(st, "req") == 35,
    "Q3": lambda st: v(st, "req") == 48,
    "C08": lambda st: (x := s(st)) and x["w"] == "queued" and x["t"] - x["callAt"] >= 20,
    "F01": lambda st: sum(1 for b in s(st)["holder"].values() if b) == 2,
    "W01": lambda st: (x := s(st)) and x["pages"] == 5 and x["status"] == "walk",
    "K07": lambda st: (x := s(st)) and x["st"] == "timeout" and x["t"] >= 25,
}

RUNS = []
def run(id_, module, inv, kind, expect, steps, tool="verify", samples=""):
    RUNS.append(dict(id=id_, module=module, invariant=inv, kind=kind, expect=expect, max_steps=steps, tool=tool, samples=samples))
V, OK = "violation", "ok"

# load overlap (C3)
run("L01", "load_free", "inv_no_rollback", "witness", V, 8)
run("L02", "load_free", "inv_quiescent_fresh", "witness", V, 8)
run("L03", "load_free", "wit_rollback_quiescent", "witness", V, 8)
run("L04", "load_free", "wit_heal", "witness", V, 11)
run("L05", "load_free", "inv_inflight_le1", "witness", V, 3)
run("L06", "load_free", "wit_inflight_all", "witness", V, 4)
run("L07", "load_latest", "inv_no_rollback", "control", OK, 12)
run("L08", "load_latest", "inv_quiescent_fresh", "control", OK, 12)
run("L09", "load_latest", "wit_latest_starves", "witness", V, 9)
run("L10", "load_revguard", "inv_no_rollback", "control", OK, 12)
run("L11", "load_revguard_del", "inv_no_rollback", "witness", V, 9)
run("L12", "load_revguard_del", "inv_quiescent_fresh", "witness", V, 9)
run("L13", "load_revguard_del", "wit_deletion_rollback", "witness", V, 9)
run("L14", "load_single", "inv_no_rollback", "control", OK, 14)
run("L15", "load_single", "inv_inflight_le1", "control", OK, 14)
run("L16", "load_single", "inv_quiescent_fresh", "control", OK, 14)
run("L17", "load_single_nomerge", "inv_quiescent_fresh", "mutant", V, 8)
run("L18", "load_single_hang", "wit_stuck_after_hang", "witness", V, 6)
run("L19", "load_single_hang", "inv_no_start_after_hang", "property", OK, 12)
run("L20", "load_free_hang", "wit_free_continues_after_hang", "witness", V, 4)
run("L21", "load_free_hang", "wit_hung_grow", "witness", V, 5)
run("L22", "load_single_dl_rearm", "inv_no_start_after_hang", "control", V, 7)
run("L23", "load_single_dl_rearm", "inv_quiescent_fresh", "control", OK, 14)
run("L24", "load_single_dl_norearm", "inv_quiescent_fresh", "mutant", V, 6)
run("L25", "load_single_dl_rearm", "inv_no_rollback", "control", OK, 14)
run("L26", "load_single", "wit_fresh_after_write", "witness", V, 10)
# outcome (C7, M6)
run("A01", "api_val_late", "inv_no_false_not_applied", "witness", V, 6)
run("A02", "api_val_late", "wit_late_after_read", "witness", V, 6)
run("A03", "api_val", "inv_no_false_not_applied", "property", OK, 8)
run("A04", "api_val_foreign", "inv_no_false_not_applied", "witness", V, 7)
run("A05", "api_rev_foreign", "inv_no_false_applied", "witness", V, 6)
run("A06", "api_pos_late_same", "inv_no_false_applied", "witness", V, 6)
run("A07", "api_pos_late", "inv_no_false_applied", "control", OK, 9)
run("A08", "api_pos_late", "inv_no_false_not_applied", "control", OK, 9)
run("A09", "api_pos_late", "wit_unknown_while_applied", "witness", V, 7)
run("A10", "api_unk_late_same", "inv_no_false_applied", "control", OK, 9)
run("A11", "api_unk_late_same", "inv_no_false_not_applied", "control", OK, 9)
run("A12", "api_marks_val", "inv_no_false_applied", "witness", V, 6)
run("A13", "api_marks_unk", "inv_no_false_applied", "control", OK, 9)
run("A14", "api_marks_unk", "inv_one_effect", "witness", V, 7)
run("A15", "api_put_unk_nokey", "wit_own_412", "witness", V, 7)
run("A16", "api_put_unk_key", "wit_own_412", "control", OK, 10)
run("A17", "api_put_unk_key", "inv_one_effect", "control", OK, 10)
run("A18", "api_put_unk_noifm", "inv_one_effect", "witness", V, 7)
# deadlines (C6)
run("D01", "dl_20_refused", "inv_no_false_not_handed", "witness", V, 4)
run("D02", "dl_20_refused", "wit_not_handed_while_running", "witness", V, 4)
run("D03", "dl_20_reread_naive", "inv_no_false_not_handed", "witness", V, 6)
run("D04", "dl_20_reread_after", "inv_no_false_not_handed", "control", OK, 10)
run("D05", "dl_none_lost", "inv_wait_bounded", "witness", V, 6)
run("D06", "dl_none", "inv_wait_bounded", "property", OK, 10)
run("D07", "dl_105", "inv_no_false_not_handed", "control", OK, 10)
run("D08", "dl_105", "inv_wait_bounded", "control", OK, 10)
run("D09", "dl_20_reread_after", "wit_unknown_end", "witness", V, 10)
run("D10", "dl_90", "inv_no_false_not_handed", "mutant", V, 8)
run("D11", "dl_95", "inv_no_false_not_handed", "control", OK, 10)
run("D12", "dl_105_ok", "wit_handed", "witness", V, 8)
# session (C8)
run("S01", "s_norm_shared", "inv_no_cross", "witness", V, 4)
run("S02", "s_norm_noshare", "inv_no_cross", "witness", V, 5)
run("S03", "s_cancel_shared", "wit_cross_before_seen", "witness", V, 4)
run("S04", "s_cancel_noshare", "inv_no_cross", "control", OK, 8)
run("S05", "s_cancel_notoast", "inv_no_cross", "mutant", V, 8)
run("S06", "s_recheck_shared", "inv_no_cross", "witness", V, 5)
run("S07", "s_bound_shared", "inv_no_cross", "control", OK, 8)
run("S08", "s_cancel_numeric_exp", "wit_double_after_expiry", "witness", V, 7)
run("S09", "s_norm_named_exp", "inv_one_row", "property", OK, 8)
run("S10", "s_age_numeric_exp", "inv_one_row", "control", OK, 10)
run("S11", "s_reload_numeric", "inv_one_row", "witness", V, 6)
run("S12", "s_reload_named", "inv_one_row", "property", OK, 8)
run("S13", "s_cancel_numeric_exp", "inv_one_row", "mutant", V, 7)
run("S14", "s_cancel_noshare", "wit_completed", "witness", V, 6)
# budget (M5, C9)
run("B01", "b_m5", "wit_exhaust_before_takeover", "witness", V, 8)
run("B02", "b_m5", "inv_never_auto_ok", "property", OK, 9)
run("B03", "b_m5", "inv_no_refused409", "witness", V, 8)
run("B04", "b_m5_unknown", "inv_no_refused409", "control", OK, 10)
run("B05", "b_m5_unknown", "wit_manual_ok", "witness", V, 9)
run("B06", "b_ra15", "wit_auto_ok", "witness", V, 7)
run("B07", "b_timeouts", "wit_auto_ok", "witness", V, 6)
run("B08", "b_huge", "wit_huge", "witness", V, 7)
run("B09", "b_huge_cap10", "inv_total_le_lim", "control", OK, 9)
run("B10", "b_ra1", "wit_faster_than_default", "witness", V, 8)
run("B11", "b_ra15_bud20", "wit_budget_ends_unknown", "witness", V, 7)
run("B12", "b_ra15_bud20", "inv_never_auto_ok", "control", OK, 9)
run("B13", "b_ra15_bud60", "wit_auto_ok", "witness", V, 7)
run("B14", "b_ra15_cap5", "inv_never_auto_ok", "control", OK, 9)
run("B15", "b_ra15_cap10", "wit_auto_ok", "witness", V, 8)
# storm (C9)
run("H01", "st_norm", "inv_feed_burst_eq_nt", "property", OK, 10)
run("H02", "st_norm", "wit_all_at_once", "witness", V, 7)
run("H03", "st_reconn1", "wit_all_at_once", "witness", V, 7)
run("H04", "st_reconn1", "inv_feed_burst_eq_nt", "property", OK, 10)
run("H05", "st_down7", "wit_all_at_once", "witness", V, 12)
run("H06", "st_norm", "inv_no_busy", "witness", V, 7)
run("H07", "st_stag", "inv_feed_burst_le_1", "control", OK, 13)
run("H08", "st_stag", "wit_all_loaded_spread", "witness", V, 11)
run("H09", "st_mut", "inv_feed_burst_le_1", "mutant", V, 7)
run("H10", "ba_norm", "inv_follows_ra", "witness", V, 3)
run("H11", "ba_follow", "inv_follows_ra", "control", OK, 6)
run("H12", "ba_ra1", "inv_follows_ra", "property", OK, 6)
# walk (C5)
run("W01", "w_none_repeat", "inv_pages_le_lim", "witness", V, 7)
run("W02", "w_none_clean", "wit_over_poll", "witness", V, 4)
run("W03", "w_none_clean", "inv_no_false_fail", "property", OK, 6)
run("W04", "w_none_clean", "inv_done_all", "property", OK, 6)
run("W05", "w_last_repeat", "inv_pages_le_lim", "control", OK, 7)
run("W06", "w_last_cycle", "inv_pages_le_lim", "mutant", V, 7)
run("W07", "w_set_cycle", "inv_pages_le_lim", "control", OK, 7)
run("W08", "w_bud5_cycle", "inv_pages_le_lim", "control", OK, 8)
run("W09", "w_bud2_clean", "inv_no_false_fail", "mutant", V, 4)
run("W10", "w_bud5_clean", "inv_no_false_fail", "control", OK, 6)
run("W11", "w_bud5_clean", "inv_done_all", "control", OK, 6)
run("W12", "w_bud5_set_cycle", "inv_no_false_fail", "property", OK, 7)
run("W13", "w_none_cycle", "inv_pages_le_lim", "mutant", V, 7)
run("W14", "w_bud5_clean", "wit_done", "witness", V, 6)
# stall (C2, M3)
run("R01", "r_text", "inv_no_empty_on_damage", "witness", V, 3)
run("R02", "r_ctrl_parse", "inv_no_empty_on_damage", "control", OK, 8)
run("R03", "r_text", "inv_wait_bounded", "witness", V, 8)
run("R04", "r_ctrl_dl", "inv_wait_bounded", "control", OK, 12)
run("R05", "r_text", "wit_ready_pending", "witness", V, 10)
run("R06", "r_ctrl_dl", "inv_mark_honest", "mutant", V, 8)
run("R07", "r_ctrl_mark", "inv_mark_honest", "control", OK, 10)
run("R08", "r_text", "wit_busy_card_behind", "witness", V, 8)
# connections (C10)
run("C01", "c_norm", "inv_no_false_timeout", "witness", V, 12)
run("C02", "c_norm", "wit_waited_full", "witness", V, 9)
run("C03", "c_l3", "inv_no_false_timeout", "control", OK, 14)
run("C04", "c_l3", "inv_start_at_once", "control", OK, 14)
run("C05", "c_dur1", "inv_no_false_timeout", "property", OK, 14)
run("C06", "c_dur1", "inv_queue_le_wait", "property", OK, 14)
run("C07", "c_any", "inv_no_false_timeout", "witness", V, 14)
run("C08", "c_any", "wit_starved", "witness", V, 14)
run("C09", "c_any_start", "inv_no_false_timeout", "control", OK, 14)
run("C10", "c_any_start", "wit_starved", "witness", V, 14)
run("C11", "c_held1", "inv_no_false_timeout", "control", OK, 14)
run("C12", "c_held1", "inv_start_at_once", "control", OK, 14)
run("C13", "c_mut_held_eq_l", "inv_no_false_timeout", "mutant", V, 12)
run("C14", "c_held1", "wit_write_done", "witness", V, 8)
# leader (C10 proposal)
run("F01", "f_nonatomic", "inv_one_holder", "witness", V, 6)
run("F02", "f_atomic", "inv_one_holder", "control", OK, 8)
run("F03", "f_atomic", "wit_no_holder_after_close", "witness", V, 4)
run("F04", "f_atomic", "inv_takeover_impossible", "property", OK, 8)
run("F05", "f_atomic_lease", "wit_takeover", "witness", V, 5)
# mount (M1)
run("M01", "m_norm", "inv_one_instance", "witness", V, 3)
run("M02", "m_norm", "wit_two_feeds", "witness", V, 3)
run("M03", "m_norm", "inv_no_leak_after_remove", "witness", V, 3)
run("M04", "m_refuse", "inv_one_instance", "control", OK, 5)
run("M05", "m_replace", "inv_no_leak_after_remove", "control", OK, 5)
run("M06", "m_refuse", "inv_no_leak_after_remove", "mutant", V, 3)
# clocks (M4)
run("K01", "k_wall_up", "inv_no_premature", "witness", V, 4)
run("K02", "k_mono_up", "inv_no_premature", "property", OK, 8)
run("K03", "k_wall_down", "inv_wait_bounded", "witness", V, 9)
run("K04", "k_mono_down", "inv_wait_bounded", "property", OK, 9)
run("K05", "k_age_browser", "inv_age_exact", "witness", V, 3)
run("K06", "k_age_server", "inv_age_exact", "control", OK, 5)
run("K07", "k_sleep", "inv_no_false_timeout", "witness", V, 7)
run("K08", "k_sleep_ctrl", "inv_no_false_timeout", "control", OK, 7)
# cost (C4)
for i, (m, depth) in enumerate([("q_small", 15), ("q_mid", 36), ("q_feed", 50)], 1):
    run("Q%d" % i, m, "wit_done", "witness", V, depth)
    run("Y%d" % i, m, "inv_req_expected", "property", OK, depth)
# secondary simulation, one thread
run("Z01", "load_single", "inv_no_rollback", "control", OK, 30, "run", 3000)
run("Z02", "load_single", "inv_quiescent_fresh", "control", OK, 30, "run", 3000)
run("Z03", "load_latest", "inv_no_rollback", "control", OK, 30, "run", 3000)
run("Z04", "s_bound_shared", "inv_no_cross", "control", OK, 25, "run", 3000)
run("Z05", "s_cancel_noshare", "inv_no_cross", "control", OK, 25, "run", 3000)
run("Z06", "api_unk_late_same", "inv_no_false_not_applied", "control", OK, 25, "run", 3000)


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
    if os.path.exists(itf): os.remove(itf)
    if run["tool"] == "verify":
        cmd = ["quint", "verify", "--server-endpoint", ENDPOINT, "--main", run["module"], "--max-steps", str(run["max_steps"]),
               "--invariant", run["invariant"], "--out-itf", itf, qnt]
    else:
        cmd = ["quint", "run", "--backend=rust", "--n-threads=1", "--main", run["module"], "--max-samples", str(run["samples"]),
               "--max-steps", str(run["max_steps"]), "--invariant", run["invariant"], qnt]
    t0 = time.time()
    try:
        cp = subprocess.run(cmd, cwd=SP, env=ENV, capture_output=True, text=True, timeout=TIMEOUT)
        rc, text = cp.returncode, cp.stdout + cp.stderr
    except subprocess.TimeoutExpired as e:
        rc, text = -1, "TIMEOUT " + str(e)
    secs = round(time.time() - t0, 1)
    low = text.lower()
    if rc == 0 and ("no violation" in low or "ok" in low):
        actual = "ok"
    elif "found a counterexample" in low or "found an issue" in low or (rc == 1 and "violation" in low and "no violation" not in low):
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
        if actual == "violation" and run["id"] in CHECKS:
            if os.path.exists(itf):
                d = json.load(open(itf))
                last = d["states"][-1]
                try:
                    good = bool(CHECKS[run["id"]](last))
                except Exception as e:
                    good = False; check_note = "; trace-check error: " + repr(e)
                if not good:
                    actual = "witness-without-order"
                    check_note += "; trace check failed"
                else:
                    check_note = "; trace check ok"
            else:
                actual = "no-trace"; check_note = "; no ITF"
        match = "yes" if actual == run["expect"] else "NO"
        row = dict(run, overrides=MODS[run["module"]][2], actual=actual, match=match, secs=secs, file=MODS[run["module"]][1], samples=run["samples"] or "")
        with open(res_path, "a") as f:
            f.write("\t".join(str(row[k]) for k in FIELDS) + "\n")
        log.write("[%s] %s %s %s rc=%s %ss expect=%s actual=%s match=%s%s\n" % (time.strftime("%H:%M:%S", time.gmtime()), run["id"], run["module"], run["invariant"], rc, secs, run["expect"], actual, match, check_note))
        tail = [l for l in text.splitlines() if l.strip()][-3:]
        log.write("    cmd: " + " ".join(cmd) + "\n    out: " + " | ".join(tail)[:400] + "\n")
        log.flush()
        print(run["id"], actual, secs, match, flush=True)
        if actual == "error" and "connect" in text.lower():
            log.write("server not reachable, stopping\n"); log.flush(); return
    print("done", total)

if __name__ == "__main__":
    main()
