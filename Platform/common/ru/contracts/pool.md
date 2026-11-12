# Договор пула: живой воркер, пул, хранитель места, пригодность сервера

Текст производный от `contracts/pool.md`, руками не правится: источник — английский [`contracts/pool.md`](../../contracts/pool.md), правка идёт в него, русский пересобирается переводом (ADR-0121; ADR-0124 доп. (1) п. 4).

Общий договор модуля «Платформа» (ADR-0083 доп. (5), доп. (13), доп. (30): общий алгоритм нескольких процессов — договор, а не
копии в главах; догадка стадии C C06-SERVER-POLICY-33-01, решение «Архитектора» 2026-10-25). Владелец — урок
[P/04](../../../04-controller/ru/spec/04-controller.norms.md) (N3 «выбрать»: контроллер размещает единицы только на воркеры пула).
Участник — консоль кластера ([P/06.5](../../../06-console/ru/spec/06.5-console.norms.md) N2: `WorkerRow.idle_by_policy`,
`ServerRow.placeable`, `why`): тот же расчёт по своим чтениям и своим часам.

Перенесено из P/04 N3 «выбрать» (строки «живой воркер», «пул», «хранитель») без изменения поведения контроллера; для взгляда
консоли, о котором P/04 молчал, — четыре ответа «Архитектора» 2026-10-25 (разделы ниже, помечены). Что единица требует
сверх пула (`constraint`, `spread_by`, `affinity`, группа, дом, ёмкость и порядок) — по-прежнему P/04 N3 «выбрать», строка
«пригодные» и ниже.

Нормативные слова — по [канону курса](../NORMATIVE-TERMS.md).

## Форма

Строки и объекты, которые читает расчёт пула, — по формам и исходам их семей (аудит раскладки, V-42–V-44, B-07; решение «Архитектора» 2026-10-25): пульс `<sub>/heartbeats/<name>`
— `Platform/03-worker/data/heartbeats.schema.json`, `Platform/03-worker/data/heartbeats.outcomes.tsv`; слот `<sub>/slots/<name>` —
`Platform/03-worker/data/slots.schema.json`, `Platform/03-worker/data/slots.outcomes.tsv`; назначение `<sub>/workers/<name>` —
`Platform/04-controller/data/workers.schema.json`, `Platform/04-controller/data/workers.outcomes.tsv`; строка заказа
`<sub>/want/<host>` — `Platform/04-controller/data/want.schema.json`, `Platform/04-controller/data/want.outcomes.tsv`; решение
`<sub>/controller/placement_intent` — `Platform/04-controller/data/placement-intent.schema.json`,
`Platform/04-controller/data/placement-intent.outcomes.tsv`; вывод `<sub>/decommissioned/<host>` —
`Platform/04-controller/data/decommissioned.schema.json`, `Platform/04-controller/data/decommissioned.outcomes.tsv`; дренаж
`platform/drain` — `Platform/06-console/data/drain.schema.json`, `Platform/06-console/data/drain.outcomes.tsv`; запрос вывода
`platform/decommission/<host>` — `Platform/06-console/data/decommission.schema.json`,
`Platform/06-console/data/decommission.outcomes.tsv`.

## Живой воркер

```yaml
live:      пульс <sub>/heartbeats/<имя> читается и менялся в последние LOST_AFTER по часам читающего (договор наблюдения
           «Свежесть»; граница — вектор fresh-age) ∧ строка слота <sub>/slots/<имя> читается, released = false (не отдан и не в
           захвате taking — slots.schema.json), holder непуст; пульс, чьё worker ≠ имени в ключе (heartbeats.schema.json), не читается —
           воркера нет
```

## Пул

```yaml
pool:      живые воркеры
           − отданные слоты
           − воркеры дренируемого сервера (platform/drain, drain.schema.json) и выведенных серверов (договор наблюдения «Сервер выведен»: читаемая строка platform/decommission/<s> или
             <sub>/decommissioned/<s>; нечитаемая — не факт, не вычитать, как правило want_rule; ответ «Архитектора» 2026-10-25)
           − при requires: resource — воркеры сервера, чей ресурс silent (resource_state договора наблюдения; unknown — не
             факт, воркер проходит)
           − retiring строк заказа <sub>/want/<сервер> (поле retiring, want.schema.json; ADR-0084)
           − процессы роли с номером больше want своего сервера (имя и номер — договор имени слота «Имя процесса роли и его
             номер»; ADR-0084 доп. (4) R28)
           − воркеры с нечитаемой строкой назначения <sub>/workers/<имя> (P/04 N4 «пульс/слот/назначение не читается»;
             у консоли — так же, ответ (3))
           − при servers: distinct — все, кроме хранителя своего места (раздел ниже)
want_rule: retiring и «номер выше want» применяются только при grows: true и только к процессам сервера, чья строка заказа
           <sub>/want/<сервер> читается: grows: false — не применяются; строки заказа сервера нет — не применяются к его
           процессам; строка нечитаема — не применяются (скрипт сервера по ней не останавливает — P/02.4 N1.5; контроллер —
           ошибка шага 9, P/04 N4); retiring — только из читаемой строки (POOL-WANT-33-01, решение «Архитектора» 2026-10-25)
```

## Хранитель места при `distinct`

