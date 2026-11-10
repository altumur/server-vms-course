module mark_ctrl {
  import mark_core(CMP_DIG=true, CLOCK="mono", PERIOD=30, JUMP=-100, DTS=Set(1, 30)).* from "../reader_mark"
}
