// Конфигурация запуска s02m-hb-blocked (генерируется run.py)
module cfg_s02m_hb_blocked {
  import p05_stall(HB=10, L=20, DURS=Set(19, 21, 40), BLOCK_HB=true).* from "../p05_stall"
}
