// Конфигурация запуска r04b-letter-qualified-eps-unbounded (генерируется run.py)
module cfg_r04b_letter_qualified_eps_unbounded {
  import p05_retain(TERM=86400, MODE="LETTER", JUMPS=Set(0,1), ALLOWED=1, CAN_APPEND=false, WRITTEN_WATERMARK=false, MUT_STRICT=false, MUT_EARLY=false, MUT_NO_MONO=false, MAX_JUMPS=99).* from "../p05_retain"
}
