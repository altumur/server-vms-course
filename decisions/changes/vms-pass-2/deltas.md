# Дельты vms-pass-2

`02-installer/spec/`: схема и разделы `worker.writes`.

`03-worker/spec/`
- MODIFIED `03.1` Н2: слово `stalled(id)`; `03.3` Н1.2 `stalled`.
- MODIFIED `03.4` Н1.1 `headroom`, Н1.6 `rows`, `list_secret`; `03.4`, `03.7` таблица пульса.
- MODIFIED `03.6` Н1.2 `suppress`, Н1.5 журнал и `rid`.

`06-console/spec/`: `06.1` Н1.6 `rows`; `06.2` `holders`, `rotate`, Н3 «перезапечатать при старте».

`common/contracts/`
- MODIFIED `gate-and-pass.md` `need`, «Передача»; `domain-token.md` таблица `expect`; `row-check.md` П2, таблица отказов.

Сборка книг (Quint V/03.6 В1): `08.5` Н1.3 `bad_contribution`, Н3 шаг 4а; `03.7` Н1.2 `same_key`; `vectors/assemble/cases.tsv`, `README.md`.

Запрос событий (вопрос 8): `events-merge.md` `query`, `by`; `05-resource` Н1.3, Н3 «запрос», Н4, OpenAPI, приёмка сц. 35; `06-console` OpenAPI, 06.4 Н4; `gate-and-pass.md` «Числовые параметры query».

`03.4`: `domain/holder` в списке «читает», исключение P/03 снято.

Данные: `catalog.tsv` `domain/holder`, `holder.outcomes.tsv`, раздел семей `08.8`, `family-read/08.tsv`.
