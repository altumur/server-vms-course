// Конфигурация запуска t03-jitter-mut-together (генерируется run.py)
module cfg_t03_jitter_mut_together {
  import p05_retry(RETRY=10, RETRY_MAX=600, STARTS=Set(0), JITTER=Set(0,3), MAX_ATTEMPTS=8).* from "../p05_retry"
}
