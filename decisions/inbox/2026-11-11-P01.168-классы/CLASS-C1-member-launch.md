# C1 — движок запускает участника группы не по «Store group stand»: ни комплектов, ни добавленных флагов, ни адресов

**Случаев:** 48 шагов цели P/01.3/group (`Platform/01-store/acceptance/3/scenarios.tsv`):
- первопричина — 7 шагов `red stand store-start`: строки 6, 7, 8, 12, 18 (сц. 07: `s1`, `s2`, `s3`, `d1`, `d2 kit=d1`), 103, 104 (сц. 17: `s4 -group-size 2`, `s5 -group-size 4`, ожидание `@exit 2`);
- следствие — 41 шаг `red stand transport`: запросы `store@<id>` к участнику, который не поднялся (строки 14–15, 115–117, 119–120, 122–123, 125, 132–137, 139–140, 142, 147–148, 156–159, 171, 175–176, 239, 241, 263, 265, 284–290, 293–294).

## Наблюдение движка
Источники: `engine.json` диагностики P01.188 и повтор replay188 (`/home/pilot/owner-receipts/P01.188-court-claude-20261111/replay188/`). Повтор — тот же движок `ef7dcf9b` со вставкой трассировки (`engine-src.diff`), тот же J-вход и тот же кандидат. Итоги шагов совпали с диагностикой. В трассе: `trace/P_01_3_group.jsonl` — 171 шаг, `selected/P_01_3_group.jsonl`; stderr процессов кандидата — `stderr/P_01_3_group.txt`.

**Повтор: что ушло кандидату и что он ответил.** В трассе `request_sent` директивы — её текст, подстановок нет (`{api@s1}` остался буквально). Наблюдения у этих шагов нет. В stderr цели 8 отказов старта и один старт стендового хранилища (`started box srv-a`). Отказы сопоставлены по содержанию; в файле они идут в обратном порядке запусков.

| Шаг (`acceptance/3/scenarios.tsv`) | Директива, как её отправил движок | Командная строка кандидата (шаблон `stand.store` + `-id <id>` + слова строки) | stderr кандидата | Ожидание строки |
|---|---|---|---|---|
| :6 (сц. 07) | `@store-start s1 -bootstrap -group-size 3` | `… -id s1 -bootstrap -group-size 3` | `refused: start_config: flag -raft: a group member needs its raft address` | `ok` |
| :7 (сц. 07) | `@store-start s2 -join {api@s1} -group-size 3 -force` | `… -id s2 -join '{api@s1}' …` | `refused: start_flags: flag -join: a value out of the type addr` | `ok` |
| :8 (сц. 07) | `@store-start s3 -join {api@s1} -group-size 3` | `… -id s3 -join '{api@s1}' …` | `refused: start_flags: flag -join: a value out of the type addr` | `ok` |
| :12 (сц. 07) | `@store-start d1 -door -voters s1@{api@s1},s2@{api@s2},s3@{api@s3}` | `… -id d1 -door -voters 's1@{api@s1},…'` | `refused: start_flags: flag -voters: a value out of the type list:id@addr` | `ok` |
| :18 (сц. 07) | `@store-start d2 kit=d1 -door -voters s1@{api@s1}` | `… -id d2 'kit=d1' -door -voters 's1@{api@s1}'` | `refused: start_flags: flag -voters: a value out of the type list:id@addr` | `@exit 2` |
| :103 (сц. 17) | `@store-start s4 -bootstrap -group-size 2` | `… -id s4 -bootstrap -group-size 2` | `refused: start_flags: flag -group-size: a value out of the type enum:1\|3\|5` | `@exit 2` |
| :104 (сц. 17) | `@store-start s5 -bootstrap -group-size 4` | `… -id s5 -bootstrap -group-size 4` | `refused: start_flags: flag -group-size: a value out of the type enum:1\|3\|5` | `@exit 2` |

Восьмой отказ — `refused: start_flags: a positional word of the daemon`. Он не от участника. Это разовый запуск команды профиля `stand.store-op` при старте стенда цели: интерфейс цели в `runner-targets.tsv:7`, вызов `run.go:266–283` → `run_stand.go:96–129` с подстановками `{id}=acceptance`, `{tls}=0`, `{args}=''` (`run_stand.go:174`). Пустая операция `''` у кандидата становится первым словом демона (`cmd/configstore-tool/adapters.go:181–196`). На шаги это не влияет; дефект движка отнесён к C4.

Для d2 (:18) кандидат отказал по `-voters`, а не по позиционному `kit=d1`: разборщик проверяет значение флага при чтении, позиционные слова — после (`internal/flags/parse.go:48–58`, `:63–82`). Код выхода 2 в обоих случаях (`internal/daemon/daemon.go:66–69`).

**41 шаг `transport`** — в трассе наблюдения нет: соединение с сокетом участника не удалось (`scenario_verdict.go:144–148`). Сокет `<rundir участника>/<роль>.sock` (`:392–407`) не создан, потому что участник отказал на старте (таблица выше).

