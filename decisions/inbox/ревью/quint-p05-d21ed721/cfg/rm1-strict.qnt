// Конфигурация запуска rm1-strict (генерируется run.py)
module cfg_rm1_strict {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=true, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
