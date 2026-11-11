# D3 — профиль не объявляет векторы общих пакетов: четыре цели `blocked`

**Случаев:** 4 цели, 103 строки `not_executed` (причина `vectors`):

| Цель | Итог движка | Строк |
|---|---|---|
| P/01/vectors-crl | `blocked interface:01-store:vectors:common/crl` | 22 |
| P/01/vectors-revoked | `blocked interface:01-store:vectors:common/revoked` | 21 |
| P/01/vectors-log-mask | `blocked interface:01-store:vectors:common/log-mask` | 39 |
| P/01/vectors-store-client | `blocked interface:01-store:vectors:common/store-client` | 21 |

Пятый общий пакет урока, `common/family-read` (P/01/vectors-family-read), тоже не объявлен. В 12 целях суда P01.188 его нет.

## Наблюдение движка
`out-diag/claude/P_01_vectors-<pkg>/engine.json`: `result: blocked`, `reason: interface:01-store:vectors:common/<pkg>`, строки — `not_executed`, причина `vectors`. Команда кандидата не вызывалась.

Код движка `ef7dcf9` — `internal/engine/run.go:272–275`: `assembly.Command(ref.Owner, ref.Section, ref.Key)` не нашёл ключа в профиле, отсюда `addBlocked("interface:" + …)`. `verdict.go:198–201`: при пустом red итог — `blocked` с первой причиной.

## Норма
M `bf846208`:
- `01-store/spec/01-store.README.md:47`, перечень «what to build», п. 8: «**The vector functions of the shared packages** (the section «Shared vector packages») behind the profile command `vectors`.»
- Там же `:49–59` (§«Shared vector packages»): «the targets of this lesson include the five shared packages of the table. Each is run by the entry of the profile section `vectors` with the key of the table and calls the implementation's own function». Ключи: `common/revoked`, `common/log-mask`, `common/store-client`, `common/family-read`, `common/crl`.
- `common/vectors/consumers.tsv:20, 128, 181, 235` — строки `01-store` для `crl`, `log-mask`, `revoked`, `store-client`.
- `common/acceptance/runner-targets.tsv:93, 100, 122, 137` (в M и J одинаково): `stand_commands` каждой цели — `{"owner":"01-store","section":"vectors","key":"common/<pkg>"}`.
- PROFILE.md:45: поле `vectors` необязательно для профиля вообще. Обязательность для урока задают README урока и `runner-targets.tsv`.

Исход `blocked` по норме:
- `common/acceptance/spec/acceptance.norms.md:57` (P/AC-R007): «`blocked` — a required interface or part of the composition is absent before execution; this is not a test result».
- Там же `:117`: «A target whose required interface is absent is `blocked` in the plan».

Здесь интерфейса нет, поэтому исход верен. В отличие от E5 P01.127: там команда профиля была объявлена и падала, а движок ставил `blocked`/`stand` вместо `implementation`.

## Код кандидата
- `01-store/acceptance.yaml`, `vectors:` — только `01-store/write-checks`, `01-store/jcs`, `01-store/rights-evaluator`.
- `01-store/cmd/configstore-tool/dispatch.go:51–70`, `vector`: ветки только для тех же трёх пакетов, остальное — `default: return 2`.
- Функции под два пакета есть, но к команде вектора не подключены: `internal/tlsx/revoke.go:16` `ReadRevoked`, `:39` `ReadCRL` (их тест — `tlsx_test.go:62`). Разбор ответа хранилища для CLI (`store-client`) и маска журнала (`log-mask`) отдельной функцией под вектор не выделены. Глубже не проверялось.

## Что видела модель
- §«Shared vector packages» и п. 8 модель прочла целиком (вызов 5, `cat spec/01-store.README.md`, 20,5 тыс. знаков без обрезки, строка таблицы `common/crl` в выводе). README пакетов `common/vectors/<pkg>/README.md` в M есть, модель их не открывала. В журнале нет ни одного чтения `common/vectors/{crl,revoked,log-mask,store-client}`, `consumers.tsv` или `runner-targets.tsv`. `wire.tsv` она смотрела через `grep -E "01-store"` (вызов 36), а строки общих пакетов там с `when: true`, без имени урока.
- Таблицы случаев (`cases.tsv`) в M нет: они только для судьи. Нормой это не запрещено: README пакета задаёт функцию и ответ.
- `NOTES.md:48–49`, «Not done / known limits»: «Shared vector packages common/revoked, log-mask, store-client, family-read, crl have no `vectors` entries (the revoked/crl readers exist in `tlsx`, not wired to the vector command).»
- `RETRO-ANSWER.md`, §3: «Checking `revoked`, `crl`, `log-mask`, `store-client` and `family-read` would need their package READMEs and case tables; I did not wire those vectors.» README пакетов в M были.
- Догадки нет. Ворот не было. Модель закончила сама при 40,2 млн из 150 млн и 0,79 ч из 24.

## Мнение
Исход — **кандидат**. Норма однозначна: README урока, `consumers.tsv` и `runner-targets.tsv` M. Исход движка верен.

Причина по доп. (42), (44) — **модель (без обратной связи)**, с сильным признаком доп. (44) п. 2: «модель знала норму … а сделала иначе». Она записала пробел в NOTES и закончила при большом остатке бюджета.

Вторая причина — **обвязка/задание**. Ни одна проверка не требовала команд векторов, а правило окончания Claude Code — «модель закончила ход» (доп. (42) п. 2).

Задания кандидату нет (генерация с нуля). Для сравнения генераций класс засчитывается модели.

## Вопросы ревьюеру
1. Считать ли случаем цель (4) или строку (103)? Строки не исполнялись, поэтому о поведении функций кандидата суд ничего не говорит.
2. Нужна ли в `01-store.README.md` §«Shared vector packages» фраза «a profile without one of these `vectors` keys leaves its target `blocked`, and the lesson is not accepted»? Или достаточно `runner-targets.tsv`, который модель не читала?
