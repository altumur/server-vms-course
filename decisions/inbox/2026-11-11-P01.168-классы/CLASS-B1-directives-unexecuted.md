# B1 — движок не исполняет директивы стенда `@restart store`, `@foreign store`, `@backup store`, `@sleep`

**Случаев:** 8 red класса `stand` и 4 зависимых `not_executed` цели P/01.3/daemon (таблица `Platform/01-store/acceptance/3/scenarios.tsv`):
- `@restart store` — 4: сц. 08-floor-replay стр. 24, 19-version-restart стр. 178, 30-batch-restart стр. 268 и 273 (причина `restart`);
- `@foreign store nolabel` / `otherlabel` — 2: сц. 10-foreign-dir стр. 36, 37 (`foreign`);
- `@backup store c2` — 1: сц. 14-copy-ids стр. 82 (`backup`); за ним 4 шага стр. 83–86 `not_executed` с причиной `14-copy-ids:82`;
- `@sleep 121` — 1: сц. 21-id-memory стр. 194 (`sleep`).

## Наблюдение движка
`engine.json` диагностики (`out-diag/claude/P_01_3_daemon/engine.json`): у каждого из 8 шагов `result: red`, `class: stand`, `reason` — имя директивы без `@`.

**Повтор replay188** (`replay188/trace/P_01_3_daemon.jsonl`, движок с одной вставкой трассировки — `engine-src.diff`; итоги шагов совпали с диагностикой):

| Таблица:строка | Отправлено движком | Статус | Тело |
|---|---|---|---|
| `acceptance/3/scenarios.tsv:24`, `:178`, `:268`, `:273` | `@restart store` — только текст директивы, запроса и процесса нет | — | — |
| `:36`, `:37` | `@foreign store nolabel` / `otherlabel` — то же | — | — |
| `:82` | `@backup store c2` — то же | — | — |
| `:194` | `@sleep 121` — то же, паузы нет | — | — |

Шаги после директив исполнены на том же процессе, перезапуска не было:

| Таблица:строка | Отправлено | Статус | Тело | Итог |
|---|---|---|---|---|
| `:23` | `admin POST /v1/write {"op":"floor","floor":4294967296,"id":"f1"}` | 200 | `{"index":"1"}` | GREEN |
| `:25` (после `:24`) | тот же запрос | 200 | `{"index":"1","again":true}` | GREEN |
| `:179` (после `:178`) | `admin GET /v1/get?key=testsub/counters/v1` | 200 | `{"items":{"n":"1"},"index":"4"}` | GREEN |
| `:195` (после `:194`) | повтор `id a02b1d0001` | 200 | `{"index":"9","again":true}` | GREEN |
| `:269`–`:271` (после `:268`) | чтения p1, p2 и повтор пакета `b30a` | 200 | `index 11`, `again: true` | GREEN |
| `:274`–`:276` (после `:273`) | чтения p1, p2; `ASSERT 11 != 12` | 200 | `{"n":"2"} index 12`; p2 `null` | GREEN |

Ответы кандидата верны для того же процесса. Сохраняет ли он их после перезапуска и после 121 с, повтор не показывает: директив движок не исполнил. Для `:36`, `:37` (чужой каталог) и `:82` (копия) повторить нечего — движок не запускал ни второго экземпляра, ни `stand.backup` по директиве.

**Вызов `stand.backup` вне сценария.** stderr демонов цели (`replay188/stderr/P_01_3_daemon.txt`) содержит `configstore: refused: no_leader: dial unix …/acceptance-engine-3079327592/run/admin.sock: connect: no such file or directory`. Его дал не `@backup`, а разовая проба интерфейсов стенда в начале цели. `internal/engine/run.go:243–291`: каждая команда `target.StandCommands` (у P/01.3/daemon — `store`, `backup`, `import`, `targets.tsv:6`) и условная `spoil-row` (`run.go:361–370`, условие `row_spoil`) один раз проходят через `executeStand` (`run_stand.go:96–129`). `stand.backup` запущен с `{socket}` = `<tmp>/run/admin.sock` и `{file}` = `<tmp>/backup.jsonl` (`run_stand.go:170–191`; файл заранее создан пустым, `:152–156`) сразу после старта `stand.store`. Готовности стора движок не ждёт: для `store`/`store1` `executeStand` только запускает процесс и возвращается (`run_stand.go:111`, `:119–122`), а следующую команду пускает сразу. Кандидат (`cmd/configstore-tool/adapters.go:199–204` → `internal/daemon/cli.go:169–181`) не нашёл сокета и отказал `no_leader`, код ≠ 0. Итог пробы движок пишет только в журнал вызовов (`run_stand.go:123–128`, статус `nonzero`), на вердикт он не влияет.

Код движка `ef7dcf9` (`/srv/minimax-loop/runs/p01-engine-8719b2141670/work/engine`):
- `internal/engine/run_directives.go:14–49` — `executeScenarioDirective` исполняет только `@group-setup`, `@store-start` и `@tls` (последнюю всегда как red `stand`). Для остальных директив функция возвращает `false`;
- `internal/engine/scenario_verdict.go:125–144` — неисполненная директива получает причину из `directiveReason` (`:232–254`). Для слов вне `@spoil`, `@rights`, `@import` это имя директивы и red `stand` (`:134`);
- `abortingDirective` (`:258–276`) обрывает сценарий на `@backup store`, поэтому стр. 83–86 получают `14-copy-ids:82`. По P/AC-R030, R033 это верно, если бы шаг 82 действительно не прошёл;
- поиск по коду движка: директив `@restart`, `@foreign`, `@sleep` в нём нет вообще. Команды `stand.backup` и `stand.import` профиля вызываются только при разовом исполнении стенда (`run_stand.go:96–129`, `:131–168`), не из сценария;
- ход движка сам это записал: `work/PLAN.md:77`, `work/NOTES.md:94` — «Unsupported scenario directives are red class `stand`».

