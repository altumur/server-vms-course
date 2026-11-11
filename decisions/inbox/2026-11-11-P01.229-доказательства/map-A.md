# P01.229 часть (А): карта переноса

База: `db52c3a18` (ветка task/P01.229), правки не закоммичены. Историю (происхождение, номера ADR) часть (А) не чистила, кроме
одной фразы в перенесённом в P/01 тексте (см. ниже).

## Разделы общего README → новые места (en; ru — те же пути с `ru/`, русские якоря)

| Было (`Platform/common/acceptance/README.md#…`) | Стало |
|---|---|
| `#assembly-example` | `Platform/common/acceptance/stand.md#assembly-example` |
| `#layout-by-processes-stage-c` | `Platform/common/acceptance/stand.md#layout-by-processes-stage-c` |
| `#environment-of-stand-processes` | `Platform/common/acceptance/stand.md#environment-of-stand-processes` |
| `#stand-without-root` | `Platform/common/acceptance/stand.md#stand-without-root` |
| `#testsub-process-stand` | `Platform/common/acceptance/testsub-stand.md#testsub-process-stand` |
| `#table-header-and-columns-by-name` | `Platform/common/acceptance/tables.md#table-header-and-columns-by-name` |
| `#target-registry-and-export-lists-assembled-from-the-lessons` | `Platform/common/acceptance/tables.md#target-registry-and-export-lists-assembled-from-the-lessons` |
| `#command-tables` | `Platform/common/acceptance/command-tables.md#command-tables` |
| `#loader-verdicts` | `Platform/common/acceptance/command-tables.md#loader-verdicts` |
| `#installation-sequences` | `Platform/common/acceptance/command-tables.md#installation-sequences` |
| `#rights-variants` | `Platform/common/acceptance/command-tables.md#rights-variants` |
| `#seam-adapter-protocol` | `Platform/common/acceptance/seams.md#seam-adapter-protocol` |
| `#procedure-and-peer-ownership` | `Platform/common/acceptance/seams.md#procedure-and-peer-ownership` |
| `#call-input-and-observation` | `Platform/common/acceptance/seams.md#call-input-and-observation` |
| `#explicit-test-side-seam-bridge` | `Platform/common/acceptance/seams.md#explicit-test-side-seam-bridge` |
| `#d7-test-side-evidence-bindings` | `Platform/common/acceptance/seams.md#d7-test-side-evidence-bindings` |
| `#stand-in-worker-of-the-pass-of-the-second-kind` | `Platform/common/acceptance/pass/README.md#stand-in-worker-of-the-pass-of-the-second-kind` |
| `#store-group-stand` | `Platform/01-store/acceptance/3/README.md#store-group-stand` |
| `#three-server-cluster-stand` | `Platform/common/acceptance/system/README.md#three-server-cluster-stand` |
| `#domain-stand` | `Platform/common/acceptance/domain-stand.md#domain-stand` |
| `#domain-vector-commands` | `Platform/common/acceptance/domain-stand.md#domain-vector-commands` |
| `#multi-cluster-stand` | `Platform/common/acceptance/domain-stand.md#multi-cluster-stand` |

README.md теперь: шапка, «Stand — common…» (h2, якорь прежний), «Topics» (указатель: прежние имена тем → файл), «Dictionary of directives
and doors» целиком (якорь прежний; VMS ссылается только на README.md и этот якорь). В словарь добавлены: строки `@stream-open`,
`@stream-wait`, `@stream-none`, `@stream-close` (определения перенесены из «Stand-in worker…», их берёт VMS/11 «as in the common
platform README»); сроки `@stream-open` 30 s и `@together` 150 s — в «Terms of the stand» (третья ячейка — что судится); указатели
«формы — урок/тема, definition: ссылка» для директив стенда передачи (P/06, pass/README.md), стенда группы (P/01,
acceptance/3), стенда трёх серверов (system/README.md), стенда нескольких кластеров (domain-stand.md). Срок `@person` — в
domain-stand.md («Term of `@person`»).

## Пункты и абзацы одного урока

