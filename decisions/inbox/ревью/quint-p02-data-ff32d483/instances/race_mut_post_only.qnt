module race_mut_post_only {
  import race_core(N=2, D2=3, D3=3, VIEW_FIRST=false, ATOMIC19=false, CLEAN="norm", POSTPARTS=true, SEQ=false, CRASH=false, FOREIGN=false, BUDGET=-1, MARK_CAS=true, ENFORCE=true, MID=false, COARSE=true).* from "../put_race"
}
