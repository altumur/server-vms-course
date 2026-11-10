module race_known {
  import race_core(N=2, D2=3, D3=3, VIEW_FIRST=false, ATOMIC19=true, CLEAN="known", POSTPARTS=false, SEQ=false, CRASH=false, FOREIGN=false, BUDGET=-1, MARK_CAS=true, ENFORCE=true, MID=false, COARSE=true).* from "../put_race"
}