| Было | Стало |
|---|---|
| Layout «Rights check command» | `Platform/02-installer/acceptance/5/README.md` «Profile interface» |
| Layout «Copy commands» | `Platform/01-store/acceptance/3/README.md` «Stand» |
| Layout «Pass report print command» | `Platform/04-controller/acceptance/README.md` «Stand» |
| Layout «Durability» | `Platform/01-store/acceptance/1/README.md` «Profile interface» |
| D7 абзац «For the bindings of the target `P/01/production` the words of the payload mean…» | `Platform/01-store/acceptance/3/README.md` «Production qualification coverage» (M, как было) |
| «Stand-in worker of the pass of the second kind» без `@stream-*`, `@together`, `@person` | `Platform/common/acceptance/pass/README.md#stand-in-worker-of-the-pass-of-the-second-kind` |
| «Store group stand» | `Platform/01-store/acceptance/3/README.md#store-group-stand` |
| «Three-server cluster stand» | `Platform/common/acceptance/system/README.md#three-server-cluster-stand` |

## Файлы (git mv)

| Было | Стало |
|---|---|
| `Platform/common/acceptance/forms/extra.tsv` | `Platform/01-store/forms/extra.tsv` |
| `Platform/common/acceptance/forms/extra.scenarios.tsv` | `Platform/01-store/forms/extra.scenarios.tsv` |
| `Platform/common/acceptance/forms/process-1.1.scenarios.tsv` | `Platform/01-store/forms/process-1.1.scenarios.tsv` |
| `Platform/common/acceptance/forms/process-1.3.scenarios.tsv` | `Platform/01-store/forms/process-1.3.scenarios.tsv` |
| `Platform/common/acceptance/forms/production.tsv` | `Platform/01-store/forms/production.tsv` |
| `Platform/common/acceptance/forms/production-input.schema.json` | `Platform/01-store/forms/production-input.schema.json` |
| `Platform/common/acceptance/production/{README.md,bindings.tsv,input.json}` | `Platform/01-store/forms/production/…` |
| `Platform/common/ru/acceptance/production/README.md` | `Platform/01-store/ru/forms/production/README.md` |

**Отступление от ответа Архитектора (место), причина — check_spec, навык не правится:** `check_spec` (`lesson()`): «acceptance of a lesson
with chapters holds only chapter directories acceptance/K/», а в каталоге главы — закрытый список входов (`supported`; иное — только
исключением `acceptance-entry` в `skills/lesson-spec/exceptions.tsv`). Поэтому `extra*.tsv`, `process-1.x.scenarios.tsv` в
`acceptance/1|3/` и каталог `acceptance/production/` у P/01 дают ERROR; формы P/01 легли в `Platform/01-store/forms/` (как прочие формы
урока, ADR-0135 доп. (14) п. 2), данные стенда — в `forms/production/`. Тот же запрет держит `pass/` и `ops/` в общем каталоге: у P/06
главы, `Platform/06-console/acceptance/pass|ops/` — ERROR. **pass/ и ops/ не перенесены** (цели PASS/stand, OPS/stand, owner 06-console):
нужна правка навыка Архитектором (исключение или поддержка каталога стенда у урока). Раздел «Stand-in worker…» лёг в pass/README.md.

## Новые слова движка (для P01.201)

- **extra**: «the rows of forms/extra.tsv **of the lesson of the target** (Platform/NN-<process>/forms/extra.tsv) for the target» (было
  `forms/extra.tsv` общего каталога); `extra.scenarios.tsv` — рядом, в `tables` строки маршрута (`Platform/01-store/forms/extra.scenarios.tsv`).
- **production**: «the rows of forms/production.tsv of the lesson of the target» (было общего каталога); данные стенда —
  `Platform/01-store/forms/production/` (bindings.tsv, input.json); схема входа N6.2 — `Platform/01-store/forms/production-input.schema.json`.
- **run** P/01.1/door, **l11** P/01.3/daemon: `tables` → `Platform/01-store/forms/process-1.1.scenarios.tsv`, `process-1.3.scenarios.tsv`.
- Шапка `Platform/common/acceptance/forms/targets.routing.tsv` (строка 2) переписана для extra и production; строки маршрутов P/01 — новые пути.

