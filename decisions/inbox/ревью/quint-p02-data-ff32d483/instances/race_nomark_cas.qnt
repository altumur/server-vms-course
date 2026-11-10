module race_nomark_cas {
  import race_core(N=2, D2=3, D3=3, VIEW_FIRST=false, ATOMIC19=true, CLEAN="norm", POSTPARTS=false, SEQ=false, CRASH=false, FOREIGN=false, BUDGET=-1, MARK_CAS=false, ENFORCE=true, MID=false, COARSE=false).* from "../put_race"
}
