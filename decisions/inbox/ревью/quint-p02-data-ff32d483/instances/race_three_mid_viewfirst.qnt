module race_three_mid_viewfirst {
  import race_core(N=2, D2=3, D3=4, VIEW_FIRST=true, ATOMIC19=true, CLEAN="norm", POSTPARTS=false, SEQ=false, CRASH=false, FOREIGN=false, BUDGET=-1, MARK_CAS=true, ENFORCE=true, MID=true, COARSE=false).* from "../put_race"
}
