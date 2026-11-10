module s_reload_numeric {
  import session_core(POLICY="cancel_seen", SHARED=false, CANCEL_TOAST=true, AGE_LIMIT=true, IDKIND="numeric", KEEP_EXP=false, RELOAD=true).* from "../retry_session"
}
