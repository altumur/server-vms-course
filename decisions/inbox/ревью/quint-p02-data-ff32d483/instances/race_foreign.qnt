module race_foreign {
  import race_core(N=1, D2=3, D3=3, VIEW_FIRST=false, ATOMIC19=true, CLEAN="norm", POSTPARTS=false, SEQ=false, CRASH=false, FOREIGN=true, BUDGET=-1, MARK_CAS=true, ENFORCE=true, MID=false, COARSE=false).* from "../put_race"
}
