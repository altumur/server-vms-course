# Ревью дельты фильтров выгрузки M/J b603f6479..e3f65994a (P02.34, 4278ba13d, Claude)

Ревьюер — kimi (окно judge P02.41). Работа: автор run (P02.34), провайдер claude, редакция
`4278ba13df552bd9d518a60e7113923462120d6a` (один поверх `59d4f2154`, влит в main). Только чтение:
`git diff`/покоммитный разбор дельты, парсинг TSV/JSON, сверки хешей; код курса и пробы не запускались.

Граница. В задаче (P02.41) формулировка «дельта … без P02.34», но конечные блобы названы
`50eb811c`/`31e6150c` — это результат P02.34, `review_of: P02.34`. Читал так: дельта двух фильтров
`b603f6479..e3f65994a` (коммиты P01.136 ×2, OBSH.39.1 ×2, OBSH.39.3, P01.142, P01.149, P02.34)
целиком, включая фильтры-правки P02.34 и прочие его файлы (реестр, README, комплект).

**Итог: Б 0, С 0, М 0 — принять (CLEAN).**

## Проверки цели (ADR-0133 доп. (4) п. 1)

Верно:

- **M — в model_and_judge из «только для судьи» не попало ничего.** За всю дельту в
  `model_and_judge` добавились только: `common/acceptance/forms/d7-payload.schema.json` (P01.136),
  `02-installer/forms/code-rules.tsv` (P02.32, без expected answers, как у P/01), и флип двух README
  (P02.34). Корпус `02-installer/acceptance/1/spec_verdicts` — все 140 файлов `judge_only`; данные
  стенда D7 `common/acceptance/production/*` — `judge_only` (P01.136); `verdicts.tsv`,
  `expect.tsv` (все варианты P/02), `acceptance/3/puts/*.subsystem.yaml` — `judge_only`;
  мутантов в дереве Platform нет (`git ls-tree -r | grep -ci mutant` = 0). Историческая дельта
  коммитов 1–7 — чистые добавления `judge_only`/как надо, без флипов.
- **d7-payload.schema.json в M — модельно-видимая форма без ответов.** Прочитан целиком: JSON Schema
  2020-12 (oneOf activate четырёх capability, $defs наблюдений/переходов, типы/enum/паттерны);
  числовых норм не задаёт («The schema sets no numeric value of a norm»), ожиданий и данных случаев нет.
- **J — вне J не попало ничего.** Дельта J = +14 include (13 файлов P02.35 + `code-rules.tsv`)
  и 1824 флипа `exclude→include`, все в пределах: `02-installer/{acceptance,data,forms,vectors}`
  (1101/24/19/243), шесть общих пакетов `common/vectors` (env-file 3, loopback 3, sealing 6,
  domain-backup-key 2, domain-founding 4, yaml-suite 405 = 423) и `06-console/acceptance/5/inputs/testsub2`
  (14). Иных изменений (include→exclude, добавления вне этих каталогов) нет.

## Реестр и маршруты P/02 (по ответу Архитектора 2026-11-11T04:38:57Z)

Верно:

- **26+26 строк.** `targets.tsv` и `targets.routing.tsv` получили по 26 строк P/02; порядок строк
  в routing совпадает с targets; по 8/6 колонок, без обрывов.
- **23 из runner-targets без P/02.1/put, общие ячейки байт-в-байт.** Сверено csv-парсингом по 6 общим
  колонкам против `runner-targets.tsv`: 22 строки равны; у `P/02.1/inproc` добавлен `flags=["optional"]`
  (как у `P/01.1/inproc`).
- **Исключения по ответу:** `P/02/vectors-canonical` ← `P/02.2/vectors` и `P/02/vectors-workers-script`
  ← `P/02.4/vectors` (имена пакетов); условие `rights_check` перенесено с `P/02.5/rights`
  (`when` опустел) на `P/02.5/variants` (условие на месте, `check.tsv` вызывает `stand.rights-check`).
