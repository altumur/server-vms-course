// Конфигурация запуска m03-noskip-nb3-control (генерируется run.py)
module cfg_m03_noskip_nb3_control {
  import p05_pass(PASS_EVERY=600, PEER_FAILS=3, NB=3, PEERS_N=2, BUDGET=10, EXPIRY_FAIL=true, REFUSAL_FAIL=false, REFUSE_HEAD=0, KINDS=Set("HANG"), PER_CALL=false, STEP_BUDGET=0, PASS_BOUND=60, MUT_NO_SKIP=true, MUT_KEEP_SKIP=false).* from "../p05_pass"
}