```yaml
place:     место воркера — по place_by манифеста (умолчание server): сервер или поле пульса; значение "" из пульса — места нет
           (как у spread_by), общего места "" не бывает (ADR-0084 доп. (2) R15; перенесено из P/04 N1.3 place_by — аудит раскладки, решение «Архитектора» 2026-10-25, B-07)
keeper:    у каждого непустого места — один хранитель среди воркеров пула до вычитания distinct: наибольшая нагрузка, при
           равенстве — первый в слотовом порядке (договор имени слота); воркер без места не хранитель
load:      нагрузка — одно определение со «свободно» P/04 N3: сумма весов уникальных id, назначенных воркеру (строка
           <sub>/workers/<имя>) или направленных к нему эффективным решением (резерв active intent — договор наблюдения «Чтение решения»; B-07); строки
           назначения нет — нагрузка 0; не число единиц (ответ (2))
weight:    вес id — поле placement.weight.field его строки единицы, целое ≥ 1 (P/04 N1.3); поля нет — weight.default; у
           манифеста без placement.weight — 1; строки единицы нет, она нечитаема или поле не целое ≥ 1 — 0 (C06-POOL-FACTS-33-01,
           решение «Архитектора» 2026-10-25)
count:     счёт — число всех назначенных id (с резервом intent), читаемы их строки или нет
capacity:  ёмкость — поле пульса placement.capacity.from (умолчание capacity); поля нет — capacity.default (обязателен); поле
           есть, но не число (слово, булево) — воркер не принимает новых единиц, пока пульс не исправлен, уже назначенные не
           снимаются, причина — в отчёте прохода, поле fates.<воркер>.why: «capacity is not a number» (как вес, R25);
           unit_mb/base_mb — бюджет памяти воркера при старте (P/03.4) (перенесено из P/04 N1.3 capacity; аудит раскладки, решение «Архитектора» 2026-10-25, A-12)
```

Нагрузка и её резерв active intent — точные неотрицательные целые весовые агрегаты, не число записей. Складывать и сравнивать их без сужения, округления или насыщения через binary64/int64, включая выбор хранителя и вычитание нагрузки из свободной ёмкости. Их JSON-выход имеет целочисленную запись без потолка common.uint53. Отдельные веса, ёмкость и прочие счётчики сохраняют формы; пределы сериализованных объектов прежние (P/04-R007, R050).

## `idle_by_policy` (ответ (1))

```yaml
idle_by_policy: true — при servers: distinct живой воркер пула до вычитания distinct, который не хранитель своего места,
           и живой воркер без места (""); иначе false — в том числе у воркера, который не живой, и всегда при shared
```

## Пригодность сервера: `placeable`, `why` (ответ (4))

```yaml
placeable: true — на сервере есть живой воркер пула (пул уже вычитает requires: resource при silent, дренаж и вывод
           сервера, отданные слоты, retiring, номер выше want, distinct); метки — свойство единицы и в placeable не входят;
           ёмкость не входит
why:       при placeable: false — «no eligible live worker»; при true — поля нет
```

## Векторы

Пакет [`pool`](../vectors/pool/README.md): вход — пульсы (кто живой), слоты, назначения, строки единиц, серверы (дренаж,
вывод, заказ), ресурсы, манифест; выход — пул, хранители, `idle_by_policy`, `placeable`/`why`, нагрузка и счёт. Живость пульса по истории — пакет
[`fresh-age`](../vectors/fresh-age/README.md) и [`resource-state`](../vectors/resource-state/README.md); `constraint`,
`spread_by`, `affinity`, порядок выбора — P/04, сценарии и чтение. Участник: пакет [`slot-name`](../vectors/slot-name/README.md)
— пакет общего договора slot-name, исполняет common; этот договор там — участник (слотовый порядок —
хранитель при равенстве нагрузки; V-44; CM-RECORD-VECTORS-128, решение «Архитектора» 2026-10-25).

Ячейка `input` таблицы `cases.tsv` — один объект JSON (чтения подменены входом). `manifest` — `{prefix, servers, place_by?, requires, grows?, weight?: {field, default}, capacity?: {from, default}}`: `prefix` — `slot.prefix` манифеста (по нему слотовый порядок и разбор имени процесса роли `<prefix>-<server>-<n>`), `servers` — `shared` или `distinct`, `place_by` — `server` или поле пульса, `requires` — `none` или `resource`, `grows` — логическое значение, `from` у `capacity` — поле пульса во входе `heartbeats`. `heartbeats` — `{<worker>: {server, <place_by field>?}}`, прочитанные пульсы; `live` — воркеры, чей пульс менялся в последние `LOST_AFTER`; `slots` — `{<worker>: {released: "false" | "true" | "taking", holder}}`, нет записи — строки слота нет; `assignments` — `{<worker>: [<id>…] | "@garbled"}`, строки назначения, нет записи — строки нет; `units` — `{<id>: <unit row> | "@garbled"}`, элементы текстом, нет записи — строки нет (вес 0); `intent` — `{target, members}`, active intent (резерв нагрузки), или нет поля; `drain` — дренируемый сервер (`""` — нет), `decommissioned` — выведенные серверы; `resources` — `{<server>: live | silent | unknown}`, `resource_state`; `wants` — `{<server>: {want, retiring?} | "@garbled"}`, строки заказа, нет записи — строки нет.

Родной выход — объект JSON `{pool, keepers, idle_by_policy, placeable, load, count}`: `pool` — массив воркеров в слотовом порядке; `keepers` — `{<place>: <worker>}`, хранители при `distinct`; `idle_by_policy` — `{<worker>: bool}` у каждого прочитанного пульса; `placeable` — `{<server>: {placeable, why?}}` у серверов пульсов и ресурсов; `load` и `count` — `{<worker>: n}` у воркеров с читаемым назначением (нечитаемое — записи нет). При `manifest.capacity` в выходе ещё `capacity`, `{<worker>: <count> | null}` (`null` — поле не число: новых единиц не принимает), и `fates`, `{<worker>: {why}}` (поле отчёта прохода контроллера; консоль считает все поля, кроме `fates`).