## Фильтры выгрузки

Перенесённые записи сняты с общих фильтров и вписаны в `Platform/01-store/forms/export.json` с прежним disposition (basis «P01.229: moved
from <old path> …»). Шесть тем + шесть переводов — в общих фильтрах: en как README.md (M `model_and_judge`, J `include`), ru как ru/README.md
(M `judge_only`, J `exclude`). `export_lists.assemble`: 0 ошибок, 3549 записей M и J.

## Правки вне acceptance/ уроков (только адрес ссылки или norm_anchors; проверено: diff без имён файлов пуст)

`Platform/01-store/README.md` и ru (кроме того — «What this lesson takes from common» переписана на нужные темы: README.md «Stand», словарь;
stand.md; tables.md «Table header…»; seams.md; system/README.md + «Three-server cluster stand»; строка стенда группы и копий снята — они в уроке),
`Platform/01-store/spec/01.{1,2,3}-store.norms.md` и ru (адреса файлов строк указателя `seam_bridge`, `group_stand`),
`Platform/01-store/spec/production-acceptance.md` и ru, `Platform/01-store/forms/targets.tsv`, `targets.routing.tsv`,
`Platform/02-installer/forms/README.md` (+ru), `forms/targets.tsv`, `Platform/03-worker/forms/README.md` (+ru), `forms/targets.tsv`,
`Platform/09-agent/lifecycle.md`, `spec/09-agent.README.md`, `spec/09.1-agent.norms.md`, `spec/09.2-agent.norms.md` (+ru, + лекция ru/09-agent.md),
`Platform/10-domain-console/lifecycle.md`, `spec/10-domain-console.README.md` (+ru, + лекция ru/10-domain-console.md).
VMS не тронут; `check_spec --scope vms` на базе и на дереве — rc 0, 0 ошибок.

## Что не сделано и почему

- pass/, ops/ → P/06: запрет check_spec (выше).
- Текстовые отсылки ««Domain stand» / «Stand without root» / «Installation sequences» … of the common acceptance README» в нормах, lifecycle
  и acceptance P/02–P/10 (около 70 мест, en+ru) не переписаны: README держит указатель тем с прежними именами, отсылки остаются верны;
  переписывать слова вне acceptance/ разрешения нет. Ссылки Markdown и norm_anchors на перенесённые якоря переписаны все (global_fix: 180 замен).
- Директивы `@view-*`, `@rev-*`, `@row-spoil`, `@shell-put`, `@stderr`, `@parallel`, `@read`, `@admin` больше не названы в ru README после
  «Словарь директив» (были в command-tables/seams/domain-stand); в scenarios.tsv Platform и VMS их нет (check_spec platform и vms зелёные) —
  это слова puts.tsv/seams.tsv со своими проверками.
- Перенесённый в P/01 текст «Store group stand» нёс «(the Architect's decision of 2026-10-30)» — m_form P/01 даёт ERROR, фраза снята,
  строка в `decisions/journal/platform/01-store/history-3.tsv`. Остальная история перенесённых в P/01, P/02, P/04 и в общие темы текстов —
  часть (Б). В P/01 3/README добавлены judge-only к `inputs/group.json`, `group.json` (judge_only_refs P/01), `tls/` → ссылка на TLS-стенд.
- Дубль: «Durability» (теперь acceptance/1 P/01) повторяет `lifecycle.md` P/01 строки 73, 84 — не сводил (смысл).

## Проверка

`check_spec --scope platform`: rc 0 (`A-check.log`). Против лога приёма P01.176 на db52c3a18
(`/home/pilot/.local/state/cammeta-watch/check-logs/check_spec-db52c3a18909-1794427110.log`): anchored_files 98→110 (+12 тем),
english_mirrors 374→380 (+6 пар), export_* 3537→3549 (+12 записей), history_rows 307→308, judge_only_refs 110→114, local_links 10138→10188
(указатель, строки-указатели словаря, ссылки на новые файлы). Прочие счёты равны.
Новые файлы не в индексе git: `git add` шести тем и шести переводов нужен при коммите.

