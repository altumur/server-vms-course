module race_break {
  import race_core(N=2, D2=2, D3=3, VIEW_FIRST=false, ATOMIC19=true, CLEAN="norm", POSTPARTS=false, SEQ=true, CRASH=true, FOREIGN=false, BUDGET=-1, MARK_CAS=true, ENFORCE=true, MID=false, COARSE=false).* from "../put_race"
}
