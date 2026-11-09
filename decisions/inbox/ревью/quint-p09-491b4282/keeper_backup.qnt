// keeper_backup.qnt — хранитель копии: подтверждение по голове или по частям (Б1),
// накопление частей у хранителя (С11), неизвестный исход записи объекта (С14 часть).
// Якоря: 09.1:590,591,734-738,1525,1723; 09.1:54; 08.8:176,187,203,204,206,321-322,745; 06.7:70-71,331,335.
// Срез 491b42822c64d74a3054be183ad50d4b9d875f03. Модель норм, не реализации.
module keeper_base {
  // RULE — прочтение нормы:
  //  "head_only"  — 09.1:590,1525: объект, затем строка после проверки головы, части не условие;
  //  "all_parts"  — 08.8:204 поверх порядка 09.1:1525: объект сразу, строка при всех частях;
  //  "parts_first"— контроль-гипотеза (нормой не задан): объект и строка только после всех частей;
  //  "some_part", "count_only" — мутанты ослабленного условия строки.
  const RULE: str
  // CLEANUP: "none" — текст (09.1:54 только put у domain/backups/part-*);
  //  "referenced" — контроль-гипотеза: хранитель держит части kObj и kTaken;
  //  "eager" — мутант: уборка всего, что не нужно новой голове, при записи объекта.
  const CLEANUP: str
  const BACKUP_HEADS: int  // 08-domain forms runtime-constants.tsv: BACKUP_HEADS = 5
  const MAXH: int          // граница: число голов в трассе

  // Часть 0 — неизменная секция (ссылка на прежнюю часть, 08.8:203 link);
  // часть h — изменившаяся секция головы h. Две секции достаточно для различения.
  pure def partsOf(h: int): Set[int] = if (h == 0) Set() else Set(0, h)
  pure def subset2(a: Set[int], b: Set[int]): bool = a.subseteq(b)

  // Части, живые у держателя: на них ссылаются BACKUP_HEADS новейших голов (08.8:203).
  // Допущение: окно BACKUP_FETCH не моделируется, живость только по головам.
  pure def holderParts(hh: int): Set[int] =
    1.to(MAXH).filter(h => h > 0 and h <= hh and h > hh - BACKUP_HEADS)
      .fold(Set(), (acc, h) => acc.union(partsOf(h)))

  var holderHead: int
  var pointer: int      // domain/keepers/<keeper>
  var kObj: int         // объект domain/backup у хранителя (номер головы)
  var kTaken: int       // строка domain/backup-taken
  var kParts: Set[int]  // части у хранителя
  var handover: str     // idle | waiting | proceeded
  var hoPair: int       // пара, которой ждёт шаг 3 передачи (08.8:322)
  var holderAlive: bool
  var everComplete: bool // когда-либо kObj имел все части
  var lastAction: str

  action init = all {
    holderHead' = 0, pointer' = 0, kObj' = 0, kTaken' = 0, kParts' = Set(),
    handover' = "idle", hoPair' = 0, holderAlive' = true, everComplete' = false,
    lastAction' = "init",
  }

  // Условие строки по прочтению.
  pure def takenOk(rule: str, ptr: int, ps: Set[int]): bool =
    if (rule == "head_only") true
    else if (rule == "all_parts" or rule == "parts_first") partsOf(ptr).subseteq(ps)
    else if (rule == "some_part") ptr > 0 and partsOf(ptr).intersect(ps).size() > 0
    else if (rule == "count_only") ps.size() >= 2
    else false