**Ложный GREEN рядом.** Шаги после неисполненного `@restart`/`@sleep` идут на том же процессе. Поэтому они зелёные, но поведения, ради которого написаны, не проверяют: 08 стр. 25 (`again: true` после перезапуска), 19 стр. 179, 21 стр. 195 (повтор после 121 с), 30 стр. 269–271 и 274–276. Итог цели red, поэтому ложного зелёного итога нет. Но после правки только класса (не исполнения) эти шаги дали бы зелёный без проверки долговечности.

## Норма
J-вход `49e62279`, `Platform/common/acceptance/README.md`, «Dictionary of directives and doors» (`:241`):
- `:290` — «`@restart store` | SIGTERM to the store, wait for the exit, start it with the same command with the same `{data}`, wait for its readiness by the rule of «Role sockets»»;
- `:297` — «`@backup store <name>` | take a copy of the stand store with the command `backup` of «Stand» into a file of the runner `<name>` … `ok` — code 0 and the file in the form of P/01.3 N1.3 `copy`»;
- `:300` — «`@foreign store nolabel` / `@foreign store otherlabel` | a second store instance with the same command with a new directory `{data}` … `ok` — the process exited with code 2 no later than 10 s and the directory tree (names, bytes) is the same as before the start»;
- `:301` — «`@sleep <seconds>` | wait».

`Platform/01-store/acceptance/3/README.md:10–13` называет эти директивы для главы; `:13` — «The stand store is durable — it survives a restart … sc. 08 relies on this».

Класс: `common/acceptance/spec/acceptance.norms.md:184` — `stand` означает, что стенд не сработал вне кода кандидата. Класс верен по смыслу, но директива словаря — обязанность судьи, а не возможность на выбор. Неисполнение снимает с цели вердикт по 13 шагам.

## Код кандидата
Профиль `01-store/acceptance.yaml`: `:8` `stand.store`, `:10` `stand.backup` (`./bin/configstore-tool backup {socket} {file}`); `keys.store_build: raft` (`:15`). Повтором (без директив) подтверждено только поведение на одном процессе: память id и пол (`:25`, `:195`, `:271`). Остальное — **по чтению кода, не повторено**:
- `@restart`: состояние долговечно — журнал или raft-лог с fsync (`01-store/ARCHITECTURE.md:30–53`, `:90–91`), память id в состоянии (`:52–53`);
- `@foreign`: `internal/datadir/datadir.go:67–82` — каталог без `FORMAT` или с чужой меткой даёт `FormatError` без записи. `internal/daemon/daemon.go:179–181` — отказ `start_format`, код 2 (`daemon.go:66–69`). То есть ровно то, что ждёт `:300`;
- `@backup`: `cmd/configstore-tool/adapters.go:199–204` → `internal/daemon/cli.go:169–197`: `GET /v1/copy` через `admin.sock`, проверка формы, `rename`;
- `@sleep 121`: память id забывается не раньше `ID_REPLAY_MIN_AGE` (`ARCHITECTURE.md:52–53`).

Проходит ли кандидат шаги `:24`, `:36`, `:37`, `:82`, `:178`, `:194`, `:268`, `:273`, не проверено: replay188 их не охватывает, потому что движок их не исполняет. Нужен повтор с исполнением директив по `README.md:290`, `:297`, `:300`, `:301`.

## Что видела модель
Норма есть в M (`common/acceptance/README.md` и `01-store/acceptance/3/README.md` в M байт в байт те же, что в J). Журнал Claude Code:
- вызов 30 (`sed -n 241,372p README.md`) — вывод 32 КБ ушёл в файл, модели показано только начало;
- вызов 31 — `grep` тех же строк по словам `restart|foreign|backup|import|spoil|sleep` с обрезкой до 900 знаков. Строки `:290`, `:297`, `:298`, `:300`, `:301` модель видела;
- вызов 33 — `cat acceptance/3/README.md` целиком (24,6 КБ, без обрезки).

Догадок о директивах в `GUESSES.md` нет. Ворот поведения у Claude Code не было, только собственные `go build/vet/test` модели.

## Мнение
Исход — **движок**. Норма однозначна: словарь называет действие и ожидание каждой директивы. Главная причина — модель линии судьи. Вторая — **цикл** линии судьи: ворота P02.40 не подавали ни одной директивы долговечности и копии на заглушку с проверкой, что команда профиля вызвана. Кандидат здесь не судим. Повтор мнение не меняет: директивы до кандидата не дошли. Разовая проба `stand.backup` до готовности стора — тоже дефект движка (готовность по «Role sockets» не выдержана), но без влияния на вердикт: отказ кандидата `no_leader` при отсутствующем сокете верен.

Предложение для ворот: заглушка-стор, у которой `@restart` теряет состояние, должна быть red. Заглушка, отвечающая на `@foreign` кодом 0, — red. Верная заглушка — GREEN. Команда `stand.backup` должна быть вызвана с `{file}` сценария.

## Вопросы ревьюеру
1. Должен ли P/AC прямо сказать, что директива словаря, которую судья не исполняет, — это `not_executed` с причиной, а не red `stand`? Сейчас R030 (`acceptance.norms.md:61`) такой причины не даёт, а R024 (`:184`) читается как «стенд сломался».
2. Нужно ли в B1 отдельно засчитать ложные GREEN после неисполненного `@restart`/`@sleep` как дефект движка: шаг, смысл которого задан предыдущей директивой, не должен быть GREEN?
