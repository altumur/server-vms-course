module start_mono {
  import start_core(START_WAIT=60, CLOCK="mono", JUMP=100, DTS=Set(1, 30, 60)).* from "../reader_start"
}
