module b_huge_cap10 {
  import budget_core(KINDS=Set("503"), LATS=Set(0), RAS=Set(3600), CAP=10, POLICY409="refuse", BUDGET=-1, TAKEOVER=30, LIM=30).* from "../retry_budget"
}
