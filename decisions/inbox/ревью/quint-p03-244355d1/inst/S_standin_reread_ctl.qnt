// Сформировано run.py: экземпляр S_standin_reread_ctl. Не редактировать вручную.
module S_standin_reread_ctl {
  import p03_stop(STOP_TIMEOUT=240, STEP_DUR=Set(1,12), LAST_RENEW_AGE=Set(0,100), ORDER_MUT="standin_after_release", STANDIN_REREAD=true, STEP_BUDGET=0).* from "../p03_stop"
}
