# Ревью урока P/08 «Процесс domain» по ADR-0129 (Kimi, CT 103)

**Назначение**: decisions/inbox/2026-11-07-ревью-P08-ADR0129-задание.md (прочитано из публикации разбора 7f6b5ea2a8cbf85cebe8e7f5f3138cefba92f8ea, в источник не переносилось), ADR-0129 до доп. (18).
**База (единственная)**: af80f21911980483fea5f911c46dbf95d166a6c8. Ветка: `kimi103/review-p08-adr0129-af80` (от af80). Дата: 2026-11-07.
**Независимость**: находки/черновики/вердикты с review103 не обменивались; её отчёт не читался.
**Счёт**: источник **Б0 / С1 / М2**; судьи **Б0 / С0 / М0**.

## 1. Покрытие чтения

Прочитано целиком (English-источник, вне `ru/`):

- `Platform/08-domain/README.md`, `spec/08-domain.README.md` (инструкции, 89 норм, 20 пунктов «Implementation decides»), `lifecycle.md`;
- все 11 глав норм: 08.0 (282 стр.), 08.1 (813), 08.2 (622), 08.3 (907), 08.4 (1016), 08.5 (640), 08.6 (566), 08.7 (233), 08.8 (922), 08.9 (352), 08.10 (289);
- формы целиком: `forms/README.md`, `daemon-flags.tsv` (20 вводов + first-admin), `runtime-constants.tsv` (51 строка), `refusals.tsv` (184 строки), `versioned-doors.tsv` (24 строки), `stages.tsv` (13 этапов);
- векторы: README трёх пакетов (`view`, `assemble`, `issue`) + сверка состава `cases.tsv` (51/23/40 строк, имена уникальны) и хешей манифестов;
- приёмка: README всех 10 каталогов (0–10) + все `scenarios.tsv` целиком (109 сценариев / 1367 шагов: 39+218+498+72+261+55+122+46+56) + все `seams.tsv` (0/2: 8+3; 1:3; 2:3; 3:4; 4:11; 5:2; 6:3; 7:3; 8:4; 9:3; 10:5) + описи `acceptance/3/inputs/`;
- данные: каталог `data/` — 178 файлов = 59 семейств × (schema+layers+outcomes) + `refusal-words.tsv` (166 слов); состав семейств сверен с `Platform/common/data/catalog.tsv` (owner P/08.* — 59 ключей, 59 схем, пропусков нет); образцы схем/таблиц прочитаны (idem, keys, view, members, pending и др. — структура стандартная);
- OpenAPI: структурно все 47 путей / 63 операции + сверки (ниже) + точечное чтение блоков (`/domain/members*`, `/domain/folders*`, `/domain/memberof*`, `/api/book*`);
- зависимости common, прочитанные в объёме употребления: `keys.md`, `domain-token.md`, `domain-envelopes.md`, `accept.md`, `may.md`, `record.md`, `ask-sig.md`, `forwarding.md` (таблица «Domain doors» целиком), `role-certificate.md` (включая классы signed/role), `local-token-door.md`, `sealing.md`, `observation.md` (LOST_AFTER, member_state), `turn.md`, `alarm-history.md`, `labels.md`, `person-name.md`, `password-hash.md`, `domain-founding.md`, `domain-backup-key.md`, `instance.md`, `agent-signature.md`, `gate-and-pass.md` (The gate, Subsystem of the check, Break-glass entry, Attempt limit, Rights by the body), `object-client.md`, `event-journal.md` (начало), `peer.md`, `env-file.md` (включая CLUSTERS), `secret-files.md`.

**Непрочитанное / границы чтения** (явно): ru/-дерево (для людей, ADR-0121/0124) — не читалось; `decisions/journal/platform/08-domain/` — листалось для Т2 (состав и объём), записи не перечитывались по одной; P/09/P/10 и поздние слои P/02/P/03/P/06 читались в объёме перекрёстных ссылок (связи с P/01–P/07/P/09/P/10 проверены по тексту ссылок, не повторным чтением чужих глав); OpenAPI не читался построчно (3802 строки) — сверки структурные + точечные блоки; лекционный текст `ru/08-domain.md` не использовался как доказательство (зеркало не подменяет канон). Побайтное совпадение ранее прочитанных зависимостей с af80 не доказывалось — выводы опираются только на чтение с этого среза; наследование прежних вердиктов не применялось.

