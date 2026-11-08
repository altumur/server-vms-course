// Сформировано run.py: экземпляр S_m_slotfirst. Не редактировать вручную.
module S_m_slotfirst {
  import p03_stop(STOP_TIMEOUT=240, STEP_DUR=Set(1,12), LAST_RENEW_AGE=Set(0,100), ORDER_MUT="slot_before_place", STANDIN_REREAD=true, STEP_BUDGET=0).* from "../p03_stop"
}
