module s_norm_shared {
  import session_core(POLICY="norm", SHARED=true, CANCEL_TOAST=true, AGE_LIMIT=false, IDKIND="named", KEEP_EXP=false, RELOAD=false).* from "../retry_session"
}
