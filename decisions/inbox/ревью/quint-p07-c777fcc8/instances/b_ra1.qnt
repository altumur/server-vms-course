module b_ra1 {
  import budget_core(KINDS=Set("503"), LATS=Set(0), RAS=Set(1), CAP=-1, POLICY409="refuse", BUDGET=-1, TAKEOVER=30, LIM=3600).* from "../retry_budget"
}
