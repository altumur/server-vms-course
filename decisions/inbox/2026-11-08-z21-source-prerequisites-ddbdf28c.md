# З21: согласование существующих Source prerequisites с Code32

Состояние: исходный компонент для совместной композиции; не приёмка реализации, профиля или общего GATE.

## Основание и граница

Обычный дочерний источник от `ddbdf28c366386d421374ac6493eedf773d09df9`. Поручение a08866fb и уточнение 21ff948b исполняют фиксированное слово владельца 4167f025 в существующей задаче З21/139. Старые ветки целиком и их родители не переносятся.

Принятые источники: P06 S08 `b45425690d0db3fa74e3b7d4bdce4289918c67ec`; локальный role-контракт `285f713746e72cb7cfd659fb8cc8e2251134f604`; публичное представление `039a6e7939823547e9d5c06945d08f434097e618`. Квитанции SRC 7ef3986a/b9b965e6, 7ee53b25 и ee874368 используются выводами, без повторной проверки архивов.

Из текущего P06 API извлечены прежние шесть inline PathItems в стандартные `components.pathItems`: `UnitsCollection`, `UnitItem`, `TableCollection`, `TableItem`, `PassRoot`, `ConsoleFile`. Из `paths` убраны только эти шаблонные записи. Их нынешние тела, параметры, операции, ответы, reference bases и все остальные узлы API сохранены. Специализация остаётся по принятому каталогу; новый endpoint, URI, полномочие или fallback не вводится. Нормы и forms README EN/RU получают ровно ранее принятые пояснения этого представления.

В deleting добавлены только локальные `$defs.person_writer` / `$defs.role_writer` и две строки слоёв. Прежний ключ выбирает person `{at,done?}` или role `{}`; объединение без ключа, универсальный required-at и новый discriminator не вводятся. EN/RU получают ранее принятый ключевой контекст вне generated marker и явные публичные таблицы профилей. Нынешние `common.time`, общий префикс, корень читателя, writer name limit, исходы и все остальные нормы сохраняются. Это контрактный вход, не доказательство конкретного key/setA/SUT-профиля.

## Точные исходные носители

| Путь | До SHA256 | После SHA256 |
|---|---|---|
| `Platform/06-console/spec/06-console.api.openapi.yaml` | `79cb9d28884f0546f6c190246d516b7a615772e32ab4dcf1706ad957657bbf23` | `5eef7c762f270b9608d7a8318d8432cf6bc7334a73d24c4e4e7bf10c20079be9` |
| `Platform/06-console/forms/README.md` | `8eb42d3fff9d30388603a49214da18a710370c5acb53f0dbe3c4758796db21e8` | `1ecb11d63d966acb597a84473539ad41e65a5ee370573e07ebcf8ec114911ee8` |
| `Platform/06-console/spec/06.5-console.norms.md` | `9d77f471d58cdb415ae4d4ccd61e1c81edcb3206982f43dadcfe1b8a2d6cea3d` | `0161d7cd8a3f2238b4ec21c866abdbf52d570d143cc6647b18436d2068e55cfe` |
| `Platform/06-console/ru/forms/README.md` | `760396684c0cb977d2eb9a4588d80404abf903ad376773eae1769f0826519162` | `eb4951280bc507dc55f42c93a3aebded5bb366ad0bdecd4edeb8be821d27a718` |
| `Platform/06-console/ru/spec/06.5-console.norms.md` | `0521566c0e256ea50e2cfa9a1c22e15ca16b892630c2fa4005a4d25d8dce51eb` | `e39514882fc73835fd3dd435660f448248fb2497d29ad13e997ed7e7b4214931` |
| `Platform/08-domain/data/deleting.schema.json` | `f831fe3c886ed9da72128cf4891cc5dd165ed8dce59d9b1471126faa54401a00` | `c70b806fbb1ae266accc847b34eeb84779768cc74ced35100211dedef75f7d08` |
| `Platform/08-domain/data/deleting.layers.tsv` | `9d8a8b7e9c99cf9905eeac4d3e5c60de2fd9cacd49a7cadd55c7a047985d473a` | `20b146f5d5ab3ab05e6f88ee28de69ad7ce0443725b6ab6d4dc81146ca327a70` |
| `Platform/08-domain/spec/08.4-domain.norms.md` | `3f3c723c260a79373ff6f4e436a303a08ca10da0fd26f45eb8d2582d4b942e07` | `34eebb2b2ef39fdbdeb89a3ebc3f9e5181492d3ebeaf4ce3305eabf9e56eeabc` |
| `Platform/08-domain/ru/spec/08.4-domain.norms.md` | `0d71e800867c4d31d6fa09e3ab3452db7d9cc5fb8ae163797cfedd4b9780aa8c` | `d9a64df5253ba1c86134c115a6637b372a66fe8d8f4604484ad14c4601dbd13b` |

