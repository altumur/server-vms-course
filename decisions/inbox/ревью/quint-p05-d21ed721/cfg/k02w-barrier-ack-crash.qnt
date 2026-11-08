// Конфигурация запуска k02w-barrier-ack-crash (генерируется run.py)
module cfg_k02w_barrier_ack_crash {
  import p05_crash(BARRIER=true, ORDER="ANY").* from "../p05_crash"
}
