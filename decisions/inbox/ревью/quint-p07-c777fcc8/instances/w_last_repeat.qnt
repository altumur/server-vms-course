module w_last_repeat {
  import walk_core(PAGES=3, FAULT="repeat", DETECT="last", BUDGET=-1, LIM=4, POLL=5).* from "../domain_walk"
}