Итого девять Source-путей, 17 непересекающихся raw blocks; собственные метаданные — только эта запись. Нормативные req ID, значения, отказы, API операции и корпуса не изменяются, поэтому новый normative change/accepted/applied не оформляется.

## Проверка изменённого входа

Авторские ограниченные проверки: 71 PASS. Обратное raw-преобразование девяти файлов восстанавливает исходные байты. Обратное структурное преобразование всего API восстанавливает исходное дерево: 140 операций совпадают. Строгие публичные readers принятого Code32 (совместный кодовый вход c769481b, компонент 7dc4a58a) разобрали параметры 19 операций шести PathItems и разрешили 63 ссылки их замыкания без генерации. Прямые внешние цели этих ссылок — только текущие P05 API и common gate-and-pass API; отдельного переноса P09A не требуется.

Строгий contextual constructor принял точную семью `domain/deleting/<name>` и оба определения; отрицательные проверки отсутствующего person/role и чужой identity отклонены. JSON Schema 2020-12 синтаксически корректна; восемь структурных profile controls отличают обязательный person-at, запрещённые дополнительные поля и role `{}`. Эти controls не проверяют codec Time или admission. Публичные EN/RU writer-таблицы совпадают с выводом этого узкого consumer. Три изменённые EN/RU пары без mirror-ошибок; новые ссылки существуют, новые английские вставки без кириллицы.

Все 21 Source-blob принятого `ecb501b3582834ad4181d8e3e6dc23e4dfd0df5d` сохранены. CommonPROFILE5977, CP6, tools/skills, Source/VMS, family08, 15 dependent declarations, metadata16, P07/J1 и прочие записи текущего main вне этой границы остаются прежними. Старые Source21 34/33, старые strict/conditional/fixture-программы и архивы не повторялись.

## Передача и пределы

Producer coordinates: `Platform/06-console/spec/06-console.api.openapi.yaml#/components/pathItems/{UnitsCollection,UnitItem,TableCollection,TableItem,PassRoot,ConsoleFile}`; `Platform/08-domain/data/deleting.schema.json#/$defs/person_writer` и `#/$defs/role_writer`; соответствующие layers и EN/RU таблицы. Исходный production endpoint `Platform/01-store/spec/production-acceptance.md` остаётся байтово точным ecb.

Внешний пакет `z21-source-prerequisites-ddbdf28c-20261108` содержит Source declaration с UTF8/codepoint/LF координатами, исходными blob/SHA/mode/length, after bytes, целевые controls, preservation и финальный FREEZE/producer input. Точный опубликованный commit фиксируется там после обычного commit/push.

Проверки полного Source/tools milestone выполняет tools на новом входе. Здесь full9/strict, генерация, codec, runtime, SUT/Go/HTTP/stand/model и GATE не выполнялись; SourceREADY не объявляется. Все 17 production-групп NOT_EXECUTED, бюджеты null, qualified provider UNKNOWN. Старые 41/ce8+c10, пакеты, installed/export/model pins и остальные owner holds не меняются.
