module k_wall_down {
  import clock_core(CLOCK="wall", JUMP=-100, T=20, D=1000, SKEW=0, AGE="server_time", SLEEP=0, WAKE_ANSWER_FIRST=false).* from "../timer_clock"
}