## 2. Проверки и доказательства

1. **check_spec P/08 (штатный судья)** — команда:
   `/opt/check-env/lesson-spec/bin/python skills/lesson-spec/scripts/check_spec.py Platform/08-domain/ru/08-domain.md`
   Результат: **PASS with 13 exceptions, structural checks only** (исключения — штатные grammar exceptions формата сценариев приёмки 5–10, по одному на каталог). Счётчики судьи: families_with_section=59/59, family_schemas=59, norm_ids=89, req_anchors=931, scenarios=109, steps=1367, versioned_doors=24, runtime_constants=111, refusal_rows=756, checklist_inventories=1, scenesets сходятся с моим подсчётом.
2. **Сверка versioned-doors ↔ OpenAPI**: все 24 пары method/path есть в OpenAPI; строгая проверка обратного заявления forms/README («Every OpenAPI operation declaring ETag or If-Match has a row») — 18 операций с заголовком ETag или параметром If-Match, все покрыты таблицей; ложное срабатывание GET `/domain/memberof/…` снято чтением блока (ETag там только в тексте «no … ETag»).
3. **Двери таблицы 8.0 N2** — все перечисленные двери процесса присутствуют в OpenAPI (несовпадения имён placeholder `{member}`/`{name}`, `{batch}`/`{name}` — косметика, не находка; литеральная `*` в пути books — осознанная).
4. **Константы**: все числовые константы норм имеют единый источник — форма P/08 либо чужой источник (LOST_AFTER/MARK_REFRESH — observation; TURN_TERM/RENEW — turn.md; TOKEN_SKEW — domain-token.md; TOKEN_BODY/TOKEN_HOLDER_BODY/TOKEN_WAIT — local-token-door.md; FRESH_EVERY/SAY_EVERY — форма P/09; FOLDER_* — форма P/06; OUTCOME_HOLD — форма P/09; BATCH_WRITES/BATCH_GUARDS — P/01.1; VERIFY_* — gate-and-pass.md). Арифметика дериваций сходится: BATCH_LIMIT=4×BODY_LIMIT=67108864; TOKEN_HOLDER_BODY=4096+512=4608; HANDOVER_WAIT=6×5=30; MARK_REFRESH=45/2=22.5; ROAD_QUIET=3×5=15; NEAR_CEILING=80 %×524288=419430; ENTRY_MAX «≈420 Entry»=524288/1240; MEMBERS_MAX «≈1.4 млн»=4096×350; «19.5 пар/с»=18700/960, «16 мин»=960 с — все согласованы.
5. **req-ссылки форм**: все `P/08.x-Ryyy` в refusals.tsv и versioned-doors.tsv существуют в нормах (comm пуст); ссылки stages.tsv — формат «P/08.x N…».
6. **Состав файлов**: 242 активных файла вне ru (13 spec + 6 forms + 6 vectors + 37 acceptance + 178 data + 2 корня) — сходится с ориентиром задания; 178 data = 59×3+1 (refusal-words).
7. **Хеши манифестов** (заявлены в README векторов): testsub `fc3bf705…7355b`, testsub2 `e4bfd9e0…15dbb` — совпали с `sha256sum`.
8. **Входные фикстуры** (sha256): `other-root.json` bd3cf48f…, `view-member-list-ghost.json` 993769eb…, `member-reported-rev-2pow53.json` a14c75f7…, `kit-m1-one/ca.pem` = `kit-m1-two/ca.pem` 71d0e4df… (центр A), `kit-m1-two/ca.next.pem` 0bb54801… — сохранены для следа.
9. **TSV-структура**: все scenarios.tsv — ровно 4 колонки; seams.tsv — 4 колонки; имена кейсов векторов без повторов.
10. **З-10-скан**: в активном каноне P/08 нет указателей former ids, миграций, чтения старых форматов под видом нынешних. Встречающиеся «former/legacy» — (а) осознанные правила чтения повреждённой/прежней строки (8.0 N1.9 «revision 0 → следующая запись пишет 1»; 8.8 N1.5 in_report «Builds before this norm … a handover to such a keeper — called off» — явный отказ, не молчаливое принятие); (б) имена швов (`legacy revision`, `forbidden legacy role`) — тестирование нынешнего читателя на испорченной строке; (в) «not a domain route» для `.`/`..` — закрытие обхода, не совместимость. Нарушений З-10 не найдено.

