// -*- mode: Bluespec; -*-
// Проверка оговорки формы P/02.4 N1.9 bound (02.4:528-531): рестарт члена по RestartSec=2 держит его
// лежащим не менее 2 с и не остаётся незамеченным хотя бы одной пачкой.
// Наблюдение батча k — в [k, k+1) (ответ не позже tick(k+1), machine:env; 02.4:529).
// Единицы — сотые секунды; DOWN — длительность простоя (RestartSec=2 плюс время старта ≥ 0).
// Батчи не прекращаются до конца поля (0..K-1); начало простоя d — в пределах, где окно целиком под батчами.
module pollbound {
  const DOWN: int   // длительность простоя (сотые)
  pure val BATCH = 100
  const K: int      // число батчей под наблюдением
  var d: int        // начало простоя
  var offs: int -> int // m_k = k*BATCH + offs[k], 0 <= offs < BATCH

  action init = {
    nondet dd = 0.to(K * BATCH - DOWN - 1).oneOf()
    nondet o0 = 0.to(BATCH - 1).oneOf()
    nondet o1 = 0.to(BATCH - 1).oneOf()
    nondet o2 = 0.to(BATCH - 1).oneOf()
    nondet o3 = 0.to(BATCH - 1).oneOf()
    all {
      d' = dd,
      offs' = Set(0, 1, 2, 3).filter(k => k < K).mapBy(k => if (k == 0) o0 else if (k == 1) o1 else if (k == 2) o2 else o3),
    }
  }

  action step = all { d' = d, offs' = offs }

  // Какое-то наблюдение попало на время простоя.
  val inv_seen = offs.keys().exists(k => k * BATCH + offs.get(k) >= d and k * BATCH + offs.get(k) < d + DOWN)
  // Свидетель: инвариант не вакуумен — наблюдения вообще есть.
  val inv_sanity = offs.keys().size() == K
}

module pb_ok   { import pollbound(DOWN=200, K=4).* }
module pb_ok201 { import pollbound(DOWN=201, K=4).* }
module pb_short { import pollbound(DOWN=100, K=4).* }
module pb_199 { import pollbound(DOWN=199, K=4).* }
module pb_198 { import pollbound(DOWN=198, K=4).* }
