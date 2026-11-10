module race_seq {
  import race_core(N=2, D2=3, D3=3, VIEW_FIRST=false, ATOMIC19=true, CLEAN="norm", POSTPARTS=false, SEQ=true, CRASH=false, FOREIGN=false, BUDGET=-1, MARK_CAS=true, ENFORCE=true, MID=false, COARSE=false).* from "../put_race"
}