## 3. Находки источника

### С1. Значения констант формы продублированы в нормативных текстах (имя можно, значение нельзя — форма↔проза)

Форма `forms/runtime-constants.tsv` — единственный источник чисел, но то же число стоит в четырёх нормативных местах; при смене значения формы чеклист/норма начнут врать:

- `spec/08.1-domain.norms.md:808` (P/08.1-06): «SHADOW_STALL 60» — форма строка 6, значение 60;
- `spec/08.1-domain.norms.md:809` (P/08.1-07): «SHADOW_CLEAN 3 in a row» — форма строка 7, значение 3;
- `spec/08.3-domain.norms.md:229` (N1.3a ROAD_QUIET): «three passes of the agent (REPORT_EVERY 5)» — форма строка 10, значение 5;
- `spec/08.8-domain.norms.md:880` (N5): «(BACKUP_HOLDERS 2 of two members)» — форма строка 27, значение 2.

Причина: раздел (в) ADR-0129; риск рассинхрона при правке формы. Контрпример уже показан соседом: `spec/08.10-domain.norms.md:47` несёт исторический след «(was 820, a new calculation below)», а `forms/runtime-constants.tsv:29` повторяет его же — урок, что числа в прозе устаревают. Предложение: заменить значения на имена («SHADOW_STALL (the form)», «SHADOW_CLEAN in a row», «three passes of the agent (REPORT_EVERY of the form)», «BACKUP_HOLDERS of two members») — правка фразой, без смены ожиданий; по доп. (14) п. 8 числа указываются формой, а не копией.

### М1. Устаревшие описательные счётчики в README приёмок (8 мест, одна причина)

Разделы «Kit seams»/«vectors … (N rows)» README приёмок не пересчитаны после добавления швов и строк векторов; читатель опись врёт:

- `acceptance/0/README.md:6` — «[3 CALL seams](seams.tsv)», файл несёт **8** швов (s01–s08, добавленные s04–s08 швы C3/replay названы в чеклистах 8.0-03/8.0-04, но README не обновлён);
- `acceptance/3/README.md` («Kit seams», конец файла) — «3 CALL seams», фактически **4** (s01–s04, s04 — cleanup seam, названный в 8.3-03);
- `acceptance/4/README.md:142` — «[4 CALL seams]», фактически **11** (s01–s11: s03–s09 supervision/spread, s10–s11 login C5-seams из чеклиста 8.4-02);
- `acceptance/8/README.md` («Kit seams», конец) — «3 CALL seams», фактически **4** (s04 — two-target-attempt, названный в 8.8-06);
- `acceptance/1/README.md:13` — «vectors view (28 rows …)», фактически **51** строка (28 бывших + 23 добавленных; README пакета подтверждает 51);
- `acceptance/5/README.md:13` — «vector assemble (17 rows …)», фактически **23** (README пакета подтверждает 23);
- `acceptance/7/README.md:13-14` — «vector issue (38 rows: 30 …, 8 …)», фактически **40** (добавлены `keep-too-long`, `keep-ok` — README пакекта подтверждает 40);
- `acceptance/4/README.md:12` — «vectors may (106 rows …)», фактически **126** (may.md:203 и `cases.tsv` подтверждают 126: добавлены may-role-*/may-107…115).

Причина: описательные счётчики без генерации; следствие — читатель/генератор опись получает ложную полноту. Минимальный контрпример: fresh-прогон `grep -vc '^#'` на файлах даёт 8/4/11/4 и 51/23/40/126. Предложение: пересчитать формулировки (число без копии значений нормы не несёт, но счёт строк — доказательство полноты, его надо верным) либо убрать числа и ссылаться на файл; не затрагивает ожидания и идентификаторы.

### М2. `held` для поля `anywhere` не описан в норме 8.4, общий контракт его допускает

