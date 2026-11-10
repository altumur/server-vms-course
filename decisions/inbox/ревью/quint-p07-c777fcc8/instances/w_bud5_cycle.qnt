module w_bud5_cycle {
  import walk_core(PAGES=3, FAULT="cycle", DETECT="none", BUDGET=5, LIM=5, POLL=5).* from "../domain_walk"
}
