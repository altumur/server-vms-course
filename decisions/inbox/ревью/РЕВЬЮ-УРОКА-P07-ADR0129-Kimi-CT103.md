# Ревью урока P/07 «Модуль консоли» по ADR-0129 (Kimi103, независимое)

- Дата: 2026-11-07 (UTC).
- Ревьювер: review103-kimi (Kimi103; находками/черновиками/вердиктами с review103 не обменивался).
- База (замороженный источник и единственная база отчёта): `10f2bd2ea4145751b3d8ce2f3d56bf6d7183f0a1`.
- Ветка отчёта: `kimi103/review-p07-adr0129-10f2`; в ветке — только этот файл.
- Задание прочитано из `1915e2eeb5255989213a980e4e3bd8ca65d7aeb8` (`decisions/inbox/2026-11-07-ревью-P07-ADR0129-задание.md`); ADR-0129 с доп. (17) — из той же публикации; в источник не переносились.
- Критерии: ADR-0129 до (17), Т1–Т5, З-10.

## 0. Входящие долги (не считаю заново)

- C6 (скрытые поля, `v1showsHidden`), критерии ADR-0127 C1–C7 и M2, критерий «один источник подписей» и «локаль дат UI» — таблица «Accepted ADR-0127 review criteria and debt of the published module bytes» норм (владелец — владелец опубликованных байтов; свидетель в этой поставке не менялся).
- A1/N5 — долги владельца опубликованных байтов; P/07-07 и P/07-08 (`module-unplaceable-all`, `module-subsystems-none`, `module-writes-via`) — открытые пункты готовности владельца.
- Дерево папок из N1.5 `tree` (вызов `/folders`): в N5 прямо записано «jsdom test `module-folders` (not written yet: the module does not do this, a debt of the product)», CONSOLE-MODULE.md §7 — «The module does not do this yet»; P/07-06 — «when the module has it». Документированный долг владельца, не новая находка.
- Принятые замечания P/06 (в т.ч. мои F1–F6 по доп. (17) пп. 6–8), известные P/02–P/05, З-10 P/06.8, очереди J-P04/J-P05/J-P06 — не пересчитываются.
- Отозванные запросы (локализация consolem, V/11) не возобновлялись.

## 1. Охват чтения и пределы

Прочитано полностью на базе 10f2 (все строки):

- `Platform/07-console-module/spec/07-console-module.norms.md` (354), `spec/07-console-module.README.md` (70), `CONSOLE-MODULE.md` (296), `README.md` (16), `data/localization.tsv` (519 строк).
- `module/console.html` (17), `module/console.css` (467), `module/console.js` (3239) — все три файла байт в байт.
- `Source/tests/console/` — изучение по N5: `run.sh`, `package.json`, `boot.js` целиком; все 45 `*.test.js` — заголовки, фикстуры и списки проверок каждого теста (по `out.*`-утверждениям); текстово детально — `module-calls`, `module-retry`, `module-words`, `module-may`, `module-page-calls`, `shell-short`.
- Предметные зависимости точечно: P/06 (нормы/OpenAPI — прежним глубоким чтением на d285; согласовано по местам ссылок N1.4/N1.5), P/08.4 N1.2/N1.2a (login, LOGIN_BODY), P/08.8 N1.3 (term/backup pair, largest (term, rev)), P/08.9 N1.2 (shared doc), P/10 N1.7/N2 и P/10-04 (holder page, `GET /manifest → {"name": "", "rows": null}`), forwarding contract «Domain doors» — по местам, где N1.6 их цитирует.
- Журнал урока: отдельного `decisions/journal/platform/07-console-module/` нет (переименований/истории правок урока в индексе журнала нет; история — в тексте норм и id-map истории).

Исполненные проверки (READONLY; команды и полные выводы — `/tmp/p07-evidence/`):

