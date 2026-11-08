// Сформировано gen_traces.py из Platform/03-worker/forms/*.traces.tsv на срезе 244355d1. Не редактировать вручную.
module traces_no_back {
  import p03_forms(MUT_FORM="no_back_after_loss").* from "./p03_forms"

  action check(c: bool): bool = all { assert(c), cw' = cw, tc' = tc, io' = io }

  run t_cw_first_waiting_no_name_taken = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwObserveA(false, false, true, 100))
    .then(check(io == [{ name: "publish", strs: ["waiting"], nums: [100, 100] }] and cw.since == 100))
    .then(cwObserveA(false, false, true, 110))
    .then(check(io == [{ name: "publish", strs: ["waiting"], nums: [100, 110] }] and cw.since == 100))
    .then(cwAcq)
    .then(check(cw.st == "holding" and io == []))

  run t_cw_refused_before_first_capture = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwObserveA(false, true, true, 100))
    .then(check(io == [{ name: "publish", strs: ["refused"], nums: [100, 100] }]))
    .then(cwLo)
    .then(check(io == [] and cw.lostEp == false))
    .then(cwAcq)
    .then(check(cw.st == "holding" and io == []))

  run t_cw_refused_priority_after_loss = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwAcq)
    .then(check(cw.st == "holding" and io == []))
    .then(cwLo)
    .then(check(io == [{ name: "name_taken", strs: [], nums: [] }] and cw.st == "seeking"))
    .then(cwObserveA(false, true, true, 120))
    .then(check(io == [{ name: "publish", strs: ["refused"], nums: [120, 120] }]))
    .then(cwObserveA(false, false, true, 130))
    .then(check(io == [{ name: "publish", strs: ["nameless"], nums: [130, 130] }]))

  run t_cw_same_state_since_survives_clock_backward = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwObserveA(false, false, true, 100))
    .then(check(io == [{ name: "publish", strs: ["waiting"], nums: [100, 100] }]))
    .then(cwObserveA(false, false, true, 90))
    .then(check(io == [{ name: "publish", strs: ["waiting"], nums: [100, 90] }] and cw.since == 100))

  run t_cw_state_change_resets_since = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwObserveA(false, false, true, 100))
    .then(check(io == [{ name: "publish", strs: ["waiting"], nums: [100, 100] }]))
    .then(cwObserveA(false, true, true, 110))
    .then(check(io == [{ name: "publish", strs: ["refused"], nums: [110, 110] }]))
    .then(cwObserveA(false, true, true, 120))
    .then(check(io == [{ name: "publish", strs: ["refused"], nums: [110, 120] }]))
    .then(cwObserveA(false, false, true, 130))
    .then(check(io == [{ name: "publish", strs: ["waiting"], nums: [130, 130] }]))

  run t_cw_withdrawn_never_contends = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwObserveA(true, true, true, 100))
    .then(check(cw.st == "quiet" and io == []))
    .then(cwObserveA(true, false, true, 110))
    .then(check(cw.st == "quiet" and io == []))
    .then(cwAcq)
    .then(check(cw.st == "quiet" and io == []))
    .then(cwObserveA(false, false, true, 120))
    .then(check(cw.st == "seeking" and io == [{ name: "publish", strs: ["waiting"], nums: [120, 120] }]))

  run t_cw_not_due_does_not_publish = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwObserveA(false, false, false, 100))
    .then(check(io == [] and cw.phase == "waiting" and cw.since == 100))
    .then(cwObserveA(false, false, false, 105))
    .then(check(io == [] and cw.since == 100))
    .then(cwObserveA(false, false, true, 110))
    .then(check(io == [{ name: "publish", strs: ["waiting"], nums: [100, 110] }]))

  run t_cw_one_event_pair_per_loss_episode = init
    .then(check(cw.st == "seeking" and io == []))
    .then(cwAcq)
    .then(check(cw.st == "holding" and io == []))
    .then(cwLo)
    .then(check(io == [{ name: "name_taken", strs: [], nums: [] }] and cw.lostEp == true))
    .then(cwLo)
    .then(check(io == []))
    .then(cwObserveA(false, false, true, 110))
    .then(check(io == [{ name: "publish", strs: ["nameless"], nums: [110, 110] }]))
    .then(cwAcq)
    .then(check(io == [{ name: "name_back", strs: [], nums: [] }] and cw.st == "holding" and cw.lostEp == false))
    .then(cwAcq)
    .then(check(io == []))
    .then(cwLo)
    .then(check(io == [{ name: "name_taken", strs: [], nums: [] }]))
    .then(cwAcq)
    .then(check(io == [{ name: "name_back", strs: [], nums: [] }] and cw.st == "holding"))

  run t_tc_cache_used_without_asking = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("demand", false, "", "", 10))
    .then(check(io == [{ name: "offer", strs: ["old"], nums: [] }]))
    .then(tick)
    .then(check(io == []))
    .then(tcE("demand", false, "", "", 30000))
    .then(check(io == [{ name: "offer", strs: ["old"], nums: [] }]))

  run t_tc_unopened_is_no_file = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", false, "", "", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("demand", false, "", "", 10))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }] and tc.st == "asking"))
    .then(tcE("demand", false, "", "", 10))
    .then(check(io == [{ name: "wait", strs: [], nums: [] }]))
    .then(tcE("issued", false, "new", "new-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }] and tc.st == "candidate"))
    .then(tcE("accepted", false, "new", "", 0))
    .then(check(io == [{ name: "persist", strs: ["new"], nums: [] }] and tc.st == "ready"))

  run t_tc_unknown_key_current_no_request = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("unknown_key", false, "old", "", 0))
    .then(check(io == [{ name: "wait", strs: [], nums: [] }] and tc.st == "ready"))
    .then(tcE("demand", false, "", "", 10))
    .then(check(io == [{ name: "offer", strs: ["old"], nums: [] }]))

  run t_tc_expired_receiver_replaces_after_accept = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("expired", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }] and tc.st == "asking"))
    .then(tcE("issued", false, "new", "new-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }] and tc.curH == "old"))
    .then(tcE("accepted", false, "new", "", 0))
    .then(check(io == [{ name: "persist", strs: ["new"], nums: [] }] and tc.curH == "new"))
    .then(tcE("accepted", false, "new", "", 0))
    .then(check(io == []))

  run t_tc_revoked_word_exact = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("revoked", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: ["old-jti"], nums: [] }] and tc.revoked == "old-jti"))
    .then(tcE("issued", false, "new", "new-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }]))
    .then(tcE("accepted", false, "new", "", 0))
    .then(check(io == [{ name: "persist", strs: ["new"], nums: [] }] and tc.revoked == ""))

  run t_tc_same_jti_until_next_day = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("revoked", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: ["old-jti"], nums: [] }]))
    .then(tcE("issued", false, "same", "old-jti", 10))
    .then(check(io == [{ name: "same_jti_log", strs: [], nums: [10] }] and tc.st == "cooldown"))
    .then(tcE("demand", false, "", "", 10))
    .then(check(io == [{ name: "wait", strs: [], nums: [] }]))
    .then(tcE("demand", false, "", "", 9))
    .then(check(io == [{ name: "wait", strs: [], nums: [] }]))
    .then(tcE("demand", false, "", "", 11))
    .then(check(io == [{ name: "request", strs: ["old-jti"], nums: [] }] and tc.st == "asking"))

  run t_tc_unknown_key_new_no_file_no_ask = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("expired", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }]))
    .then(tcE("issued", false, "new", "new-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }]))
    .then(tcE("unknown_key", false, "new", "", 0))
    .then(check(io == [{ name: "wait", strs: [], nums: [] }] and tc.st == "candidate"))
    .then(tcE("demand", false, "", "", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }]))

  run t_tc_new_expired_before_first_accept = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("expired", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }]))
    .then(tcE("issued", false, "new", "new-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }]))
    .then(tcE("expired", false, "new", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }] and tc.st == "asking" and tc.curH == "old"))

  run t_tc_new_revoked_before_first_accept = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("expired", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }]))
    .then(tcE("issued", false, "new", "new-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }]))
    .then(tcE("revoked", false, "new", "", 0))
    .then(check(io == [{ name: "request", strs: ["new-jti"], nums: [] }] and tc.st == "asking" and tc.curH == "old"))

  run t_tc_stale_recipient_results_do_not_promote = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("expired", false, "foreign", "", 0))
    .then(check(io == [] and tc.st == "ready"))
    .then(tcE("expired", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }]))
    .then(tcE("issued", false, "new", "new-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["new"], nums: [] }]))
    .then(tcE("accepted", false, "old", "", 0))
    .then(check(io == [] and tc.st == "candidate"))
    .then(tcE("revoked", false, "old", "", 0))
    .then(check(io == [] and tc.st == "candidate"))

  run t_tc_issue_failure_keeps_old_memory = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("expired", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }]))
    .then(tcE("issue_failed", false, "", "", 0))
    .then(check(tc.st == "ready" and io == [] and tc.curH == "old" and tc.usable == false))
    .then(tcE("demand", false, "", "", 10))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }]))

  run t_tc_same_jti_expired_is_not_revoked_word = init
    .then(check(tc.st == "loading" and io == []))
    .then(tcE("loaded", true, "old", "old-jti", 0))
    .then(check(tc.st == "ready" and io == []))
    .then(tcE("expired", false, "old", "", 0))
    .then(check(io == [{ name: "request", strs: [""], nums: [] }]))
    .then(tcE("issued", false, "same", "old-jti", 10))
    .then(check(io == [{ name: "offer", strs: ["same"], nums: [] }] and tc.st == "candidate"))
}
