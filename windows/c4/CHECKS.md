# Проверки C4 — итог для чтения

Исходная база окна: ce7f1a83, затем ff9844eae7 (документы мутационной пробы,
Source не менялся). Source: **6d9a8a1787afd2fa4033c9db3939b64857415b85**, tree
**ce218c621e34c4442c8662421ee7c2a8588ccddc**.35 пофайловых коммитов.
Архитектор разрешил слияние c2f66fc9; фактический merge **e24dac956e79c33ec1782620bd217153f63da292**.

| Набор | Результат | Свидетельство |
|---|---|---|
| Первый core |39/2/0, exit1 | targeted-first.log/.exit |
| Второй core |50/0/0, exit0 | targeted-second.log/.exit |
| Core с правами, старыми tokens и boundary |73/0/0, exit0 | core-third.log/.exit |
| Первый полный Cluster |119/2/0, exit1 | cluster-full-first.log/.exit |
| Первый полный Domain |224/4/0, exit1 | domain-full-first.log/.exit |
| Первый полный unit |1935/0/0, exit0 | unit-full-first.log/.exit |
| Финальный полный unit, все160 модулей и console |1935/0/0 (Python1895+JS40), все4 exit0 | unit-part-1…4.log/.exit; unit-summary.json |
| Финальный полный Cluster |121/0/0, exit0 | cluster-full.log/.exit |
| Финальный полный Domain |228/0/0, exit0 | domain-full.log/.exit |
| Финальный полный DomainVMS |166/0/0, exit0 | domainvms-full.log/.exit |
| Target исправлений Device/foreign data |34/0/0, exit0 | domain-migration-targeted.log/.exit |
| Target точных ACL/trace ожиданий |22/0/0, exit0 | cluster-migration-targeted.log/.exit |

Причины первого core: root лишний worker.reads member-topology дал новое
расхождение байтов cam; убрано, чтение общей политики выводится из unit.
После появления unit старый долг upstream.unit неправильно называл уже
известный родитель: уточнён до действительно неизвестных sub/caller C6b.
Оба исправлены, следующие core зелёные.

Причины Cluster: точное ACL ожидание ещё не включало C4 чтения; трасса03
ещё не показывала две новые guarded операции polls. Проверки сохранены,
ожидание уточнено, трасса переснята; в замороженном уроке только4 числовые
цитаты согласно явному исключению cecc0b3e.

Причины Domain: два теста выявили создание слота Device ещё до членства —
исправлена реализация; test_foreign_data ещё ожидал polls в ответе старого
Books — проверка неполного отчёта/сохранности остальных шагов сохранена,
старый издатель polls уже удалён; topology scenario переведён на C4 путь, прежняя проверка no-restart сохранена.

## Тест → судьба

- Прежние assigned C2/C3b transport-тесты: сохранить поведение целиком.
- test_lesson10_cluster_of_one: сохранить число boot-записей и отсутствие
  записи heartbeat на flash до вступления, исправить преждевременный слот.
- test_foreign_data torn bundle: сохранить неполноту и независимость шагов;
  вместо старой стадии polls проверять, что её нет у Books.
- test_topology no restart, lesson16 unrecorded/scenario/holder move,
  lesson17 unrecorded relay: перенести стенд на slot-owned publishers,
  принятые отчёты, generic collect и локальную роль. Не создавать фиктивных
  назначений, не подменять полную книгу flat словарём.
- Новый generic unit binding: две testsub, accepted report, подпись/роль,
  отзыв unit/member, повреждения, topology/holder moves, closed loader/ACL.
- Новые recording_polls и recording_poll_push: полнота/unique/origin,
  publisher election/guard, адресов/credentials камеры нет, реальный роль-
  сокет, запрет отправки видео при want, late role response и отказ ingest.

Отложенное: storage baseline из мутационной пробы (свой inbox/окно), C5,
C6/C6b/C7, перенос продукта. Приёмку стенда продукта не заявляем.

## Финальная проверка и границы вывода

Все160 Python test_*.py выполнены ровно один раз в финальном разбиении,
console ровно один раз; суммарно1935/0/0. Первый обычный полный unit дал
тот же результат, но начат до последних правок: он не подменяет финальный.
unit-runtime-inputs.json совпадает до/после финальных процессов;
input-digests.json проверен после всех прогонов. Source после фиксации
6d9a8a17 не менялся. Временная ссылка jsdom удалена.
Паритет, строгая загрузка, права, секреты и boundary входят в полный unit.
Продуктовая ведомость ещё ждёт синка своей команды; её не правили.
Git diff --check для Source и разрешённых числовых цитат — exit0.
Логи оставлены исходными; SHA256 всех артефактов в evidence.json.

Unrecorded/scenario/relay/holdermove проверены настоящими ordinary
publishers, целостными подписанными отчётами, generic collect, carry и
локальными role requests. Готовые собранные книги/токены не подставлены,
назначений для unrecorded нет. Прежние проверки возможностей не сняты.
Внутреннее чтение helper проверило эти четыре перенесённых файла отдельно;
оно не заменяет вердикт Архитектора по платформе.

При holder-move безопасный отказ длится до45с freshness старого poll
вклада. Тест оставляет старый roster/вклад, подтверждает ERROR и ноль dial,
ждёт строго >received_at+45, затем проверяет новый SN3 и ровно2 действия.
Это видимая задержка доступности, вынесенная Архитектору с рекомендацией
сохранить generic unique/grace. Мгновенный перенос здесь не заявлен.

## Проверка при слиянии

Прочитанный81324161 слит поверх нового main d4a95bf9. В новом main
только тексты/решения и shared acceptance «Спецификации»; runtime, unit
модули и прежние сценарии C4 не изменялись. Сравнение всего Source кроме
acceptance с прочитанным итогом — exit0; все runtime SHA256 совпали с
unit-runtime-inputs.json. Новая acceptance сохранена с main без своих
правок и не объявлена пройденной этим окном. Вердикт/merge — READING.md.