1. Хеши канона: `sha256sum` — `module/console.js` = `05d167f53a4d91214f30188d5331f0f4afbd99bfa7e4ac349b98f423f1bec89e`, `console.css` = `44d4045693f60fcf719e7c216352e9e4b7873b69c372ae35e37d010050bb4de6`, `console.html` = `c3e33f59424b516e1778dc514712050692a1a9a07327267f6e37f6af4334fb76`, `localization.tsv` = `a5b3c4b9c1af6cfe40a72c80b58d2348a9e9517d7c36c0b6ad8a91bc807850e9` (`module-sha.txt`). Заявленный в шапке console.js (:19) хеш TSV — совпал (выполненная сверка).
2. `check_spec.py Platform/07-console-module/ru/07-console-module.md` → **exit 0, PASS** с 5 исключениями; `lessons=1`, `norm_ids=8` (P/07-01…08) (`check_spec-p07.txt`).
3. Сверка WORDS↔localization: на собственной инструментированной копии js (экспорт WORDS) node-скрипт — **519/519 строк TSV присутствуют и совпадают в обоих языках; лишних ключей нет**; `n.*` и `kinds.*` биндинги по правилу норм (:167) (`words-node.js`, `words-check.txt`, `console-words-export.js` — всё вне дерева).
4. Скан словаря запрещённых слов §2 CONSOLE-MODULE.md по console.js: все 17 вхождений `live` — допустимые токены (`resource === "live"`, `state === "live"`, «live workers», локальная переменная); `live_url/LIVE_*/livecontroller//live/` отсутствуют; остальные словарные слова — 0 вхождений.
5. Штатный jsdom-набор `Source/tests/console` — два изолированных прогона в собственных копиях (источник не тронут): (а) штатная конфигурация — модуль из свидетеля `Source/w2cplatform/console.js` (sha `9e0356451fcc3c143aacdc643da3881d57936dc91b3315eb6125c35f5a404c71`, 261 122 байт); (б) перенацеленная копия — нынешние байты `Platform/07-console-module/module/console.js` (sha `05d167f5…`, 312 543 байта). Окружение: node v22.23.2, jsdom из `/home/pilot/coord103/p07-module-node-env/node_modules` (симлинк в моих копиях). Результаты идентичны: **44 ok, 1 FAILED** — `shell-short` (backendLink, otherVersionSaid), причина — устаревший тест против нынешней короткой оболочки VMS: `VMS/01-cam/cam.shell.html` несёт `<a href="/backend/">VMS console</a>`, тест ждёт «Консоль VMS»; оба прогона падают одинаково, различий свидетель/нынешние байты по итогам нет; набор — 45 тестовых файлов: 39 `module-*` + `platform-page` = **40 прошли** (все 17 поимённо названных в N5 существующих тестов и остальные модульные), плюс `holder-page` и 3 shell-теста; все они ok на нынешних байтах. Отсутствующие проверки — `module-folders` (в N5: not written yet) и названные P/07-07/08 `module-unplaceable-all`/`module-subsystems-none`/`module-writes-via` — **не исполнялись и не закрыты** прогоном. Выводы: `jsdom-witness-bytes.txt`, `jsdom-current-bytes.txt`.

Пределы (явные): зеркала `Platform/07-console-module/ru/**` — не канон (по ADR-0121/0124; семантика зеркал не сверялась, состав — через check_spec, PASS); человеческая лекция `ru/07-console-module.md` не читалась и канон не подменяла; установок зависимостей не делал (jsdom — готовое окружение coord103, только симлинки в моих копиях); прогон тестов не исполняет реализацию стендом P/06 — это jsdom-проверки опубликованной библиотеки.

## 2. Находки источника

### М1 — висячая ссылка `id-map.tsv` в шапке норм

- reqID: не привязан (шапка урока); прецедент — ADR-0129 доп. (16) п. 4 (снятие той же ссылки в P/05) и доп. (17) п. 8 (уборка указателей former ids из активного входа).
- Место: `Platform/07-console-module/spec/07-console-module.norms.md:19` — «the map to former ids is `id-map.tsv` (historical record)».
- Причина: файла `id-map.tsv` нет в `Platform/07-console-module/**` (`find` — пусто); карта M10/M11→Platform лежит в `decisions/history/platform/id-map.tsv` (check_spec читает её оттуда: `id_map_ids=8`) и нормой не названа. Т3: ссылка из текста не разрешима читателем.
- Минимальный контрпример: читатель норм ищет `id-map.tsv` рядом с уроком и не находит; инструмент путь знает, человек — нет.
- Предложение: указать путь `decisions/history/platform/id-map.tsv` либо убрать фразу — по образцу доп. (16) п. 4 / доп. (17) п. 8. Отмечу: это то же место, что моя F2 P/06, но в P/07 — собственная локация; решение по P/06 эту строку не закрывает.

### М2 — `worker:<sub>/<w>`: все воркеры `/servers` именуются подсистемой корня

