# X4 — MiniMax 8: группа строк write-checks проверяется «строка за строкой», а не «элемент за элементом»

**Случаев:** P/01/vectors-write-checks, 1 строка из 83 — `write-checks.probes.tsv:78` (J). У Opus 8 цель GREEN 83/83.

## Норма (M)
- `forms/write-checks.tsv:4–5`: «group — consecutive rows with one group form a group: each binds the index and the element of a list (i, w in body.writes), the group applies to the elements in order, element i as a whole before element i + 1».
- `spec/01.1-store.norms.md:380`: первая нарушенная строка даёт код и вид отказа; `:383`: родной вывод пакета — `{"n": <первая нарушенная строка>, "code", "kind"}`.
- Пакет определён в M: `spec/01.1-store.norms.md:383`, `common/vectors/wire.md:147–154`, `common/vectors/probe-tables.tsv:16`. Пробы — только у судьи (`wire.md:147`, «judge-only»).

## Случай (J)
`write-checks.probes.tsv:78`: `22 pair writer {"op":"batch","writes":[{"op":"delete","key":"acc/a","cas":"x"}, 5]}`.
Элемент 0 нарушает строку 22 (`wc-write_cas`, `write-checks.tsv:42`). Элемент 1 (`5`) нарушает строку 17 (`wc-write_object`, `:37`). По `:5` элемент 0 проверяется целиком раньше элемента 1, ответ — `n: 22`. Обе строки дают `400 badrequest`, расходится только `n`.

## Наблюдение движка
`minimax8/out/minimax8/P_01_vectors-write-checks/engine.json`, `rows`: `line-78`, `red implementation`, `native output differs from the expected row` (`vector/run.go:614` снимка 340fbb39).

## Код кандидата
`internal/model/table.go:125–137`: внешний цикл — по строкам формы; `evaluateGroup` `:174–206` для одной строки обходит все элементы списка. Строка 17 проверяется на всех элементах раньше строки 22 на элементе 0, вывод — `n: 17`. Вывод окна по коду; бинарник окно не запускало.

Тест `TestWriteChecksPrecedence` (`internal/model/write_checks_test.go:67–88`) проверяет порядок строк 1–9 на одиночных командах; батча из двух элементов с разными нарушениями нет. Мутации формы (`minimax8/form-mutation/report.md`, write-checks 68/68 «ровно так») меняют только `code` и `kind` строки и порядок элементов не видят.

## Что видела модель
- Строка `:5` формы — в голове этапа `model`, раунд 1 (`round-001.json`, сообщение 1).
- Ворота `vectors:write-checks` этапа `model` (`stages.tsv:24`) цикл не исполнял: этап закрыт воротами `mech` 15/15 (`passport.json`, `stages.model.gates`). Проба профиля пишет `"01-store/write-checks": "the wire form assigns no vectors table of this package to the module"` (`passport.json`, `profile_probe`, все записи). Полнота профиля помечает цель `not_required`: «M has no definition: M has no vector package 01-store/write-checks (Platform/01-store/vectors/write-checks/README.md)» (`passport.json`, `profile_completeness`, с раунда 10001). Это неверно: пакет определён в M (см. «Норма»). Правильная причина — пробы только у судьи.
- Модель всё равно объявила `vectors.01-store/write-checks` (`acceptance.yaml`) и собрала `cmd/vector-write-checks`.
- Догадки нет.

## Мнение окна
Исход — **кандидат**. Норма прямо в форме, форма в голове. Причина по доп. (44): **модель (без обратной связи)**: пробы судейские, ворот по ним быть не могло. Вторая — **цикл**, мелкая: ложная причина «в M нет определения» в полноте профиля (надо: «пробы только у судьи; пакет определён, `optional`», `targets.tsv:18`).
