// Конфигурация запуска k03-order-any (генерируется run.py)
module cfg_k03_order_any {
  import p05_crash(BARRIER=false, ORDER="ANY").* from "../p05_crash"
}