**Код движка** `ef7dcf9` (`/srv/minimax-loop/runs/p01-engine-8719b2141670/work/engine/internal/engine/`):
- `run_directives.go:20–32` — `@group-setup` только читает файл описания и даёт GREEN. Комплекты не выпускаются.
- `run_directives.go:58–129` — `startGroupMember`. К шаблону добавляется только `-id <id>` (`:100`) и слова строки в кавычках (`:101–103`). Нет `-tls <kit dir>`, `-api {api@<id>}`, `-tuning lan`, `-raft {raft@<id>}`, `-raft-bind`. Подстановок `{api@<id>}`, `{raft@<id>}` в движке нет (grep `api@`, `raft@` по `internal/` пуст; повтор это подтвердил). `kit=<id2>` не разбирается и уходит кандидату словом.
- `:104` и `run_stand.go:272–292` — окружение участника `BOX_ID=stand-box`, `SERVER_NAME=srv-a`, а не `<id>`.
- `:119–127` — готовность определяется по сокетам за 20 с, а не по `admin@<id> GET /v1/status` → 200.
- `scenario_verdict.go:126` — директиве передаётся только запрос, столбец `expect` не читается. Ожидание `@exit 2` не исполняется: верный отказ с кодом 2 даёт `red stand store-start`.

**Итог повтора.** На строках :18, :103, :104 кандидат сделал то, что ждёт строка (код 2), а движок покрасил. На строках :6, :7, :8, :12 кандидат отказал только потому, что движок не дал флагов участника и не подставил адреса. Каждый отказ — по норме флагов (`forms/daemon-flags.tsv`: `-join` addr, `-voters` list:id@addr, `-group-size` enum:1|3|5) или по догадке 1 (`-raft`). Как кандидат ведёт себя при верном запуске участника, повтор не видел: тот же движок, тот же запуск.

## Норма
J-вход `49e62279`, `Platform/common/acceptance/README.md` (тот же файл в M, байт в байт):
- `:621–626` «Members»: «the ports are handed out by the runner … `{raft@<id>}`, `{api@<id>}` — substitutions in flags, requests and probes»;
- `:627–628` «Kits — the description `inputs/group.json` …: one CA of the group, a leaf for each member»;
- `:635–639` «Member launch … with the environment `BOX_ID=<id>`, `SERVER_NAME=<id>`, `PLATFORM_DIR={data}/<id>` … The runner appends only these flags: `-id <id>`, `-tls <kit dir>`, `-api {api@<id>}`, `-tuning lan`; for a voter also `-raft {raft@<id>}` … and `-raft-bind <own port>`»;
- `:646` `@group-setup`: «the runner issues the kits per the description»;
- `:647` `@store-start`: «`kit=<id2>` — the member `<id>` receives the kit of the member `<id2>` …; the expectation: `ok` — `admin@<id> GET /v1/status` answers 200 no later than 20 s; `@exit 2` — the process exited with code 2 no later than 10 s».

## Код кандидата
- Профиль `01-store/acceptance.yaml`: `stand.store` = `./bin/configstore -dir {data}/configstore -sockets {rundir} -rights {rights} -max-body {body_limit} -max-value {row_ceiling}`. Флагов, которые добавляет стенд группы, в шаблоне нет, как требует README главы 3 «Profile interface».
- `internal/daemon/daemon.go:107–118` (`mode`): с `-raft` — группа, без него `-bootstrap`/`-join`/`-group-size ≠ 1` → `start_config`.
- `internal/daemon/group.go:100–142` (`openGroup`, `start`): транспорт raft на `-raft-bind`/`-raft` с TLS-комплектом, bootstrap или join.
- Свой тест группы есть: `internal/daemon/group_test.go:155` `TestGroup`, `:337` `TestGroupImport` (по `NOTES.md`: три голосующих и дверь, отказ лидера, leave/admit, потеря кворума, recover). Прогон — только `go test` самой модели.

## Что видела модель
- Раздел «Store group stand» есть в M (`common/acceptance/README.md` M = J). Модель его прочла: журнал, вызов 32 (`sed -n 456,523p README.md; sed -n 612,655p README.md`), README главы 3 — вызов 33, PROFILE.md — вызов 25.
- `inputs/group.json` и `scenarios.tsv` главы 3 в M нет. Модель сама называет это в ретроспективе (`RETRO-ANSWER.md`: «the group-stand kit description could not be read»; «the runner's raft proxy for `@cut`, the stand's own kit issuer … were not available to test against»).
- Ворот поведения не было: Claude Code, только `go build`/`vet`/`test` самой модели.

## Мнение
Исход — **движок**, подтверждён повтором: отказы кандидата в stderr объясняются командами, которые собрал движок. Норма однозначна: README:635–639 и :647 перечисляют, что добавляет стенд и как судится `@store-start`. Главная причина в линии судьи — модель. Вторая — **цикл линии судьи**: ворота P02.40 закрыли `rules` 345/345, не исполнив стенд группы на верной заглушке. 41 шаг `transport` — следствие, а не отдельный дефект.

Вывод о кандидате по главе 1.3 «группа» из этого суда сделать нельзя: ни один шаг не дошёл до его группы.

## Вопросы ревьюеру
1. Достаточно ли README:647, чтобы требовать от движка исполнять `@exit 2` как ожидание директивы, или это нужно записать отдельной строкой общего правила «ожидание директивы — из столбца `expect`»?
2. Догадка 1 кандидата (`-bootstrap`/`-group-size 3` без `-raft` → `start_config`) не красная только потому, что стенд обязан дать `-raft`. Нужна ли в P/01.3 N1.3 фраза о старте участника без `-raft` в сборке `raft`? В `daemon-flags.tsv` у `-raft` `required` = `false`.