- reqID: P/07 (нормы N1.5 `objects`; чек-лист P/07-02).
- Места: нормы `07-console-module.norms.md:84` (`worker:<sub>/<w>` — воркер подсистемы) и `module/console.js:1360` — `const workerRef = w => "worker:" + st.root + "/" + w;` (комментарий в коде: «the root subsystem's (CONSOLE_ROOT)»).
- Причина: `/servers` (P/06.5 N2) агрегирует воркеров всех подсистем каталога (в приёмке P/06.5 sc. 12/19 у сервера есть и `w-1` корня, и `t-1` смонтированной `testsub2`); модуль присваивает каждому ref с именем корня. Для воркера смонтированной подсистемы подсистемная часть ref ложна; двух воркеров с одним слотным именем у разных подсистем различить нельзя. Чтение: норма задаёт `<sub>` подсистемы воркера; байты осознанно (по своему комментарию) выбирают корень, т.к. по строке воркера `/servers` подсистему не узнать.
- Минимальный контрпример: каталог root=`testsub`, смонтирована `testsub2`, слот `t-1` на `srv-a` (стенд acceptance/5 P/06.5): модуль строит ref `worker:testsub/t-1` вместо `worker:testsub2/t-1`; `on("select")` отдаёт странице ref с неверной подсистемой.
- Предложение: либо зафиксировать в N1.5, что в ref воркеров `/servers` подсистема — CONSOLE_ROOT (нынешнее поведение байтов, тогда норма и байты сойдутся), либо получать подсистему из данных пульса и строить ref по ней. Вопрос на решение «Архитектора»/владельца байтов.

### Позитив и согласования (зафиксировано без находок)

- N1.4 закрытый список против байтов: все чтения/записи модуля в пределах `reads`/`writes`; `never` (`/{sub}/requests`, `/api/backup`, `/resources`, таблицы вне `servers.show`, двери держателей) не вызываются; порядок `order` в `load()` (:3122–3159) совпадает; feed: номер до строк (:3225–3226), `wait=15` (FEED_WAIT), 404 отключает ленту, ≤1 запрос/с, опрос `poll_s` (умолчание 5 с), `/events?unit=` выбранной каждые 5 с (:3230).
- N1.5: версия 1 и ровно шесть features (:3238); `ready` (401 ждёт логина, сбой `/manifest` ждёт опроса — :1412, :3081–3087); `api`: ключ на действие, повторы только POST строк юнитов с Retry-After/2-3-5 с и сдачей после третьего (:1148–1191), 412 → `retry:false` (:1174), PUT/DELETE/таблицы — «сначала прочитать» (:1179–1182), ifMatch только на читающих дверях с отказом до запроса (:1197–1225); `may` по рангам/областям, open/glass/closed/unknown (:1307–1315); `where` → `door || null` (:1347–1351); `return` — точное `/<sub>/` каталога, иначе `/`, повторный параметр → `/` (:3090–3096); события `session`/`card.closed`/`refresh` (:1129–1135, :3102–3104, :3159); разметка карточки и `<h2>`→`.card` (:1886–1944).
- Локализация: выбор языка строго `opts.lang === "ru"` (:1110), браузерный язык не используется (у свидетеля — fallback на `navigator.language`, строка 368 свидетеля: это подтверждённое различие свидетеля и нынешних байт); даты — явные `ru-RU`/`en-US` (:1111, :3034).
- N1.6: режим держателя (`sections:[domain]`) не грузит юниты/`/servers`/`/unplaceable`, живёт без них (:3177–3185); сравнение копий `(term, rev)` по старшинству term→rev (:2706–2710); форма по схеме shared-документа (:2766–2802); логин `login_url` → токен → `/session` (:3067–3079).
- Публикация и упаковка: README/нормы единообразны — линия пакует байты, второй реализации нет; sc. 01 acceptance 6.5 — место проверки публикации (вне этого урока).

## 3. З-10

- Скан по канону P/07 (`backward|compatib|legacy|устарев|совместимост`): старой совместимости нет; CONSOLE-MODULE.md :63 — «old versions are not served: backward compatibility… is not kept» — нынешний формат. Единственное наследие — свидетель `Source/w2cplatform/console.js` (старое поведение: fallback на язык браузера и пр.); он вне канона урока, его результаты не наследуются (см. §4).

## 4. Судьи и доказательства (отдельный счёт)

- Существующие судьи: `check_spec` — PASS (exit 0) на уроке; штатный jsdom-набор `Source/tests/console` — существующая проверка библиотеки владельца спецификации.
- **Граница доказательства (главное)**: штатный набор по умолчанию грузит замороженного свидетеля `Source/w2cplatform/console.js` (sha `9e035645…`), а не нынешние опубликованные байты `Platform/07-console-module/module/console.js` (sha `05d167f5…`); байты различаются (261 122 ≠ 312 543 байт; у свидетеля — старое поведение языка, нет хеша TSV). Поэтому его «зелень» сама по себе нынешний модуль не доказывает. Перенацеленный прогон (собственная копия, команды/пути/хеши сохранены) показал: на нынешних байтах все модульные/платформенные тесты набора, включая весь список N5 (`module-calls`, `module-changes`, `module-retry`, `module-may`, `module-contract`, `platform-page`, `module-session`, `module-words`, `module-page-calls`, `module-return`, `module-form-if-match`, `module-refusal-field`, `module-shared-schema`, `module-refresh-event`, `module-tree-nodes`, `module-page-adds`, `module-card-markup`), — ok.
- `shell-short.test.js` (не входит в список N5 P/07; проверяет короткую оболочку VMS со stub-модулем) — FAILED дважды (в обеих конфигурациях): тест ждёт «Консоль VMS», нынешняя `VMS/01-cam/cam.shell.html` несёт «VMS console»; рассинхрон тест/свидетель оболочки VMS, к P/07 модулю отношения не имеет. Зафиксировано как факт о состоянии судьи, не находка P/07.
- Чтение, схема и jsdom-проба — разные виды доказательства; чужие старые успешные числа не наследовались (перепрогон своей копией).

## 5. Итог

- Источник P/07 (10f2): **Б0 / С0 / М2** — М1 (висячая `id-map.tsv`, norms:19), М2 (атрибуция воркеров корню, console.js:1360 против N1.5 `objects`).
- Судьи: **Б0 / С0 / М0** — check_spec PASS; jsdom-набор исполнен на нынешних байтах (44 ok + устаревший shell-short вне N5); граница «свидетель по умолчанию» записана и преодолена перенацеленным прогоном.
- Замороженный источник, судьи, генераторы — без правок; новых моделей/Go/реализации/HTTP-стенда/SDK/SUT/линии нет; отчёт — единственный файл ветки; доказательства вне дерева: локально `/tmp/p07-evidence/` — 8 обычных файлов на верхнем уровне (`module-sha.txt`, `check_spec-p07.txt`, `words-check.txt`, `words-check.py`, `words-node.js`, `console-words-export.js`, `jsdom-current-bytes.txt`, `jsdom-witness-bytes.txt`), два каталога с полными копиями набора (`src/`, `witness-run/`) и две внешние связи (`VMS`, `Platform`); суммарно по дереву 108 обычных файлов и 10 внешних связей (эту точную копию сохранил у себя coord103).

СТОП: сдача P/07 | ЖДУ: разбора «Архитектором» (второй отчёт review103) и дальнейших назначений (P/08 — по слову «Архитектора» после обоих и разбора)

---

# Дополнение 1 (2026-11-07, по уточнению «Архитектора»): дочитанные тесты N5 и воспроизводимость

## Д1. Чтение тестов N5 с логикой (закрыто)

Прочитаны целиком, с телом, фикстурами и условиями, все существующие тесты, на которые ссылается N5 (17 поимённо названных + служебный `boot.js` ранее): `module-calls` (закрытый список `allowed()` в тесте против `reads`/`writes`, `never` по токенам путей, порядок `ORDER` при монтировании и на опросе, `/events?unit=` каждые 5 с, режим держателя), `module-changes` (номер до строк, `after&wait=15`, ≤1/с, своё/чужое/сброс/пусто, 404, держатель без ленты), `module-session` (создание, logout, break-glass, «Retry» с тем же ключом), `module-retry` (ключ на действие, 5xx/сеть/таймаут/`in flight` у POST строк, Retry-After против 2-3-5 с, сдача после третьего с `status/body/retry`, 11 дверей без автоповтора с чтением первым, 401), `module-may` (ранги/области, about-unit, labels about-vs-own, open/closed/unknown/glass), `module-contract` (включая проверку словаря §2 с `platform-words.debt`, `where`, `manifest`, декор, XSS-строка текстом), `platform-page` (только модуль+mount, версия до использования, слова подсистем отсутствуют), `module-refresh-event`, `module-tree-nodes` (пять видов узлов, все поля, after/replaces), `module-page-adds` (addIcons/addNote/fullScreen/isFav/toggleFav, addSection/addTab×4/busy/addBlock×2/addAction/dialog/confirm), `module-words` (равенство ключей en/ru, использованные слова, kinds, исходы команды, kindWord/display/eventNote), `module-card-markup`, `module-page-calls` (features/ready/select/card.closed/ifMatch-отказы до запроса/412), `module-return` (14 случаев `return`), `module-form-if-match`, `module-refusal-field` (включая `~1`), `module-shared-schema`.

Точно непрочитанные (вне N5; читались заголовок/фикстуры/список `out` только): `module-access`, `module-children`, `module-command-words`, `module-debug`, `module-drain`, `module-form`, `module-form-json`, `module-groups`, `module-journal-late`, `module-keys`, `module-labels-unread`, `module-local-groups`, `module-nested`, `module-poll`, `module-servers`, `module-shared-groups`, `module-show`, `module-steady-tabs`, `module-tree`, `module-unplaced`, `module-view`, `module-worker-table`, `shell-page`, `shell-volumes`, `shell-xss-sweep`; `module-domain` и `holder-page` — общая ссылка N1.6/N5 «jsdom test of the mode domain / holder page» (тела не читал, из списка `out` — покрытие режима `domain`/страницы держателя). `shell-short` прочитан целиком (субъект — оболочка VMS со stub-модулем). Входящие отсутствующие проверки: `module-folders`, `module-unplaceable-all`, `module-subsystems-none`, `module-writes-via` — файлов нет, прогоном не исполнялись и не закрыты.

## Д2. Воспроизводимость прогонов (точные команды)

Каталог доказательств: верхний уровень — 8 обычных файлов, каталоги `src/` и `witness-run/` (полные копии набора), связи `VMS` и `Platform`; суммарно 108 обычных файлов и 10 внешних связей (копию сохранил coord103). Новых прогонов для этого дополнения не делал (счётчики — из сохранённых выводов).

Прогон на нынешних байтах (выполнен 2026-11-07, cwd — моя копия):

```
cd /home/pilot/review103-kimi || exit 1
mkdir -p /tmp/p07-evidence/src/tests
cp -r Source/tests/console /tmp/p07-evidence/src/tests/console
R=/home/pilot/review103-kimi
ln -sfn $R/Source/vms /tmp/p07-evidence/src/vms
ln -sfn $R/Source/w2cplatform /tmp/p07-evidence/src/w2cplatform
ln -sfn $R/VMS /tmp/p07-evidence/VMS
ln -sfn $R/Platform /tmp/p07-evidence/Platform
cd /tmp/p07-evidence/src/tests/console
sed -i "s|path.join(__dirname,\"..\",\"..\",\"w2cplatform\",\"console.js\")|\"$R/Platform/07-console-module/module/console.js\"|g; s|path.join(__dirname,\"..\",\"..\",\"w2cplatform\",\"console.html\")|\"$R/Platform/07-console-module/module/console.html\"|g" *.test.js boot.js
ln -sfn /home/pilot/coord103/p07-module-node-env/node_modules node_modules
sh run.sh > /tmp/p07-evidence/jsdom-current-bytes.txt 2>&1
```

Условие переназначения: заменяются только два `path.join(__dirname,"..","..","w2cplatform",…)` (`console.js`, `console.html`) на абсолютные пути нынешних опубликованных байт; все прочие относительные пути (`vms/`, `w2cplatform/domain/page.html`, `VMS/01-cam/…`, `Platform/08-domain/…`, `platform-words.debt`) восстанавливаются симлинками/копией один в один; `node_modules` — симлинк на готовое окружение (установок не было).

Контрольный прогон штатной конфигурации (свидетель): то же без `sed`, каталоги `/tmp/p07-evidence/witness-run/{vms,w2cplatform,VMS,Platform}`, вывод — `jsdom-witness-bytes.txt`.

Предел: пофайловые результаты (`ok`/`FAILED`/стек) сохранены в выводах обоих прогонов; код возврата оболочки `run.sh` (=1 из-за shell-short) зафиксирован в журнале сессии, но не записан в файлы вывода — при воспроизведении получается из самого вывода (наличие строки `FAILED`); старые события задним числом не восстанавливал.

СТОП: сдача дополнения 1 к P/07 | ЖДУ: разбора «Архитектором» и назначения P/08
