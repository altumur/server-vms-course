// Конфигурация запуска s01-rules-conflict (генерируется run.py)
module cfg_s01_rules_conflict {
  import p05_stall(HB=10, L=20, DURS=Set(19, 21, 40), BLOCK_HB=false).* from "../p05_stall"
}
