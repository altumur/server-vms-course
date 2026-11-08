// Конфигурация запуска r06b-defer-seam-q6 (генерируется run.py)
module cfg_r06b_defer_seam_q6 {
  import p05_retain(TERM=86400, MODE="DEFER", JUMPS=Set(0), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
