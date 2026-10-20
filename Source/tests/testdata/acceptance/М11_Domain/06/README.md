# Приёмка М11/6 — назначение и хранимые правки

[Нормы](../../../../../../М11_Domain/spec/06-assignment.norms.md),
[HTTP-контракт](../../../../../../М11_Domain/spec/06-assignment.api.openapi.yaml),
[лекция](../../../../../../М11_Domain/06-assignment.md).

Сценарии на стенде урока 3; условие `If-Match` двери единиц — сц. 14 приёмки [P/06.1](../../../../../../Platform/06-console/acceptance/1/README.md),
исполнители в теневом отчёте на векторах — пакет [`view`](../../../../../../Platform/08-domain/vectors/view/README.md)
(строки прежнего сц. 10 приёмки М11/01, снятой переносом урока 8), на стенде — сц. 15 приёмки главы 8.1 ([acceptance/1](../../../../../../Platform/08-domain/acceptance/1/README.md)).

## Стенд

Подготовка — как README приёмки [главы 8.3](../../../../../../Platform/08-domain/acceptance/3/README.md) («Стенд», «Подготовка каждого сценария»; прежде — README приёмки М11/03): `hold`, `m1`, `m2`,
каталог `testsub` (`domain.edit: [start, labels]`, `domain.ref: name`). Двери и директивы — раздел «Стенд домена» [общего README приёмки](../../../../../../Platform/common/acceptance/README.md#стенд-домена); у двери `holder` раннер ставит `Idempotency-Key` и у `PUT`/`DELETE`, `@key(N)` повторяет ключ
шага `N`.

## scenarios.tsv

Формат — словарь «Стенда» М10/01 и раздел «Стенд домена» общего README приёмки. `$id` — id хранимой правки из ответа 202. Перенесено: сц. 01, 02, 03,
05, 09 — приёмка главы 8.6 ([acceptance/6](../../../../../../Platform/08-domain/acceptance/6/README.md)), сц. 06 — приёмка главы 8.1 как 15 ([acceptance/1](../../../../../../Platform/08-domain/acceptance/1/README.md)) (стадия B, урок 8).

Всего 3 сценария / 26 шагов.

## corrections.tsv

Журнал исправлений ИИ (ADR-0080 доп. 1): `date`, `sample`, `fix`, `languages`.
