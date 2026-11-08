// Конфигурация запуска r04-letter-qualified-eps (генерируется run.py)
module cfg_r04_letter_qualified_eps {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0,1), ALLOWED=1, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false).* from "../p05_retain"
}