  action newHead = all {
    holderAlive, holderHead < MAXH,
    holderHead' = holderHead + 1,
    pointer' = pointer, kObj' = kObj, kTaken' = kTaken, kParts' = kParts,
    handover' = handover, hoPair' = hoPair, holderAlive' = holderAlive,
    everComplete' = everComplete, lastAction' = "newHead",
  }
  // Проход держателя ставит указатель на последнюю голову (08.8:173).
  action movePointer = all {
    holderAlive, holderHead > pointer,
    pointer' = holderHead,
    holderHead' = holderHead, kObj' = kObj, kTaken' = kTaken, kParts' = kParts,
    handover' = handover, hoPair' = hoPair, holderAlive' = holderAlive,
    everComplete' = everComplete, lastAction' = "movePointer",
  }
  // Поле backup ответа, шаг 4 N3: запись объекта (первая половина, 09.1:1525).
  // Неизвестный исход записи (С14) — это тот же шаг: объект есть, строки ещё нет.
  action writeObject = all {
    holderAlive, pointer > 0, pointer != kObj, pointer >= kObj, pointer != kTaken,
    RULE != "parts_first" or partsOf(pointer).subseteq(kParts),
    kObj' = pointer,
    kParts' = if (CLEANUP == "eager") kParts.intersect(partsOf(pointer)) else kParts,
    holderHead' = holderHead, pointer' = pointer, kTaken' = kTaken,
    handover' = handover, hoPair' = hoPair, holderAlive' = holderAlive,
    everComplete' = (everComplete or (kObj > 0 and partsOf(kObj).subseteq(kParts))),
    lastAction' = "writeObject",
  }
  // Запись строки (вторая половина шага 4; условие — прочтение нормы).
  action writeTaken = all {
    kObj > 0, kObj != kTaken, kObj == pointer,
    takenOk(RULE, kObj, kParts),
    kTaken' = kObj,
    kParts' = if (CLEANUP == "referenced") kParts.intersect(partsOf(kObj)) else kParts,
    holderHead' = holderHead, pointer' = pointer, kObj' = kObj,
    handover' = handover, hoPair' = hoPair, holderAlive' = holderAlive,
    everComplete' = (everComplete or partsOf(kObj).subseteq(kParts)),
    lastAction' = "writeTaken",
  }
  // Часть по двери backup-part (08.8:204): только живая у держателя.
  action fetchPart = all {
    holderAlive, pointer > 0,
    val candidates = partsOf(pointer).intersect(holderParts(holderHead)).exclude(kParts)
    all {
      candidates.size() > 0,
      nondet p = oneOf(candidates)
      all {
        kParts' = if (CLEANUP == "referenced") kParts.union(Set(p)).intersect(partsOf(pointer).union(partsOf(kObj)).union(partsOf(kTaken))) else kParts.union(Set(p)),
        lastAction' = "fetchPart",
      },
      everComplete' = everComplete,
    },
    holderHead' = holderHead, pointer' = pointer, kObj' = kObj, kTaken' = kTaken,
    handover' = handover, hoPair' = hoPair, holderAlive' = holderAlive,
  }
  action startHandover = all {
    holderAlive, handover == "idle", pointer > 0, pointer == holderHead,
    handover' = "waiting", hoPair' = pointer,
    holderHead' = holderHead, pointer' = pointer, kObj' = kObj, kTaken' = kTaken, kParts' = kParts,
    holderAlive' = holderAlive, everComplete' = everComplete, lastAction' = "startHandover",
  }
  // Шаг 3 передачи: ждём пару в domain/backup-taken (08.8:322).
  action proceedHandover = all {
    holderAlive, handover == "waiting", kTaken == hoPair,
    handover' = "proceeded",
    hoPair' = hoPair, holderHead' = holderHead, pointer' = pointer, kObj' = kObj, kTaken' = kTaken, kParts' = kParts,
    holderAlive' = holderAlive, everComplete' = everComplete, lastAction' = "proceedHandover",
  }
  action callOff = all {
    handover == "waiting", kTaken != hoPair,
    handover' = "idle",
    hoPair' = 0, holderHead' = holderHead, pointer' = pointer, kObj' = kObj, kTaken' = kTaken, kParts' = kParts,
    holderAlive' = holderAlive, everComplete' = everComplete, lastAction' = "callOff",
  }
  action loseHolder = all {
    holderAlive,
    holderAlive' = false,
    holderHead' = holderHead, pointer' = pointer, kObj' = kObj, kTaken' = kTaken, kParts' = kParts,
    handover' = handover, hoPair' = hoPair, everComplete' = everComplete, lastAction' = "loseHolder",
  }
  action step = any { newHead, movePointer, writeObject, writeTaken, fetchPart, startHandover, proceedHandover, callOff, loseHolder }
  // Шаг для С11: только накопление, чтобы дойти до BACKUP_HEADS+1 голов.
  action stepDisk = any { newHead, movePointer, writeObject, writeTaken, fetchPart }

  // --- Инварианты ---
  // Б1: строка подтверждена только при всех частях (08.8:204).
  val TakenHasParts = kTaken == 0 or partsOf(kTaken).subseteq(kParts)
  // Б1: шаг 3 передачи пропускает только цель со всеми частями (08.8:322 при 08.8:204).
  val HandoverTargetComplete = handover != "proceeded" or partsOf(hoPair).subseteq(kParts)
  // Б1: после потери держателя подтверждённая копия пригодна целиком (06.7:335).
  val RestoreAfterLoss = holderAlive or kTaken == 0 or partsOf(kTaken).subseteq(kParts)
  // Порядок объекта и строки и пара (09.1:1525, 590): строка никогда не впереди объекта.
  val TakenBehindObject = kObj >= kTaken
  // 09.1:591 «нет выбрасывания»: раз имев целую копию, хранитель её не теряет заменой на неполную голову.
  val LastCopyServable = not(everComplete) or partsOf(kObj).subseteq(kParts)
  // С11: части хранителя ограничены числом частей BACKUP_HEADS голов.
  val KeeperDiskBounded = kParts.size() <= BACKUP_HEADS + 1

  // --- Свидетели (нарушение ожидаемо) ---
  val witHeadOnlyHandover = not(handover == "proceeded" and not(holderAlive) and kParts.size() == 0)
  val witAllPartsTaken = not(handover == "proceeded" and partsOf(hoPair).subseteq(kParts))
  val witDisk = not(kParts.size() > BACKUP_HEADS + 1)
  val witTaken = not(kTaken > 0)
  // Уточнение Б1: подтверждённая целая копия заменена объектом новой, ещё неполной головы (09.1:591, 1525).
  val witCopyReplaced = not(kTaken == 1 and kObj == 2 and not(partsOf(2).subseteq(kParts)))
}

module keeper_head_only { import keeper_base(RULE = "head_only", CLEANUP = "none", BACKUP_HEADS = 5, MAXH = 2).* }
module keeper_all_parts { import keeper_base(RULE = "all_parts", CLEANUP = "none", BACKUP_HEADS = 5, MAXH = 2).* }
module keeper_parts_first { import keeper_base(RULE = "parts_first", CLEANUP = "none", BACKUP_HEADS = 5, MAXH = 2).* }
module keeper_mut_somepart { import keeper_base(RULE = "some_part", CLEANUP = "none", BACKUP_HEADS = 5, MAXH = 2).* }
module keeper_mut_count { import keeper_base(RULE = "count_only", CLEANUP = "none", BACKUP_HEADS = 5, MAXH = 2).* }
module keeper_mut_eager { import keeper_base(RULE = "all_parts", CLEANUP = "eager", BACKUP_HEADS = 5, MAXH = 2).* }
module keeper_disk_text { import keeper_base(RULE = "all_parts", CLEANUP = "none", BACKUP_HEADS = 5, MAXH = 7).* }
module keeper_disk_ctrl { import keeper_base(RULE = "all_parts", CLEANUP = "referenced", BACKUP_HEADS = 5, MAXH = 7).* }
