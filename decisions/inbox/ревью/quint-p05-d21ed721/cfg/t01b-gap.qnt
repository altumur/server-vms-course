// Конфигурация запуска t01b-gap (генерируется run.py)
module cfg_t01b_gap {
  import p05_retry(RETRY=10, RETRY_MAX=600, STARTS=Set(0), JITTER=Set(0), MAX_ATTEMPTS=8).* from "../p05_retry"
}
