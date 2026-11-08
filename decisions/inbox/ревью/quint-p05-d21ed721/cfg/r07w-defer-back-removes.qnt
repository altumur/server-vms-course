// Конфигурация запуска r07w-defer-back-removes (генерируется run.py)
module cfg_r07w_defer_back_removes {
  import p05_retain(TERM=86400, MODE="DEFER", JUMPS=Set(0,-600,600), ALLOWED=0, CAN_APPEND=true, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
