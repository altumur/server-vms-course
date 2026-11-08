// Конфигурация запуска s02w-running-past-edge (генерируется run.py)
module cfg_s02w_running_past_edge {
  import p05_stall(HB=10, L=20, DURS=Set(19, 21, 40), BLOCK_HB=false).* from "../p05_stall"
}
