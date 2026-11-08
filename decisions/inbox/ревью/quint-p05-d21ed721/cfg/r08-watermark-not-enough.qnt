// Конфигурация запуска r08-watermark-not-enough (генерируется run.py)
module cfg_r08_watermark_not_enough {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0,-600,600), ALLOWED=0, CAN_APPEND=true, WRITTEN_WATERMARK=true, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
