module s_age_numeric_exp {
  import session_core(POLICY="cancel_seen", SHARED=false, CANCEL_TOAST=true, AGE_LIMIT=true, IDKIND="numeric", KEEP_EXP=true, RELOAD=false).* from "../retry_session"
}
