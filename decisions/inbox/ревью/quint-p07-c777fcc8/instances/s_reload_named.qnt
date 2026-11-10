module s_reload_named {
  import session_core(POLICY="norm", SHARED=true, CANCEL_TOAST=true, AGE_LIMIT=false, IDKIND="named", KEEP_EXP=false, RELOAD=true).* from "../retry_session"
}
