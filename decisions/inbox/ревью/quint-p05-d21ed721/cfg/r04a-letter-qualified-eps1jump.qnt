// Конфигурация запуска r04a-letter-qualified-eps1jump (генерируется run.py)
module cfg_r04a_letter_qualified_eps1jump {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0,1), ALLOWED=1, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=1).* from "../p05_retain"
}
