module k_age_browser {
  import clock_core(CLOCK="mono", JUMP=0, T=20, D=25, SKEW=30, AGE="browser", SLEEP=0, WAKE_ANSWER_FIRST=false).* from "../timer_clock"
}
