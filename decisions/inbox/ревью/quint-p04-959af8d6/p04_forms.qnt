// СГЕНЕРИРОВАНО gen_forms.py из формы P/04 на пине; не редактировать.
// slot-fate.tsv sha256 7984459d16329e90738ca03c68cfd41402769b7301d151e4fa5b8caf9b373742  (16 строк)
// slot-release.tsv sha256 a9a4f0a97f2ae69a3b2c119a9dfcd5f009df2046b21c9706d1551032e08917a5  (8 строк)
module p04_forms {
  pure val SLOT_TERM: int = 45     // slot-fate.tsv: #const SLOT_TERM; Platform/common/contracts/slot.md:45
  pure val LOST_AFTER: int = 45    // slot-fate.tsv: #const LOST_AFTER; observation.md Freshness
  pure val NOVER: int = -1         // пустая версия: нет разрешения

  // Результат: (судьба, версия разрешения или NOVER, номер строки формы)
  pure def slotFate(age: int, slot_readable: bool, worker_fresh: bool, resource: str, presence: str, assigned: bool, server_known: bool, gen_readable: bool, version: int, HUNG_MOVE_AFTER: int): (str, int, int) =
    if (slot_readable  and  age < SLOT_TERM) ("alive", NOVER, 1)
    else if (resource == "live"  and  presence == "gone"  and  not(assigned)) ("release", NOVER, 2)
    else if (resource == "live"  and  presence == "gone") ("move", if (gen_readable) version else NOVER, 3)
    else if (age < SLOT_TERM + LOST_AFTER) ("alive", NOVER, 4)
    else if (worker_fresh) ("alive", NOVER, 5)
    else if (resource == "live"  and  presence == "runs"  and  age >= HUNG_MOVE_AFTER) ("hung_moved", if (gen_readable) version else NOVER, 6)
    else if (resource == "live"  and  presence == "runs") ("hung", NOVER, 7)
    else if (resource == "live"  and  presence == "unlisted") ("wait", if (gen_readable  and  age >= HUNG_MOVE_AFTER) version else NOVER, 8)
    else if (resource == "live"  and  presence == "unknown"  and  age >= HUNG_MOVE_AFTER) ("unsure_moved", if (gen_readable) version else NOVER, 9)
    else if (resource == "live"  and  presence == "unknown") ("unsure", NOVER, 10)
    else if (resource == "unreachable"  and  age >= HUNG_MOVE_AFTER) ("unsure_moved", if (gen_readable) version else NOVER, 11)
    else if (resource == "unreachable") ("unsure", NOVER, 12)
    else if (resource == "silent"  and  not(worker_fresh)) ("move", if (gen_readable) version else NOVER, 13)
    else if (not(server_known)) ("move", if (gen_readable) version else NOVER, 14)
    else if (assigned) ("move", if (gen_readable) version else NOVER, 15)
    else if (true) ("release", NOVER, 16)
    else ("judge", NOVER, 0)

  // Шаг машины release: (состояние, судьба-исход, версия-разрешение, номер строки); нет совпадения — ожидание без действия.
  pure def slotReleaseStep(state: str, fate: str, gen_readable: bool, age: int, HUNG_MOVE_AFTER: int, version: int, release_version: int, reply: str): (str, str, int, int) =
    if (state == "consider") (if (fate == "release") ("writing", "", NOVER, 1)
    else if (fate == "move") ("move", "move", if (gen_readable) version else NOVER, 6)
    else if (fate == "wait") ("wait", "wait", if (gen_readable  and  age >= HUNG_MOVE_AFTER) version else NOVER, 7)
    else if (fate == "hung") ("hung", "hung", NOVER, 8)
    else ("consider", "", NOVER, 0))
    else if (state == "writing") (if (reply == "conflict") ("refused", "not_released", NOVER, 2)
    else if (reply == "blocked") ("refused", "not_released", NOVER, 3)
    else if (reply == "badkey"  or  reply == "error") ("refused", "not_released", NOVER, 4)
    else if (reply == "ok"  and  gen_readable) ("released", "release", release_version, 5)
    else ("writing", "", NOVER, 0))
    else ("done", "", NOVER, 0)
}
