module s_norm_noshare {
  import session_core(POLICY="norm", SHARED=false, CANCEL_TOAST=true, AGE_LIMIT=false, IDKIND="named", KEEP_EXP=false, RELOAD=false).* from "../retry_session"
}
