# E1 — один адаптер `door` на всю цель; его смерть — `stand transport` на каждом следующем шаге

**Случаев:** P/01.1/inproc кандидата MiniMax — 236 `red stand transport` и 3 `not_executed assertion` после смерти адаптера на `22-body-edge:111` (причина смерти — K3). По R037 цель получает класс `stand`, а `stand` по R024 «ничего не говорит о реализации». Красное кандидата K3 этим скрыто, хотя его причина — код кандидата.

## Норма
- `Platform/01-store/acceptance/1/README.md:34`: «For **each scenario, including on a repeated run**, the runner creates a new isolated instance of the store with empty application rows and an empty memory of the write identifiers `id`.» Общая приёмка повторяет это: `common/acceptance/README.md:187` («Instance — per scenario (P/01.1) …»).
- `PROFILE.md:97`, `:99`: адаптер `door` обслуживает один экземпляр по пути `{data}`; «another instance uses another process and data path».
- R024 (`acceptance.norms.md:183–184`): `implementation` — несовпадение шага или «the expired term of an answer of a door or of a process of the candidate»; `stand` — «the stand did not work, **outside the code of the candidate**: its transport failed, … its own auxiliary process failed».
- R038 (`acceptance.norms.md:196`): команда профиля, которая не стартовала (коды 126, 127), умерла по сигналу или не уложилась в срок, — `implementation`; «The class `stand` applies only to a command of the stand itself or a proxy of the judge.»
- `PROFILE.md:107`: «Premature EOF, I/O failure or invalid outer JSON is a transport failure rather than an API refusal.»
- R030 (`acceptance.norms.md:61`): шаги после шага, который прервал сценарий, — `not_executed` с причиной «the scenario and the number of the step whose failure ended it; that step keeps its own class».

## Наблюдение
Адаптер кандидата (команда `adapters.door` его профиля) вышел с кодом 2 на шаге 111. Движок дальше пишет кадры в закрытый канал: каждый HTTP-шаг 19 следующих сценариев получает `red stand transport`, `ASSERT` по несвязанным переменным — `not_executed assertion`. Нового адаптера на следующий сценарий движок не запускает.

## Код движка (`ef7dcf9b`)
- `run.go:285` → `run_adapters.go:27–83`: `executeAdapter` запускает адаптер один раз на цель, путь данных один — `{tempDir}/adapter-data` (`:31`); `c.adapterDoor` живёт до конца цели.
- `scenario_verdict.go:54–66`: при `adapterDoor != nil` проверки готовности и `failStepsForCandidateExit` (её движок делает для процесса стенда) нет.
- `scenario_verdict.go:145–148`: нет ответа от адаптера → `redVerdict(ClassStand, "transport")`, `continue`; сценарий не прерывается, адаптер не перезапускается.

## Мнение окна
Исход — **движок** по двум пунктам, и **норма** по одному.
1. **Движок, экземпляр на сценарий.** `acceptance/1/README.md:34` требует нового экземпляра на каждый сценарий, а движок держит один адаптер и один каталог данных на всю цель. С адаптером на сценарий K3 дал бы красное только сценарию `22-body-edge`, а не 19 сценариям. Что одна и та же память `id` у Opus не дала красного, говорит лишь о том, что ключи сценариев не пересекаются. Та же норма нарушена на стенде daemon (P01.168, B3: хранилище не сбрасывается между сценариями).
2. **Движок, класс.** Адаптер — команда профиля кандидата, а не процесс стенда. По R024 («outside the code of the candidate») и R038 (`stand` — только команда самого стенда или прокси судьи) его смерть — `implementation`. Так движок уже делает для процесса стенда (`failStepsForCandidateExit`, `scenario_verdict.go:60`; ср. P01.127 E5).
3. **Норма.** R038 перечисляет «не стартовала, сигнал, срок», но не «вышла сама с ненулевым кодом посреди потока». `PROFILE.md:107` называет обрыв «transport failure», а R024 относит transport к `stand`. Чтение «транспорт адаптера кандидата — `stand`» тексту не противоречит. Не хватает фразы: «обрыв или выход адаптера кандидата посреди потока — `implementation` того шага; остальные шаги сценария — `not_executed` по R030; следующий сценарий получает новый адаптер».

Причина в линии судьи — модель (линия судьи); вторая — **цикл**: ворота линии судьи не подавали заглушку адаптера, которая умирает посреди цели, и не сверяли число запусков адаптера с числом сценариев.

## Правила для ворот линии судьи
1. Заглушка `adapters.door`, которая выходит с кодом 2 на N-м кадре: шаг N — `red implementation`, остальные шаги сценария — `not_executed` «сценарий:N», следующий сценарий — новый процесс адаптера и GREEN.
2. Число запусков `adapters.door` за цель P/01.1 равно числу сценариев; у каждого запуска свой путь `{data}`.

## Вопросы ревьюеру
1. Экземпляр на сценарий (`acceptance/1/README.md:34`) обязателен и для цели `inproc` через адаптер, или только для стенда? Окно читает «any implementation … each scenario» как обязательное для обоих путей.
2. Класс шага, на котором адаптер кандидата умер, — `implementation` с причиной `transport` или с причиной `process`?
