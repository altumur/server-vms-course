module w_none_repeat {
  import walk_core(PAGES=3, FAULT="repeat", DETECT="none", BUDGET=-1, LIM=4, POLL=5).* from "../domain_walk"
}
