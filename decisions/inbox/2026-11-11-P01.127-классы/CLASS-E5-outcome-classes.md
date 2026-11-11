# E5 — классы исходов: падение демона кандидата — `blocked`, отказ команды вектора кандидата — `stand`

**Случаев:**
- 5 целей `blocked readiness:role` (door, extra, rights, daemon, group), их 1018 шагов `not_executed`, причина `stand`;
- 94 строки векторов `red`, `class stand`, `reason command`, `response malformed`: jcs 17, rights-evaluator 37, log-mask 39, revoked 1.

Цвет у векторов верный (red), класс — нет. У стендовых целей неверны и исход (`blocked`), и причина `not_executed`.

## Норма (J `Platform/common/acceptance/spec/acceptance.norms.md`)
- R024, таблица классов (стр. 176–182): `implementation` — «a checked behaviour did not match: a mismatch of a step, row or probe … or the expired term of an answer of a door or of a process of the candidate»; `stand` — «the stand did not work, outside the code of the candidate: … its own auxiliary process failed».
- R038 (стр. 192): «A command of the profile of the implementation that could not start (the shell codes 126 and 127), died by a signal or whose term expired has the class `implementation`. The class `stand` applies only to a command of the stand itself or a proxy of the judge.»
- R017 (стр. 127): «A process that had already exited by itself when a stop or restart step came is a mismatch of that step: the stand does not hide it by starting the process again.»
- Исходы (стр. 49–57): `blocked` — «a required interface or part of the composition is absent before execution; this is not a test result».
- R030 (стр. 61): закрытый список причин `not_executed`; для шагов, оставшихся после прерванного сценария, — «the scenario and the number of the step whose failure ended it; that step keeps its own class». Слова `stand` в списке нет.
- R037 (стр. 188): класс цели — первый из `runner`, `stand`, `data`. Класс `stand` на строке делает весь пакет «стендовым» и снимает вывод о реализации («says nothing about the implementation»).

## Наблюдение
- Стенд: команда `store` профиля кандидата объявлена, процесс запущен и вышел с кодом 2 до готовности. Проба `probe-start.txt` в квитанции P01.126: «rights file … is not valid JSON», rc=2. Интерфейс не отсутствует — он есть и упал.
- Векторы: команда профиля кандидата (`go run ./cmd/vector-jcs {input}`, `./bin/vector-common {input}`) завершилась кодом 2, без сигнала, без истечения срока.

## Код движка
- `run_vectors.go:58–63`: при `waitErr != nil` — `Response = "malformed"`, `redVerdict(ClassStand, "command")`. Любой ненулевой выход команды кандидата — `stand`.
- `scenario_verdict.go:52–59` (`addBlocked("readiness:role")`) и `run_stand.go:455–466` (`waitForStoreReady`): неготовность хранилища → `blocked`, шаги — `not_executed stand`.

## Мнение представителя
Исход — **движок**:
- по R038 команда профиля кандидата — `implementation`, `stand` только для команд самого стенда;
- падение процесса кандидата при запуске — несовпадение (R017, R024), а не отсутствие интерфейса (`blocked`).

Последствие неверного класса: по R037 цели получают класс `stand`, и вердикт «ничего не говорит о реализации». Красное кандидата (K1–K4) этим скрыто.

Главная причина — модель (линия судьи); вторая — **цикл**: ворота проверяли `roles` и отказ команды на заглушке, которая не падает, и класс исхода отказа не сверяли.

Правила для ворот:
1. Заглушка кандидата, чья команда `store` выходит с кодом ≠ 0 до готовности, даёт цели red `implementation` (первый шаг), остальные шаги — `not_executed` с причиной «сценарий и номер шага».
2. Команда вектора заглушки с кодом 2 — red `implementation`.
3. Коды 126/127 и сигнал — тоже `implementation`.

## Вопросы ревьюеру
1. «Стенд не поднялся из-за процесса кандидата» — это red `implementation` первого шага каждого сценария или red цели целиком? Норма называет класс, но не единицу.
2. Для команды вектора с кодом 2 без ответа ответ называется `malformed` (`outer_form`) или `command`? Класс в обоих случаях — `implementation`?
