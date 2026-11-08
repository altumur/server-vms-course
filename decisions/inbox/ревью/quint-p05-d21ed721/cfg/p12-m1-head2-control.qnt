// Конфигурация запуска p12-m1-head2-control (генерируется run.py)
module cfg_p12_m1_head2_control {
  import p05_pass(PASS_EVERY=600, PEER_FAILS=3, NB=6, PEERS_N=2, BUDGET=10, EXPIRY_FAIL=true, REFUSAL_FAIL=true, REFUSE_HEAD=2, KINDS=Set("OK"), PER_CALL=false, STEP_BUDGET=0, PASS_BOUND=60, MUT_NO_SKIP=false, MUT_KEEP_SKIP=false).* from "../p05_pass"
}
