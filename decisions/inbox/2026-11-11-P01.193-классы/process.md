# P01.193: процессные красные (чтение)

Срезы: J `49e622795ca96b2e73904f1da5d203f2d103b2d5`, M `bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae`; engine b244d533 из P01.245; MiniMax candidate git 77b90bef; Claude source P01.188/cand-diag. Исполнение кандидатов/движков, сборки и тесты — 0. Служебные артефакты и чужие деревья не изменены.

## 1. HEAD copy: две красные единицы, класс «норма»

Оба отчёта P01.192 `out-diag/{claude,attempt6}/P_01_3_daemon/engine.json`, `rows` table `Platform/common/acceptance/forms/process-1.3.scenarios.tsv`, physical line10, case 32-copy-raw: статус 405 при ожидании200, длина тела 0.

- J process-1.3.scenarios.tsv:10: `admin HEAD /v1/copy` → `200 @empty`.
- M P01/spec/01.3-store.norms.md:315–318 P/01.3-R033: неподдерживаемый метод405/Allow: GET, HEAD без тела. HEAD не объявлен поддерживаемым методом, перечислен только GET. В M checklist P/01.3-12 :479 повторяет method 405 / Allow: GET / HEAD без тела.
- J P01/spec/production-acceptance.md:77 RUN-H02 и :132: unsupported method 405 / Allow: GET, HEAD без тела. Таким образом противоречие есть и внутри J; M здесь лишь дополнительное подтверждение.
- Engine core/scenrun.go:890–898 проверяет фактический код по числу exp.Code; core/http.go:191–193 в режимеHEAD возвращает пустое тело. Отдельного специального ожидания HEAD движок не добавляет.
- Claude candidate internal/door/service.go:16,20–23: serviceMethods[copy]=GET, HEAD даёт wrongMethod; :42–46 возвращает CopyMethod и NoBody. internal/httpd/server.go:259–261 тоже подавляет тело для HEAD.
- MM candidate 01-store/door/request.go:186–189 отвергает метод, отличный от GET; :208–213 строит405 Allow: GET и omitBody для HEAD. 01-store/door/response.go:130–158 тело не пишет при omitBody.

Правка: исправить ожидание J на405 @empty с отдельной проверкой Allow: GET (или разрешённой единственной @header после @empty). Это не ошибка кандидатов и не основание подгонять их HEAD к200. Нынешний движок честно исполнил ошибочное ожидание. Происхождение до предыдущего среза не исследовано.

## 2. Два точных заголовка Claude: класс «кандидат»

P01.192 `out-diag/claude/P_01_1_door/engine.json`, rows process-1.1.scenarios.tsv:9,11: `header Connection differs`. Тело 63 байта SHA-256 `9d497e314ddd51bee9bcb70f17073d48132eb3f93625c39d662eea6da9abd575` в обеих строках.

- J AC/README.md:344: `@header Name: =text` требует присутствия **ровно один раз** и равенства байт в байт; process-1.1.scenarios.tsv:9,11 требует Connection=close.
- Engine core/scenrun.go:908–915: len(vals)!=1 или vals[0]!=Text → red. HTTP parser core/http.go:183–189 сохраняет каждый header отдельно. Проверка соответствует J.
- Claude internal/refusals/refusals.tsv:27 `input_timeout` уже содержит `Connection: close`.
- internal/refusals/refusals.go:71–74 читает этот заголовок, :115–123 переносит его в Fault.
- internal/httpd/server.go:194–208 на timeout вызывает writeFault; :226–228 помимо готовых заголовков выставляет resp.Close=true.
- :244–249 пишет все resp.Headers, затем :253–255 ещё раз пишет Connection: close из resp.Close. Получаются **две строки** Connection: close. Это конкретный путь, объясняющий оба наблюдённых mismatch; тело/заголовки сами отчётом не сохранены, механизм установлен кодом.

Правка кандидата: печатать Connection: close однократно, согласовать готовый заголовок Fault и принудительное закрытие HTTP. Движок в этом месте прав. У MiniMax эта причина не возникает: writeRawResult печатает единственную Connection: close; его строки9,11 GREEN.

## 3. MM import: одна красная единица, класс «кандидат»

P01.192 `out-diag/attempt6/P_01_3_daemon/engine.json`, steps P01/acceptance/3/scenarios.tsv:38, 11-copy#1: import refused (code 1); следующие 10 шагов not_executed 11-copy#1.

