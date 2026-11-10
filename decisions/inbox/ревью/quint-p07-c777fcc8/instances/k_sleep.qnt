module k_sleep {
  import clock_core(CLOCK="mono", JUMP=0, T=20, D=25, SKEW=0, AGE="server_time", SLEEP=60, WAKE_ANSWER_FIRST=false).* from "../timer_clock"
}