- **3 новые строки:** `P/02.1/seams` (run, `acceptance/1` — у каталога нет `scenarios.tsv`, есть
  `seams.tsv`), `P/02.4/seams` (run, `acceptance/4` + `acceptance/2` для манифеста testsub,
  requirements `01-store`+`02-installer`), `P/02.5/variants` (variants, `acceptance/5`).
- **Слова движка:** verdicts — `P/02.1/load`, `P/02.1/inproc`; puts — `P/02.2/put` (tables
  `acceptance/2/puts-ceiling.tsv` + каталог `vectors/canonical` под `# canonical:`) и `P/02.3/put`
  (каталог `06-console/acceptance/5/inputs/testsub2` под `# beside:`); run — `P/02.5/rights`
  (+`common/data/testsub`), обе seams; variants — `P/02.5/variants`; vector — 18 строк над 17
  каталогами = 16 пакетов + canonical (каталоги входов `acceptance/1/cases`, `acceptance/2/puts`,
  `common/data/testsub` на месте), `env-file` обслуживает две строки (`env-line`, `env-files`).
  Части 01-store — `store1` (обе puts) и `store` (rights, variants). У `P/02/vectors-log-mask`
  нет `secret-in` (нет потребителя P/02).
- **README EN/RU** (`targets.README.md`): оба обновлены согласованно, называют отличия от
  runner-targets (переименования, перенос `rights_check`, `P/02.1/put` не цель — нет выборки
  установки, три строки только в реестре).
- **Фильтры = git ls-files Platform + прежний COURSE_COMMIT:** 3514 файлов на диске, множества
  путей M и J равны (по 3515, дублей нет); лишний только фантомный `Platform/COURSE_COMMIT`
  (на диске отсутствует, прежний, в квитанции отмечен).
- **Раскладка J:** `acceptance/**`, `data/**`, `forms/**`, `vectors/**` P/02 → include
  (`verdicts.tsv` include); `README.md`, `lifecycle.md`, `spec/**`, `ru/**` P/02 → exclude;
  `spec_verdicts` 140/140 exclude (основание в фильтре: «Verdict corpus; never judge input
  (ADR-0135 (2) item 1)»; подтверждено и ADR-0133 стр. 246). Все 25 каталогов и файлов маршрута P/02
  существуют и целиком include в J, кроме spec_verdicts.
- **Раскладка M:** `acceptance/1/README.md` и `vectors/install-order/README.md` → model_and_judge
  (как README остальных пакетов P/02 и acceptance/1 P/01); 13 файлов P02.35 → judge_only;
  `code-rules.tsv` → model_and_judge. Основания (basis) у новых/флипнутых записей точны по задачам.
- **Комплект** `decisions/changes/0133-p02-registry-filters`: таблицы блобов и SHA256 в change.md
  и delta.md сходятся с git-объектами (парсил из файла, сверял `rev-parse`/`sha256sum` всех 6 артефактов).
- **Доказательства автора:** лог `check_spec-4278ba13d.txt` существует, финал «PASS structural
  checks only».

## Наблюдения вне дельты (не против P02.34)

- basis J у 16 исключений P/02 (`README.md`, `lifecycle.md`, `spec/**`) говорит «…nor data of P/01» —
  текст с прежних времён (так же на `59d4f2154`), косметика; disposition верные.
- Замечания автора вне участка подтверждаю: `02-installer/acceptance/1/README.md` (строка 19 —
  `dup_top_key_name` называет строку 36, `unknown_depth4`; строка 23 — шесть ok-файлов корпуса с
  `testsub`) и `02-installer/acceptance/4/README.md` (строка 15 — «not … a new public stand target»:
  при появлении цели реестра `P/02.4/seams` фраза устарела; участок 2г).

Счёт: **Б 0, С 0, М 0**. Рекомендация: **принять**; работа соответствует ответу Архитектора
2026-11-11T04:38:57Z и ограничениям ADR-0133/ADR-0135.
