// Конфигурация запуска rm3-defer-no-mono (генерируется run.py)
module cfg_rm3_defer_no_mono {
  import p05_retain(TERM=86400, MODE="DEFER", JUMPS=Set(0,86400), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=true, MAX_JUMPS=99).* from "../p05_retain"
}
