// Конфигурация запуска p03a-budget5-expfail (генерируется run.py)
module cfg_p03a_budget5_expfail {
  import p05_pass(PASS_EVERY=600, PEER_FAILS=3, NB=6, PEERS_N=2, BUDGET=5, EXPIRY_FAIL=true, REFUSAL_FAIL=false, REFUSE_HEAD=0, KINDS=Set("HANG"), PER_CALL=false, STEP_BUDGET=0, PASS_BOUND=30, MUT_NO_SKIP=false, MUT_KEEP_SKIP=false).* from "../p05_pass"
}
