// Конфигурация запуска p07-percall-hang-ok (генерируется run.py)
module cfg_p07_percall_hang_ok {
  import p05_pass(PASS_EVERY=600, PEER_FAILS=3, NB=6, PEERS_N=2, BUDGET=10, EXPIRY_FAIL=true, REFUSAL_FAIL=false, REFUSE_HEAD=0, KINDS=Set("HANG","OK"), PER_CALL=true, STEP_BUDGET=0, PASS_BOUND=60, MUT_NO_SKIP=false, MUT_KEEP_SKIP=false).* from "../p05_pass"
}
