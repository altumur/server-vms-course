// Конфигурация запуска r05w-defer-removes-after-term (генерируется run.py)
module cfg_r05w_defer_removes_after_term {
  import p05_retain(TERM=86400, MODE="DEFER", JUMPS=Set(0,86400), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
