# Ревью ADR-0083 (156) Variant B — достаточность публичных носителей для семейного суждения (Kimi)

Предмет: задание Dispatcher `KIMI-PUBLIC-FAMILY-CONTRACT-SUFFICIENCY-TASK.json`
(sha256 `ca1c779fdb139759dfa9c705863f14c33a3bba3df0da4e2118ae7431131c08ac`), ADR-0083 доп. (156),
Variant B: достаточны ли публичные носители (`Platform/common/LAYERS.md`, `Platform/common/data/**`,
`Platform/common/vectors/family-read/**` + необходимые публичные зависимости по фактическим ссылкам) для семейного
adjudication БЕЗ чтения `tools/normgen/**` (v7/stack.py и любых private-oracle носителей). Sole acceptor — coord103-src;
нормативные gaps — Architect через SRC.

Baseline (prospective, объявляю полные пины): Source `244355d161139bd6fe65fd68c7e5134598c21ba3`
(parent `061f004970584dd8a279b6ae9808238a1a68e3dd`), export `d5e76008659836735e7e9b21a6d4e1e67391a027`.
Это baseline-чтение, не выбор финального Owner pin; текущий main не подставлял. Прочитаны только публичные носители;
реализация, peer-отчёты, outcome metadata, архивы и формальные модели не открывались; ничего не запускалось.

## Вывод

**Публичных носителей достаточно для семейного adjudication без v7/stack.py по всем аспектам матрицы — с одним
блокирующим нормативным конфликтом (Г-1) и двумя мелкими непрояснённостями (Г-2, Г-3).** Контракт LAYERS.md +
data-носители + векторы family-read определяют форму семей, кодек строк, ключи, места отказов, выбор reader outcomes
и формат ответа так, что ожидания векторов воспроизводятся из правил для всех проверенных семей, кроме 12 строк
`family-read/01.tsv` (Г-1), где опубликованное ожидание противоречит опубликованному правилу выбора outcome.
Итог: sufficiency — условно достаточно; нормативных gaps — 1 (Г-1), мелких — 2 (Г-2, Г-3); остальное — пределы
покрытия векторами, а не пробелы носителей.

## Прочитано (фактический состав)

- `Platform/common/LAYERS.md` — 174 строки, целиком: §1 файлы, §2 семь слоёв, §3 слова схемы + Expression,
  §4 fine check текста, §5 CEL, §6 семьи (ключи, места отказа), §7 outcomes (V7-OUTCOME-SELECT-01), §8 scalars.
- `Platform/common/data/`: `README.md` (каталог + шаблон ключа, обе таблицы placeholders), `catalog.tsv`
  (172 семьи), `codec.tsv` (9 типов: string/integer/number/boolean/time/array/encoding json/encoding jcs/null),
  `common.layers.tsv` (13 мест x-*), `common.schema.json` (807 строк, помечен «reference, not a norm»),
  `key-placeholders.tsv` (49 грамматик), `outcome-units.tsv` (row/field/element), `cell-json-sha256.tsv`
  (хэши байт-сохранности ячеек, baseline `2ebffcaa59ab7694fb90d7f6d29410b44adcd619`), `testsub/` (README + 2 манифеста).
- `Platform/common/vectors/family-read/`: `README.md` + `01.tsv` (109 строк), `02.tsv` (586), `03.tsv` (1192),
  `04.tsv` (1514), `05.tsv` (1141), `06.tsv` (1314), `08.tsv` (3359), `09.tsv` (1668) — все строки охвачены
  (полные тексты прочитаны для 01 и репрезентативных строк остальных; по остальным — все колонки метаданных
  case/family/key/kind/mode/who/verdict/paths/outcome/note, громоздкая колонка `text` сверялась выборочно; это предел
  способа чтения, не предел носителя).
- Необходимые публичные зависимости по фактическим ссылкам: `Platform/common/vectors/wire.tsv`/`wire.md`
  (строки `common/family-read` для 01,02,03,04,06; владельцы 01-store, 02-installer, 03-worker, 04-controller,
  06-console); семейные схемы, `*.layers.tsv`, `*.outcomes.tsv` в `Platform/NN-*/data/` (149 outcomes-таблиц,
  включая `slots.domain.outcomes.tsv`/`heartbeats.domain.outcomes.tsv` для формы `schema#word`).

## Матрица anchor / applicability / gap

