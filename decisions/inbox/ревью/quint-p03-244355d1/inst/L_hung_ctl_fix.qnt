// Сформировано run.py: экземпляр L_hung_ctl_fix. Не редактировать вручную.
module L_hung_ctl_fix {
  import p03_lease(N=1, HORIZON=3000, DURS=Set(1,90,1800), POLLS=Set(1), LATS=Set(0), WAKES=Set(75), CEIL=0, FAULTS=0, JUMPS=Set(), WALL_CADENCE=false, WALL_AGE=false, STANDIN=true, STEAL=false, FOREIGN=false, WRITE_FAULT=false, INIT_DELAY=Set(1,75), POLL_MIN=0, INIT_DUE=false, UPFLIP_NOT_BEFORE=0, LAST_AT_ANSWER=false, SLOT_AT_ANSWER=false, REVIVE_FENCED=false, REVIVE_OVERSLEPT=false, STANDIN_FROM_CONFIRM=true).* from "../p03_lease"
}
