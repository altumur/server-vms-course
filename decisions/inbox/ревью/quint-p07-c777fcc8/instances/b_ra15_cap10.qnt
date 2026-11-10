module b_ra15_cap10 {
  import budget_core(KINDS=Set("409"), LATS=Set(0), RAS=Set(15), CAP=10, POLICY409="refuse", BUDGET=-1, TAKEOVER=30, LIM=3600).* from "../retry_budget"
}
