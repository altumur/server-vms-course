module start_wall_fw {
  import start_core(START_WAIT=60, CLOCK="wall", JUMP=100, DTS=Set(1, 30, 60)).* from "../reader_start"
}