| Аспект семейного суждения | LAYERS.md | data-носители | векторы family-read | Статус |
|---|---|---|---|---|
| Типизация строк (codec items) | §1, §2 слой 3, §3 writer/reader | `codec.tsv` — все 9 типов, две нотации, signed до tolerance | integer exact decimal (1e0/-0.0/1.5/100.00000000000000001 — отказы), number (valid_until «1.0» ok), boolean («true» ok), time, list-нотация, null-отсутствие, json/jcs | покрыто (якорь: `codec.tsv` + §3) |
| Слой-3 x-* keywords | §3 таблица слов | `common.layers.tsv`; слова в семейных схемах (публичные, по ссылкам каталога) | x-time, x-integer, x-whole, x-max-names (02-a17), x-max-bytes (06-a09, rids/0), x-encoding jcs writer-canonical (08-0843), x-opaque (book `value`, имя «Bad Name!»), x-file (05: root null, «a\n», not JSON) | покрыто |
| Key placeholders / grammar | §6 «The key» | `data/README.md` §Key + `key-placeholders.tsv` (49 грамматик) + таблица по семьям | 462+ строк «catalog key» + k-серия 01; покрыто ~24 placeholder'а из 49 | покрыто (выводимость полная; покрытие векторами не исчерпывающее — предел) |
| Reader outcomes | §7 формат строки + 4 шага V7-OUTCOME-SELECT-01 + `schema#word` | `outcome-units.tsv`; `<family>.outcomes.tsv` (149, публичные) | per-role outcomes; field/element-unit строки сообщаются своим путём ([/doc/lines], [/short], [/status], [/*], [/revision], [/until]); row-unit приоритет ([/floor] pri 0 бьёт "" pri 2) | **конфликт — Г-1** (12 строк 01.tsv) |
| Order / output (формат ответа) | §6 «The answer is a set of paths» | — | README: `{"verdict","paths","outcome"}`, paths множество; wire.tsv: native object/json, paths set, outcome object-sets | покрыто |
| Отказы / unreadable | §6 таблица мест отказа (слой 4) | каталог kind (row/object/file) | root null (196 row/54 object/16 file), not JSON (120), uniqueItems `/units/1`, propertyNames `//entries`, enum `.` `/units/0`, pattern `free-` `/rids/0`, `zz_extra` | покрыто, кроме не-UTF-8 файла (нет вектора — предел носителя-ячейки) |
| Границы / пределы | §3 Expression, §2 слой 2 | `codec.tsv` пределы, грамматики | 2^53 (9007199254740992), FILE_MAX (8388608 ok / 8388609 `/files/a.js/size`), Z-10 folder 1000/1001, 1e400 вне binary64 (`/doc`, `/floor`, writer не падает), time ≤3 дробных цифры (1.0001 отказ, 1.123 ok) | покрыто (overflow time «не по форме» — правило есть, примера нет: предел) |
| Производные / формулы | §6 `<manifest:X>` | `key-placeholders.tsv` | sha16(name)/manifest:X — суд по грамматике, манифест не читается; JCS — RFC 8785 по ссылке | покрыто |

## Gaps (для SRC → Architect)

### Г-1. Блокирует. Опубликованные ожидания `family-read/01.tsv` противоречат опубликованному правилу §7 для epoch_floor

**Точные публичные якоря.**
- Правило: `Platform/common/LAYERS.md` §7 «Choice of the outcome» (V7-OUTCOME-SELECT-01), шаги 2–3: для пути
  отказа q действуют покрывающие строки наибольшей глубины; среди них field/element-unit строки исключают менее
  глубокие.
- Данные: `Platform/01-store/data/epoch_floor.outcomes.tsv`: `/generation_at  *  …  1  field` и
  `""  <s>worker  …  2  row`.
- Векторы: `Platform/common/vectors/family-read/01.tsv` строки `01-0028, 01-0030, 01-0032, 01-0034, 01-0036,
  01-0058, 01-0060, 01-0062, 01-0064, 01-0066, 01-0068, 01-0070` (reader, единственный путь `/generation_at`,
  ожидание `{"<s>worker": [""]}`).

**Что не выводится.** По §7 для q=`/generation_at` покрывающие строки — `/generation_at` (глубина 1, unit field)
и `""` (глубина 0); наибольшая глубина — `/generation_at`, среди deepest есть field-unit → действует только она →
ожидаемый ответ `{"<s>worker": ["/generation_at"]}`. Опубликованное ожидание `[""]` из этих носителей не выводится:
чтобы его получить, `/generation_at`-строку надо проигнорировать, а это прямо противоречит шагу 3. Контрольная
проверка по соседним семьям с той же структурой приоритетов даёт обратное: `04-controller/data/controller-pass.outcomes.tsv`
(`/short * field pri 1`, `"" pri 2`) → `04.tsv` `04-1156` ожидает `{"<s>worker": ["/short"], …}`; `08-domain/data/grants.outcomes.tsv`
(`/doc/lines * element pri 0`, `"" pri 1`) → `08.tsv` `08-1850` ожидает `["/doc/lines"]`. То есть векторы применяют
правило «deepest field/element wins» везде, кроме epoch_floor. Публичный адъюдикатор без чтения реализации не может
одновременно удовлетворить §7+outcomes-таблице и этим 12 строкам: носители конфликтуют. Какая сторона нормативна —
из публичных носителей не следует (семантически ["/generation_at"] означает «поле не читается, эпоха выдаётся по floor»,
что согласуется с текстом строки outcomes; [""] — «строка нечитаема целиком», что тексту `/generation_at`-строки
противоречит).

### Г-2. Мелкое. Значение `-` в колонке `schema` каталога не определено

**Якорь.** `catalog.tsv` — 15 семей со `schema` = `-` (`<sub>/idem/<key>`, `<sub>/blobs/sha256-<hex>`,
`<sub>/<manifest:domain.witness.report>/<name>`, файлы `/etc/w2c/tls/*`, `/etc/w2c/configstore-rights.json`,
`/etc/w2c/roles/<role>.env`, `<domain recovery file>`, `%h<sha256>.name`, `~lock`). LAYERS §6 определяет семью через
«the column `schema`»; значение `-` нигде в трёх носителях не расшифровано.
**Что не выводится.** Явное «формы нет — семья вне family-read / байты не судятся». Семьи без векторов, практического
блока нет, но поведение общей функции чтения для `-` из публичных носителей не следует.

### Г-3. Мелкое. Значение `manifest` в колонке `schema` не разрешается тремя носителями; семьи не покрыты

**Якорь.** `catalog.tsv` — 8 семей со `schema` = `manifest`: `<sub>/<manifest:unit.rows>/<id>`,
`<sub>/<manifest:tables>/<name>`, `objects/<sub>/<manifest:objects.rows>`(±`/*`),
`<sub>/<manifest:domain.books.from>`(±`/<slot>`), `domain/<sub>/<manifest:domain.kept>`(±`/*`). Ни LAYERS, ни
data/README, ни векторы не говорят, как из объявления манифеста (P/02.1, вне скоупа) строится форма семьи; в
family-read эти семьи не покрыты (проверено: в `0*.tsv` их нет; `platform/memberof/<sub>/<manifest:unit.rows>/<id>`
и `domain/memberof/…` — другие семьи, со своими схемами).
**Что не выводится.** Из трёх носителей не выводится ни конструкция формы, ни рабочий пример ожиданий для этих
семей в family-read (потребительские обязанности есть у пакета `row-check` с манифестами как fixtures, но это не
алгоритм построения формы). Для adjudication по family-read блока нет (векторов нет), но при расширении покрытия
понадобится публичное правило разрешения.

## Пределы (не нормативные gaps)

- **Покрытие векторами, а не выводимость.** Правила публичны и полны; экземпляров нет: (а) «a file that is not UTF-8»
  (§6, последняя строка таблицы) — TSV-ячейка по построению UTF-8, сырой невалидной последовательности в векторах нет;
  (б) time overflow «не по форме» (`codec.tsv`, MAY-UNTIL-D8-01) — примера нет; (в) ~25 placeholder'ов из 49 без
  catalog-key векторов (например `<box>`, `<place>`, `<volume>`, `<sha16(name)>`, `<hex>`, `<form>`, `<root>`, `<i>`,
  `<object-key>`, `<path>`, `<dir>`, `<sha256>`, `<n>`, `<tree>`, `<kind>`, `<relay>`, `<cluster>`, `<ref>`,
  `<domain recovery file>`, корневые `<events/objects root>`).
- **Wire.** `wire.tsv` объявляет привязки `common/family-read` только для 01,02,03,04,06 (владельцы 01-store…06-console);
  таблицы 05,08,09 опубликованы, но wire-строк не имеют — README family-read это фиксирует дословно, «A missing
  binding is an undeclared adapter» (wire.md). Зелень через wire на этом baseline — только P/01,02,03,04,06;
  ожидания 05/08/09 остаются читаемыми носителями без объявленного исполнительного surface.
- **Роли writer-режима.** `who` writer извлекается из прозы колонки `ops` каталога (роли — префиксы `<role>=`);
  правило публично (README family-read), но извлечение — не машинно-тривиально. Несоответствий в проверенных строках нет.
- **Способ чтения векторов.** Все 10 883 строк охвачены по метаданным; полные `text` прочитаны для 01.tsv и
  репрезентативных строк 02–09 (base, отказы, add-кейсы, Z-10/ADR-маркеры). Проверка построчной согласованности
  `text`↔`paths`↔`outcome` для каждой строки не выполнялась (это аудит векторов, а не его sufficiency).
- **Объём проверки outcomes-таблиц.** Алгоритм §7 сверен на 4 семьях (epoch_floor, configstore-doors, controller-pass,
  grants) + подтверждено существование и форма всех 149 outcomes-таблиц и `*.layers.tsv`; спот-чеки схем с x-* словами.
- **Граница скоупа.** Не оценивались уроки-нормы (P/01…P/10) как носители; они публичны, но вне трёх частей задания.
  Каталог отсылает к ним в колонке `norm`; sufficiency оценивалась для суждения семей по общей библиотеке чтения.

## Пределы самого задания

Report-only: Source не правился, прогонов/моделей/SUT не было, peer-материалы не читались. Настоящее ревью не
переоткрывает P06 и не подменяет production-очередь Dispatcher.
