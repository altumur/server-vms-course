module b_timeouts {
  import budget_core(KINDS=Set("409", "lost"), LATS=Set(0, 20), RAS=Set(), CAP=-1, POLICY409="refuse", BUDGET=-1, TAKEOVER=30, LIM=3600).* from "../retry_budget"
}
