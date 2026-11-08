// Конфигурация запуска r05b-defer-forward-s50 (генерируется run.py)
module cfg_r05b_defer_forward_s50 {
  import p05_retain(TERM=86400, MODE="DEFER", JUMPS=Set(0,86400), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
