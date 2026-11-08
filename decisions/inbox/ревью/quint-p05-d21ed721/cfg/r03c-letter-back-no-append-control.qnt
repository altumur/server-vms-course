// Конфигурация запуска r03c-letter-back-no-append-control (генерируется run.py)
module cfg_r03c_letter_back_no_append_control {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0,-600,600), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
