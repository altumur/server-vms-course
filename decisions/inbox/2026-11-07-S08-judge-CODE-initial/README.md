# S08: начальный CODE-допуск двух существующих тестовых файлов

**Разрешены CODE и только 18 новых именованных Python-групп.** Пакет `b3e9a580329c316d8517f5964cf595b335641f713b9d928df460a8f00fc0809e` рассмотрен как исправление существующего судьи S08/J06. Base — `43750c8ef574ae4af747f481433fd7f4e0045793`; будущие Source-пины не подмешиваются. Полная машинная граница — [APPROVAL.json](APPROVAL.json).

## Файлы и сохранность

Разрешены только `tools/normgen/test_gen_door_lesson.py` и `tools/normgen/test_gen_door_bodies.py`. Canonical CHANGED-BLOCKS `a6a6d3ba…` задаёт **16 mutable blocks + 6 insertion anchors**. Устаревшее «14» OB17 не действует: новый guard проверяет все 16. Якорь разрешает вставку, а не правку соседнего кода. Все прочие блоки и третий CODE-файл заморожены.

DRIVER с единственной `%module`-подстановкой, run, ввод Method/Path/ID, старый result4|err, read_report/disagree/CheckingError и freshness остаются byte-equal. В 19 старых RouteServiceControls разрешены только два прямо названных fixture executor assignment: `mutant_case` и `test_complete_before_oracle`; их assertions и checking-смысл прежние. Остальные 18 test methods и 6 BodyServiceControls неизменны. В старых test_probes/test_mutants меняются только два вызова executor; dictionary/inputs/applicability/comparison/survivor loop сохраняются.

## Независимый Source и точные идентичности

Model/bindings читают полный исходный Source с исходными document/base/pointer/owner-контекстами, шесть standard PathItems и отдельный GIVEN-каталог. Producer selector/privateSpec/generated allocation не служат expected. SourceSchemaReader получает operation_declarations и точные parameter-координаты; прежние input/coercion/report subspans и typed-ref/oracle-ограничения сохраняются.

Утверждён фиксированный identity witness `decisions/inbox/2026-11-07-p06-s08-source/operation-map.json` на437, SHA256 `af5920d7fb4e73055b33229f9a65c330bc021d4e780e9cd7719b46531d547f19`; его API SHA `b4073b39c35094aba8bd6cecefd0f63f5cc2c37abc867e72a0b81eaa4c7b189e`. Старые140 expected чисел — `logical_ordinal_original140` 1–140 с именами/координатами этой неизменяемой карты. Содержание операций читается из текущего закреплённого Source; старая карта не доказывает новую семантику или admission.

Добавленные source-witness значения закреплены явно:

| Op | Число |
|---|---|
| OpHeadFolders | 141 |
| OpHeadFoldersById | 142 |
| OpHeadBySubOperationsById | 143 |
| OpHeadChanges | 144 |
| OpHeadBySubNextId | 145 |
| OpHeadApiBackupPartByMemberByPart | 146 |

Actual producer не выбирает expected-числа. Несовпадение/отсутствие witness/API не лечится перенумерацией или fallback.

Смысл прежнего `Match.Sub` сохраняется: короткий root-path — пустой Sub; явно названный root — `testsub`; mount — `testsub2`. Effective root короткого пути — отдельная premise `testsub`, а не новое значение capture Sub.

## Контекст и отдельное наблюдение

Только manual P/06.5 pair `testsub`/`testsub2` с точными двумя COMPLETE view SHA из пакета и explicit nonempty root=`testsub`, принадлежащим этому контексту. GIVEN уже принятые immutable views — условие изолированной проверки, не доказательство нынешних P02 admission/startup/row-view-mark/profile/Б1/N5/B,V. Автоматический four-manifest контекст и220 независимых случаев не объединяются с этой парой. Положительного pass второго вида здесь нет: он остаётся отдельной предпосылкой, не закрывается каркасом.

Owned companion реализует существующий CatalogSnapshot в отдельной копии; same-package observer лишь снимает actual Match/Op/provenance. Go-тест не сравнивает expected-маршруты. Протокол `1dacdf4a…` сохраняет singleton package/test Go-json и отдельный новый0600 O_EXCL private файл с полными meta0/routes/end, typed IDs/run/context/counts/EOF. Полный normal lifecycle, строгий transport и валидная premise обязательны до любого semantic comparison. Service-accounting helper complete_go_tests читается только из неизменяемого test_gen_machine SHA `3f4b8adc…`, диапазон53–110; этот третий файл не меняется и не предоставляет oracle.

Compile/start/panic/nonzero/partial/context/ambiguous Code0 остаются CheckingError, не kill. Валидный Match.Op0 — actual число, а не RouteError.Code0: после полного trusted отчёта неверный Op сравнивается с Source. Полный unfiltered actual Ops145/147 с согласованными counters может дать semantic mismatch; усечённый или выдуманный transport — CheckingError. Raw references без координат/кратности не доказывают оба carrier; raw parameter lists не выдают за отсутствующие effective bindings.

## Начальное выполнение

Сейчас разрешены только запись CODE, syntax/raw/AST проверки и **именованные OB01–OB18 Python-группы** с синтетическими NDJSON/FS-фикстурами и injected process outcomes. Они обозначаются mocks, а не реальными Go-событиями. Никакого full class/module discovery, старых service suites, настоящего setUpClass/P06 setUp или материализации B1/Cobs/Cmut, companion/provider/observer. Go-шаблон можно написать строкой; запуск или материализация требует следующего отдельного составного scope. В настоящем будущем P06 тесте новый instance setUp должен гарантировать normal observer baseline до legacy comparisons; пропущенная premise не превращается в скрытый boolean fallback.

Обязательные applicable Source-obligations имеют отдельные ID, ненулевые входы и zero mandatory misses. Старый optional/random10% остаётся отдельным. Prefix-lost/all405/pattern/rank сохраняются; неприменённый или выживший обязательный мутант остаётся GAP/FAIL, проверочная ошибка не засчитывается убийством.

Поставка — normal child437 с ровно двумя файлами, картами сохранности и раздельным авторским Python-отчётом. Успех этих18 групп не разрешает actual observer/Go/render/generated output/full9/KIT/fullstrict/GATE, Source051/P09 adoption, main merge, новый runtime/API/loader/DSL, ms resume или Claude calls. Partial E01/E09/S01/S02/S03 и прочие неисполненные места сохраняются явно. Дополнительный CODE-блок или изменение протокола/контекста — точный запрос до правки.

Архитектор прочитал протокол/границы/plumbing/mutants/context и service-accounting code; отдельно сравнил22 raw Source-spans, неподвижный helper и Source-witness/API hashes. Это чтение и проверка метаданных, без запуска Model/schema/tests/Go. Tools выдаёт конкретную активацию из этого пакета и передаёт автору; повторного подтверждения Архитектора в той же области не нужно.
