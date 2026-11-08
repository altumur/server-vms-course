// Сформировано run.py: экземпляр S_flush_ctl. Не редактировать вручную.
module S_flush_ctl {
  import p03_stop(STOP_TIMEOUT=240, STEP_DUR=Set(1,12), LAST_RENEW_AGE=Set(0,100), ORDER_MUT="none", STANDIN_REREAD=true, STEP_BUDGET=0).* from "../p03_stop"
}
