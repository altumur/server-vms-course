module s_cancel_notoast {
  import session_core(POLICY="cancel_seen", SHARED=false, CANCEL_TOAST=false, AGE_LIMIT=false, IDKIND="named", KEEP_EXP=false, RELOAD=false).* from "../retry_session"
}
