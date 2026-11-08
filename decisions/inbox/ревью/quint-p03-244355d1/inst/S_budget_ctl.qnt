// Сформировано run.py: экземпляр S_budget_ctl. Не редактировать вручную.
module S_budget_ctl {
  import p03_stop(STOP_TIMEOUT=240, STEP_DUR=Set(1,12,600), LAST_RENEW_AGE=Set(0,100), ORDER_MUT="none", STANDIN_REREAD=true, STEP_BUDGET=12).* from "../p03_stop"
}
