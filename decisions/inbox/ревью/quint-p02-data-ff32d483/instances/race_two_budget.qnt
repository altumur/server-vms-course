module race_two_budget {
  import race_core(N=2, D2=3, D3=3, VIEW_FIRST=false, ATOMIC19=true, CLEAN="norm", POSTPARTS=false, SEQ=false, CRASH=false, FOREIGN=false, BUDGET=3, MARK_CAS=true, ENFORCE=true, MID=false, COARSE=true).* from "../put_race"
}