- J P01/acceptance/3/scenarios.tsv:38: `@import store inputs/copy-ok.jsonl` → ok.
- J P01/acceptance/3/inputs/copy-ok.jsonl:1–2: index 7, floor 4294967296, generation_at `1760745600.5`.
- J AC/README.md:299: import получает новый пустой data, index_base из header. core/directive.go:574–592 создаёт новый data/configstore и подставляет index 7; :596 исполняет команду профиля; :605–607 при code 1 выдаёт наблюдённое red. Чужой отказ по build/runtime здесь не выдуман.
- J P01/data/epoch_floor.schema.json:13–18 generation_at ссылается на common.time, :813–819 описывает time N0 P/01.1. M P/01.1-R006 :41–45 и R007/R008 :47–55 задают Unix-секунды, а не RFC3339.
- MM 01-store/daemon/copy_admin.go:68–78 читает и разбирает copy, :88–90 вызывает importPlan; :115–118 → copy.Prepare.
- MM 01-store/copy/plan.go:63–78 читает generation_at и вызывает parseTimestamp.
- MM 01-store/copy/timestamp.go:11–16 требует RFC3339 и отвергает `1760745600.5` по длине/позициям. Отказ безусловен для точного входа J, не зависит от текущей даты, времени и окружения. Вызов Main возвращает ненулевой код CLI по ошибке RunImport (cmd/configstore/main.go:39–41).

Правка кандидата: читать и писать time в форме существующего N0, убрать RFC3339 из формы epoch_floor; это та же категория «неверная форма времени», что подлежит проверке всего пути floor/import/recover, а не исправление одного файла.

## 4. E4 — четыре временных red: класс «движок», вердикт не обеспечен требуемыми наблюдениями

Claude process-1.1.tsv:7 (нет close к 10 с), :8 (ответ после @by(10)), :10 (ответ после @by(30)); MiniMax :10 (ответ после @by(30)). Наблюдённые детали именно таковы; численные времена отчётом не сохранены.

- J AC/README.md:349: @by считается от начала шага и требует отдельно записать разрешение часов/планирования; предел не расширяется.
- J process-1.1.scenarios.tsv:7–10 задаёт 10/30 с. Заголовок:1–2 называет это первым утверждённым бюджетом оценки из production-acceptance. J P01/spec/production-acceptance.md:37–38 BUDGET_HEADERS 10, BUDGET_BODY 30, :68 требует **точные начальные события фаз** R147.
- M P/01.1-R147 :390–391: header от первого байта строки запроса; body от полных заголовков, устанавливающих тело. Это позже начала шага.
- Claude internal/httpd/server.go:24–27 объявляет header 10 с / body 30 с; :141–163 реализует первый байт → срок заголовков и полные заголовки → срок тела; :194–212 отдаёт 400 после timeout и закрывает. Этот код сам по себе не доказывает задержку сверх своего фазового срока.
- MM 01-store/door/types.go:145–150 объявляет header 5 с / body 30 с; request.go:86–92 header после первого байта, :134–143 body после полных заголовков. header у MM зелёный, body на границе 30 с красный.
- Engine core/http.go:68 начинает время **до dial**; :78–82 deadline @by для @noreply — ровно start+10; ожидание response/close:89–97; :144–146 Elapsed=time.Since(start) вычисляется после ожидания close. Core/scenrun.go:750–765 выбирает WaitClose=by, :854–861 классифицирует timeout при @noreply как implementation; :871–872 сравнивает итоговый Elapsed с by.
- Отчёт хранит только detail и BodyInfo(hash/len/type). Ни Elapsed, ни время первого/последнего ответа/close, ни начальные события фаз, ни разрешения часов/планирования в этих rows не записаны. Нет оснований выбирать между малым сдвигом начальной точки, планированием и реальным опозданием; нельзя объявлять подтверждённый сбой среды.

Итог E4: «движок: временной вердикт не обеспечен требуемой записью разрешения часов/планирования и точек измерения». Четыре строки не названы ложными red; кандидатам не приписываются ни опоздание, ни исправность, среде — сбой. Правка движка: разнести события начала фазы, ответа и закрытия, сохранять численные наблюдения и требуемую разрешающую способность часов и планирования.

Разрешение измерения не считать прибавкой к пределу. Несогласованные начала сроков — отдельный пункт списка проверки нормы; их вклад в фактический результат этих red не установлен. Из сохранённых файлов точную монотонную трассу восстановить нельзя; новый запуск не поручен.

## Доп. (44)

Четыре поля (красные ворота / раунды и бюджет / догадка / тест) для этих новых кандидатских классов по журналам модели этим подразбором не установлены. Метка «модель при обратной связи» не ставится. Суд во время генерации кандидаты не видели. Это не новое свидетельство модели и не разрешение достраивать поля догадкой.
