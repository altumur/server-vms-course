// Конфигурация запуска rm2-early (генерируется run.py)
module cfg_rm2_early {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=true, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