`common/contracts/domain-envelopes.md` «Content of sealed» строка 116: `held?: [<field name>…] of "grants", "roles", "anywhere", "break_glass"`; `accept.md` «The answer carry» (строка 185) тоже перечисляет `folders?` и `gone_seen?`, а held — по контракту. Норма `spec/08.4-domain.norms.md` N1.3 carry (строка 217) называет held только `["grants", "roles"]`, N1.6 carry (строка 421) — `break_glass`; случай нечитаемой/не сошедшейся сводки `domain/anywhere` (ANYWHERE_MAX, «an unreadable row … or a role only narrows the summary» — строки 224–226) в held не вписывается. Двусмысленность: непрочитанная anywhere → held с именем `anywhere` (по контракту) или поле просто отсутствует как «not sent» без held (по 8.4)? Для break_glass норма прямо описала held (8.4 N1.6, C08-GLASS-HELD-01), для anywhere — нет, хотя сводка так же критична как вход (D-8). Предложение: одной фразой в 8.4 N1.3 закрепить «сводка не прочитана/перевесила потолок → held: [..., "anywhere"]», либо явно исключить anywhere из held в контракте — решение за «Спецификацией»; контрпример чтения: сводка > ANYWHERE_MAX при живых grants (строка 226 «larger — the row stays the former one») — строка остаётся, а новая не несётся; агент обязан не трогать копию — по контракту это held, по 8.4 — молчание.

## 4. Судьи и генераторы (Т1–Т5, разделы (а)–(г))

- **Судьи P/08**: check_spec — PASS (п. 2); машинные тесты normgen для P/08 (test_gen_door_lesson.py, test_gen_versioned_doors.py, family_judge и др.) не запускались — требуют пакет линии, новых установок не было; это граница, не успех. Счёт судей Б0/С0/М0.
- **(а) Догадки/двусмысленность**: кроме М2, мест не найдено; характерные узлы (base_rev vs If-Match, membership index-only, executors `{cluster} ∪ copies`, camera `silent_after`, until-округление, kept_at nextafter) имеют по одной формулировке и согласованы с OpenAPI и векторами.
- **(б) Т2**: место со всеми зависимостями не сводится к строкам (нормы отсылают к контрактам/формам/семьям); осмысловых эпизодов ≥3 (сборка урока из M11/1–12, reconciliation M11 S1…X14, аудиты покрытия 1e9929d51 и второй прогон Gemini e32df6f8b, G08-BATCH-REFUSED-OVERFLOW, G10-read-forms) — но новый генератор по Т1–Т5 не выводится (нормативный охват криптопроцедур и процедур дверей не сводится к форме; «кандидаты без векторов» отмечены самими README пакетов как осознанные доли). Недельная мера 2026-11-13 14:00 UTC ещё не наступила — фиктивной доли нет, снятие/ввод генератора не предлагаю.
- **(в) Формы↔проза**: С1 (четыре места); других дублей значений не найдено (п. 4 п.2 сверки).
- **(г) Существующие генераторы P/08**: gen_families (общий по каталогу) и gen_versioned_doors — правятся вместе с нормами, действующей недельной меры нет, порог снятия (>1/2) не измерим — не снимаю.

## 5. Входящие (не пересчитаны как новые)

J-P05-02, J-P06, J-P07; прежние ремонты P/03–P/07; «дескрипция исключения acceptance-entry inputs не называет sc. 22» (записана в `acceptance/3/README.md` как известная правка «Архитектора»); лимиты TLS-стенда, «no dry run» сценарии 8.4 sc. 24–37/8.5 sc. 14/8.8 sc. 18/8.3 sc. 28–29 — названные владельцами долги, не находки P/08.

## 6. Вне счёта (наблюдение для spec103)

`Platform/common/contracts/turn.md:101` — опечатка «the33 previous cases» (пробел потерян). Не влияет на смысл; общий контракт.

## 7. Пределы и границы доказательства

Реализация не исполнялась (нет назначенной линии); «Schema/declared expect/static PASS не означает execution» — check_spec структурный, семантика по чтению. Прогоны семейного/дверного судей normgen не выполнялись (граница окружения). OpenAPI сверен структурно и точечно, не построчно. Связи с P/01–P/07/P/09/P/10 проверены по перекрёстным ссылкам и чтению общих контрактов, не повторным чтением чужих глав. Реальные состояния гонок/TLS между кластерами — по норме «by reading» (штатная граница урока).

СТОП: сдача P/08 | ЖДУ: разбора «Архитектором» обоих отчётов P/08 и назначения P/09
