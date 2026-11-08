// Конфигурация запуска r01b-letter-nojump-s50 (генерируется run.py)
module cfg_r01b_letter_nojump_s50 {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0), ALLOWED=0, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
