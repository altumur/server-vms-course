module s_norm_named_exp {
  import session_core(POLICY="norm", SHARED=true, CANCEL_TOAST=true, AGE_LIMIT=false, IDKIND="named", KEEP_EXP=true, RELOAD=false).* from "../retry_session"
}
