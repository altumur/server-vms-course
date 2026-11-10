module w_last_cycle {
  import walk_core(PAGES=3, FAULT="cycle", DETECT="last", BUDGET=-1, LIM=4, POLL=5).* from "../domain_walk"
}
