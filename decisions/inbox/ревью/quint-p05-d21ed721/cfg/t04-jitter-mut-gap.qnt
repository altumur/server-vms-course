// Конфигурация запуска t04-jitter-mut-gap (генерируется run.py)
module cfg_t04_jitter_mut_gap {
  import p05_retry(RETRY=10, RETRY_MAX=600, STARTS=Set(0), JITTER=Set(0,3), MAX_ATTEMPTS=8).* from "../p05_retry"
}
