// Конфигурация запуска t01w-coincide (генерируется run.py)
module cfg_t01w_coincide {
  import p05_retry(RETRY=10, RETRY_MAX=600, STARTS=Set(0), JITTER=Set(0), MAX_ATTEMPTS=8).* from "../p05_retry"
}
