// Конфигурация запуска p01b-hang-nobudget-gap (генерируется run.py)
module cfg_p01b_hang_nobudget_gap {
  import p05_pass(PASS_EVERY=600, PEER_FAILS=3, NB=6, PEERS_N=2, BUDGET=0, EXPIRY_FAIL=true, REFUSAL_FAIL=false, REFUSE_HEAD=0, KINDS=Set("HANG"), PER_CALL=false, STEP_BUDGET=0, PASS_BOUND=6000, MUT_NO_SKIP=false, MUT_KEEP_SKIP=false).* from "../p05_pass"
}
