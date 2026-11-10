module mark_wall {
  import mark_core(CMP_DIG=false, CLOCK="wall", PERIOD=30, JUMP=-100, DTS=Set(1, 30, 40)).* from "../reader_mark"
}
