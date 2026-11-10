module k_mono_up {
  import clock_core(CLOCK="mono", JUMP=100, T=20, D=25, SKEW=0, AGE="server_time", SLEEP=0, WAKE_ANSWER_FIRST=false).* from "../timer_clock"
}
