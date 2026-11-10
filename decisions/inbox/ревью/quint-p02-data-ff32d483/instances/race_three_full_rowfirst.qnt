module race_three_full_rowfirst {
  import race_core(N=3, D2=3, D3=4, VIEW_FIRST=false, ATOMIC19=true, CLEAN="norm", POSTPARTS=false, SEQ=false, CRASH=false, FOREIGN=false, BUDGET=-1, MARK_CAS=true, ENFORCE=true, MID=false, COARSE=false).* from "../put_race"
}
