// Свидетели невакуумности посылок инвариантов модели 1 (отдельный модуль, чтобы не менять admission.qnt после прогонов).
module admission_wit {
  import admission.* from "./admission"
  val not_w_r071Ante = not(IDXS.exists(i => IDXS.exists(j =>
    i < j and j < logLen and log.get(i).notBefore != NONE and log.get(i).outcome == "ok" and log.get(j).notAfter == log.get(i).notBefore)))
  val not_w_stickyAnte = not(IDXS.exists(i => IDXS.exists(j =>
    i < j and j < logLen and log.get(i).outcome == "expired" and log.get(j).notAfter == log.get(i).notAfter)))
  val not_w_catchUpAnte = not(IDXS.exists(i =>
    i < logLen and log.get(i).clk >= (if (i > 0) log.get(i - 1).adm else 0) and log.get(i).notAfter != NONE and log.get(i).notAfter >= log.get(i).clk))
  val not_w_idAnte = not(IDXS.exists(i => i < logLen and log.get(i).outcome == "ok" and log.get(i).id != NONE))
}
