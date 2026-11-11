# C4 — директивы стенда группы не реализованы в движке: `@sigterm`, `@sigkill`, `@restart`, `@cut`, `@mend`, `@store-op`, `@sleep`, `@tls`

**Случаев:** 49 шагов `red stand <директива>` цели P/01.3/group:
- `store-op` 15: строки 108, 109, 154, 155, 164–166, 238, 240, 250–253, 262, 264;
- `tls` 9: строки 19–22, 227–230, 291;
- `restart` 8: строки 113, 118, 124, 129–131, 167, 254;
- `sigkill` 8: строки 121, 144, 145, 161, 162, 247, 248, 292;
- `sigterm` 6: строки 105, 126–128, 163, 249;
- `cut` 1 (138), `mend` 1 (141), `sleep` 1 (146).

## Наблюдение движка
- `run_directives.go:14–48` (`executeScenarioDirective`) знает только `@group-setup`, `@store-start` и `@tls`. На `@tls` ответ всегда `redVerdict(ClassStand, "tls")` (`:40–44`, комментарий: «The first-wave protocol stub cannot perform the TLS exchange, so report the stand limitation»).
- Остальные директивы идут в `scenario_verdict.go:130–135` → `directiveReason` (`:232–253`). Ветка `default` даёт имя директивы как причину, `missing = false` → `red stand <имя>`. Ни `@sigterm`, ни `@sigkill`, ни `@restart store@<id>`, ни `@cut`/`@mend`, ни `@store-op`, ни даже `@sleep` движок не исполняет: grep `@sigterm|@sigkill|@restart|@cut|@mend|@store-op|@sleep` по `internal/` пуст.
- Команда профиля `stand.store-op` (`./bin/configstore-tool store-op {socket} {dir} {id} {tls} {args}`) по директиве не вызывается ни разу; один раз она запускается при старте цели без операции (ниже).
- Здесь первопричина — сам движок. Даже с участниками, которые поднялись (C1), эти 49 шагов остались бы красными. Шаги после них (`transport`, `expectation`) отнесены к C1 и C3 по своей причине.

Повтор replay188 (`trace/P_01_3_group.jsonl`, `stderr/P_01_3_group.txt`) подтвердил:
- у всех 49 шагов в трассе `request_sent` — текст директивы как в таблице: `@sigterm store@s3`, `@store-op s1 admit s3`, `@store-op s1 recover -peers s1@{raft@s1}/{api@s1} -isolated`, `@tls inputs/door-on-raft.json` и т. д.; `{raft@…}`, `{api@…}` не подставлены. Наблюдения нет: к кандидату ничего не отправлялось;
- в stderr цели нет ни одного процесса `store-op` по директиве и ни одного перезапуска. Есть только 7 отказов старта участников (C1), старт стендового хранилища и один отказ `refused: start_flags: a positional word of the daemon`;
- этот отказ — побочный дефект того же класса. Движок запускает `stand.store-op` один раз как стендовую команду при старте цели: интерфейс цели `runner-targets.tsv:7`, `run.go:266–283` → `run_stand.go:96–129`, с подстановками `{id}=acceptance`, `{tls}=0`, `{args}=''` (`run_stand.go:174`). Кандидат получает пустую операцию: `cmd/configstore-tool/adapters.go:181–196` передаёт `''` первым словом демону, а тот отвечает отказом `start_flags`. На шаги это не влияет: исход одноразовой команды движок только пишет в `calls`.

Красный этих шагов не зависит от ответа кандидата.

## Норма
J-вход `49e62279`, `Platform/common/acceptance/README.md`:
- `:648` `@sigterm store@<id>` / `@sigkill store@<id>` — «stop the member; the data directory remains; the expectation `ok` — the process exited»;
- `:649` `@restart store@<id>` — «start a stopped member with the same command, with the same flags, directory and kit»;
- `:650` `@cut`/`@mend store@<id>` — прокси бегуна на raft-адресе голосующего;
- `:651` `@store-op <id> <operation> …` — по команде `store-op` «Stand», ожидание `ok` — код 0, `refused` — код ≠ 0;
- `:652–653` `@tls` к `raft@<id>` и `api@<id>` — форма исхода README `tls/`;
- `:301` `@sleep <seconds>` — «wait».

## Код кандидата
Не вызывался. Для справки: `cmd/configstore-tool/dispatch.go:31` (`store-op`), `adapters.go:188–203` (`recover`, `import`, `restore`, `backup` через демон). TLS-транспорт raft — `internal/daemon/group_net.go`, проверка имени двери — `internal/daemon/daemon.go` (`loadKit`).

## Что видела модель
Не относится к модели. Таблицу директив модель прочла (журнал, вызов 32).

## Мнение
Исход — **движок**. Норма однозначна. Пробел движка: стенд группы реализован на треть (подготовка и старт, и те неверно, C1, C2). Вторая причина — **цикл линии судьи**: P02.40 закрыла `rules` и `breadth` 345/345, хотя для директив стенда группы нет исполнения. Ворота, видимо, принимают `red stand` за допустимый исход.

## Вопросы ревьюеру
1. Нужно ли правило ворот линии судьи: каждая директива словаря README, которая встречается в судимых сценариях цели, исполняется на верной заглушке и даёт GREEN; `red stand <имя директивы>` в воротах — красное ворот?
