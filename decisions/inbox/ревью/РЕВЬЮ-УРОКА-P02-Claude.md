урок: P/02 (ADR-0121 доп. (2) п. 3; ADR-0127 доп. (1) п. 5)

# Ревью урока P/02 в новой форме — английский источник, формы, нормы ADR-0115 (28)–(37) и автомат опроса (Claude) — черновик, **прервано**

**Прервано** 2026-11-05 словом владельца: ревью теперь только Codex. Черновик сдан как есть. Находки проверены по строкам курса, но перегонка модели не кончена (раздел «Модель»). Счёт черновика.

Поручение «Архитектора» 2026-11-05, main 3c98007fd.

Что читалось:
- **английский источник:** `spec/02.1`–`02.4`, `02-installer.README.md`, `lifecycle.md`;
- **формы:** `forms/daemon-flags.tsv`, `operator-commands.tsv`, `refusals.tsv`, `stages.tsv`, `rollout-poll.machine.yaml` с `rollout-poll.traces.tsv`, `forms/README.md`; швы `acceptance/1/seams.tsv`, `acceptance/4/seams.tsv`;
- README и таблицы приёмки 1–5, README векторов `canonical`, `exec`;
- для сверки: P/01.2 Н1.1, P/01.3 Н1.3 и `/v1/status`, P/02.5 Н3, `common/data/catalog.tsv`, ADR-0115 доп. (28)–(37), ADR-0120 доп. (5), (6);
- черновик `РЕВЬЮ-ADR-0115-28-37-нормы-Claude-черновик.md`: его находки переходят сюда по ADR-0121 доп. (2) п. 2.

Как читалось:
- Н1.9 `rollout`, автомат опроса и находки черновика читал сам.
- Четыре агента-читателя по моему заданию прочли:
  - 02.1–02.3;
  - 02.4 без `rollout`;
  - формы против прозы.

  Каждую их находку ниже я перечитал по строкам курса. Неподтверждённые отброшены: в каталоге есть код `exit 2` метки; живого U+2028 в 02.1:51 нет.
- Перегонка модели Quint на нынешней форме автомата — агент в `cammeta-quint`, раздел «Модель» ниже.

Кода и норм не правил.

**Счёт черновика: Б 1, С 14, М 9.**

## Что держится

- **Находки черновика 0115 (28)–(37) закрыты в английском P/02.4 и в автомате.**
  - **С1** (адрес против id): `poll` (02.4:491–492) — «a live answer is compared … by leader_id, the address leader is needed only for the target read». В автомате: `set_leader`, `answer` по `r.leader_id == leader_id`, чтение цели по `leader` или `members[leader_id]`.
  - **С2** (оба предела отрезанного): `bound` (02.4:507–509) и `env:` строка 73.
  - **М1** (чтение служит тем, чей ответ пришёл до его начала): правило ушло в автомат — `read_commit` берёт `need` в миг начала; `other_order` (02.4:504–506).
  - **М3** (состав своего члена отстаёт): `bound` (02.4:512–513), переходы `self_status-4`, `status-3`.
  - **М2** (`unproven`): дополнен списком v115p и ссылкой на v120. Буква «item 2 (b)» вместо «(c)» уже в ревью норм ADR-0121 (С2). После перегонки список стоит обновить ещё раз (раздел «Модель»).
- **Правки формы ADR-0120 доп. (5) п. 4 и доп. (6) — в автомате.**
  - действия — присваиваниями CEL;
  - `invariants:`, `env:` (порядок событий одного мига), `types:` ответа `/v1/status`, `timers:`;
  - `input.last` (Ф3);
  - сверка состава и по ответу лидера партии (Ф1, переходы `self_status-4`, `status-3`);
  - пустота лидера по `leader_id` (Ф5, `self_status-7`), при `-last` — `r.leader_id != input.self` (Ф6, `self_status-5`);
  - трассы `two-voters-refused` (Ф4), `leader-voters-changed`, `leader-voters-changed-held` (Ф1) и трассы смены состава и лидерства в поздней партии, голосующего без ответа к сроку (`voters-changed-later-batch`, `became-leader-later-batch`, `lost-leadership-later-batch`, `target-voter-silent`).
- **Автомат против прозы Н1.9 по переходам.**
  - Проход: `size(alive) >= size(voters) / 2 + 2` — это «≥ quorum + 1» при quorum = ⌊V/2⌋ + 1. При `-last` — живы все прочие.
  - Отказы лидерства — сразу, в каждой партии (`self_status-5`, `-6`).
  - Сверка состава идёт раньше лидерства.
  - Срок — после суда последней партии (порядок `env:`).
  - Цель не движется без разрыва: `set_targets` только для `need`.
  - Разрыв снимает цель (`close_batch`, `answer`).
- **Швы `acceptance/4/seams.tsv` s5–s11** — это трассы автомата: `healthy-under-write`, `rupture-drops-target`, `last-at-follower`, `leader-voters-changed`, `two-voters-refused`, `answer-at-tick-instant`, `commit-at-deadline-instant`. Итог и слова совпадают с последними утверждениями трасс.
- **Формы, где они есть, совпадают с прозой** (по чтению агента, выборочно сверено мной):
  - имена опций, умолчания, обязательность `-deployment`, `--sha256`, `-high`/`-low` против `-off`, типы `-days`/`-alarms`;
  - число аргументов `secrets`, `tls status`, `w2c-ca.sh` и 13 ролей `w2c-run.sh`;
  - коды и слова строк `refusals.tsv` 2.1–2.5 (`refused`, `unknown-row-form`, `unreadable`, `busy`, exit 1/2/!0).
- **Счёты:**
  - вердикты 946/202/744, набор Б — 43 случая;
  - 11 `platform_fields`, `PASS_WAIT_MAX` = 9000, `stop_timeout` 20…50;
  - арифметика веса вида в приёмке 2;
  - шаги основания домена.

## Б

### Б1. У юнитов платформы нет группы сокета своей роли

P/02.4 Н1.1 перечисляет `SupplementaryGroups=` у каждого юнита:
- `w2c-resource.service` (02.4:60) — `w2c-store w2c-events`;
- `w2c-console.service` (02.4:65) — `w2c-store w2c-events w2c-secrets`;
- `w2c-domain`, `w2c-domainconsole`, `w2c-domainagent` (02.4:661, 666, 672) — те же;
- `w2c-controller@.service` (02.4:62) — «the group w2c-<sub>controller», без `SupplementaryGroups=`.

Группы роли `w2c-<role>` нет ни у одного. А у рабочих юнитов она есть: `<dep>-<sub>worker` (02.4:67), `<dep>-<sub>domain` (02.4:679).

Сокет роли — 0660 с `SocketGroup=<role group>` (02.4:56; P/01.2 Н1.1: «platform role: w2c-<role>»). P/02.5 Н3 «install» п. 2 (02.5:185) требует «Units: `SupplementaryGroups=<role group>`».

Процесс `User=w2c` без группы `w2c-console` не откроет `/run/configstore/console.sock`: EACCES. То же у ресурса, контроллера и процессов домена. Реализация, которая пишет юниты по перечню Н1.1, а перечень читается как полный, получает сервер, где ни один процесс платформы не дойдёт до хранилища. Зачётная приёмка P/02 живого systemd не поднимает и этого не увидит.

Правка: в Н1.1 у каждого юнита платформы — `SupplementaryGroups=w2c-<role> …`, у контроллера — `w2c-<sub>controller` в `SupplementaryGroups=`. По ADR-0121 доп. (2) п. 4 — правится сразу.

## С

### С1. Два голосующих и `-last` без `-allow-downtime`: автомат пропускает перезапуск лидера без кворума

Н1.9 `pre` (02.4:475–477): «at most two voters — only with -allow-downtime … and there is no poll; two voters without the flag — the refusal by the deadline above, a named bound». Это правило ADR-0120 доп. (6) п. 3 (Ф4). Но `leader:` (02.4:480–481): «with -last both pre are replaced by the -last check». Автомат при `input.last` проходит, когда «every other voter is live» (`tick-2`).

При V = 2 сервер лидера с одним `-last` проходит проверку, едва второй голосующий жив. Затем перезапуск лидера, и кворум 2 из 2 теряется, а согласия оператора на простой (`-allow-downtime`) нет.

Для V ≥ 3 правило «живы все прочие» верно: V − 1 ≥ кворума. Для V = 2 — нет: 1 < 2. Трассы V = 2 с `last: true` в `rollout-poll.traces.tsv` нет. (Проверка моделью — раздел «Модель».)

Предложение: правило «≤ 2 голосующих — только с `-allow-downtime`» — до выбора между `pre` и проверкой `-last`, в `mode`. В автомате: `input` — «≥ 3 voters, или -last и ≥ 3», либо переход, отказывающий `-last` при V = 2 без флага. Плюс трасса `two-voters-last-refused`.

Попутно о V = 1 (коробка). `input` говорит «≥ 2 voters», проза — «at most two voters — only with -allow-downtime». Системный сц. 09 шаг 5 (`@manual`) ждёт отказа, код 2. Какой отказ, со словом каким и сразу ли, а не по сроку, — не сказано.

### С2. Каталог отказов `forms/refusals.tsv` не держит отказы команд Н1.9 и части Н1

Н4 (02.4:807–809): «The normative refusal catalogue of this chapter is `forms/refusals.tsv`». Строк 2.4 — 22, и среди них нет ни одной строки:
- **`rollout`:**
  - пять слов опроса из автомата — «voters changed», «-last: not the leader», «leader goes last», «not enough live voters», «-last: voters not live»;
  - повтор `<sub>` (02.4:464);
  - неизвестное состояние в `mode` (02.4:465–466);
  - несделанный барьер по `wait` (02.4:539–540, «the output names the unfulfilled part»);
  - отказ шага (`failure`).
- **`manifest get`:** несовпадение `--sha256`, нет строки, ошибка записи — код 2 (02.4:445–446).
- **`tls status`:** коды 1 и 2 (02.4:607–611).
- **Н1.7 `refuse`:**
  - настоящий каталог `/etc/w2c`;
  - `W2C_DEPLOYMENT`, `CONSOLE_ROOT`, `DOMAIN_SERVER`, форма `W2C_HOLD`;
  - хранилище не ответило на `/v1/status` (02.4:390);
  - macOS, код 2 (02.4:353).
- **Отказы старта:**
  - неполный комплект, код 2 (02.4:301);
  - нет корня (02.4:138);
  - файл окружения не читается;
  - владелец тома части (02.4:100);
  - `boot-rows.json` не по форме (02.4:627).

Генератор отказов (`gen_refusals`) берёт только каталог. Эти отказы реализация увидит лишь в прозе, а модель с пакетом — нигде.

Расходятся и коды двух строк, которые есть:
- `address_without_tls` (2.4 стр. 17) — код «-», а Н1.6 (02.4:301–306) — «a start refusal, code 2»;
- `process_environment` (2.4 стр. 8: манифест не грузится, схема выше сборки, файл прав устарел, бюджет памяти) — «exit !0». А Н1.1 (02.4:48) опирается на код 2: `RestartPreventExitStatus=2`, и строка 2.3 стр. 1 — exit 2. Код 1 даёт перезапуск каждые 2 с.

Предложение: строки каталога на все отказы выше, коды — по прозе. `check_forms` для урока с `own`-каталогом — правило «отказ с кодом в прозе Н1/Н3 ⇒ строка каталога». Сейчас `check_refusals` при `own` судит только имена, грамматику кода и нумерацию.

### С3. Формы и lifecycle ссылаются на «P/02.4 Н1.9» за командами, которых там больше нет

Коммит 6e3ee71a2 («express command options … as source forms») убрал из Н1.9 перечень команд. Ушли в том числе:
- `w2c-run.sh` с ролями (`configstore | controller <sub> | … | workers | rights | part <sub> <part>`);
- `w2c-workers.sh`;
- `manifest status`.

Что ссылается в пустоту:
- `operator-commands.tsv:26–37` — 12 строк `w2c-run.sh` — «P/02.4 Н1.9 w2c-run.sh»;
- `operator-commands.tsv:10` и `daemon-flags.tsv:11` (`manifest status [-rights]`) — «P/02.4 Н1.9»;
- `lifecycle.md:24` — тоже. Н1.9 сейчас не называет `manifest status` ни разу (0 мест);
- 02.3:217, `vectors/exec/README.md:6`, 02.1 — «Н1.9» за программой исполнителя.

Описание осталось одной строкой таблицы `lifecycle.md:24–25, 30`: что выводит `manifest status`, с какими кодами — нигде. `w2c-workers.sh` — ни строки формы, ни делегирования в шапке `operator-commands.tsv:4–5`. А `lifecycle` называет и `w2c-run.sh workers`, и `w2c-workers.sh`: чем запускать `w2c-workers.service`, не ясно.

Предложение: в Н1.9 — короткий раздел «Runner and status commands» с выводом и кодами `manifest status` и с тем, чем `w2c-workers.service` запускает скрипт. Ссылки форм — на него.

### С4. «Implementation decides» отдаёт реализации то, что форма уже закрепила

- 02.3:370 (п. 3): «the name and the form of the installer command (`manifest put`, `manifest status`)». Но `operator-commands.tsv:8, 10` закрепляет слова argv, и шов `acceptance/4` s1 зовёт `w2cctl manifest put`.
- 02.5:254: форма команд `w2cctl mirror|space|retention` — у реализации. А `operator-commands.tsv:13–15` и `daemon-flags.tsv:15–19` её закрепляют.
- 02.3:368: «the form of the log line at the stop on a change of the mark» — у реализации. А `refusals.tsv` 2.3 стр. 2 (`manifest_changed`) ставит в `log` закрытый отрывок «manifest changed, restart».
- 02.3:371 (п. 4): «the size limit of the manifest row» — у реализации. А 02.2:64–67 и 02.3 шаг 6: потолок — `max_value` хранилища, «the installer has no ceiling setting of its own».

Генератор увидит две нормы, и обе нормативны. Пункты «Implementation decides» устарели — их убрать или сузить («расположение исходного файла»).

### С5. Читатель вида не стартует в окне между записью вида и метки

Порядок записи `manifest put`: строка → вид → метка (02.3 шаги 14–18; 02.2 «Races»).
- **Процесс-загрузчик** (02.3:215–216, «Races» 02.3:228): метка ниже строки на старте — не отказ, процесс служит по строке.
- **Процесс-читатель вида** (02.2:789–793 «Reader» шаг 2): «If the view … its rev or sha256 ≠ the mark's … do not start, exit code 2». Начало процесса (02.3:295–296): «no start, code 2, without a restart».

В окне между записью вида (rev 2) и метки (rev 1) читатель вида выходит с кодом 2 и стоит до оператора. Загрузчик в том же окне стартует. «Races» 02.2:798–800 («a starting process … reads the row and the view of the same rev») это окно не покрывает: метку он читает первой, и она старая.

Предложение: читатель с видом новее метки ведёт себя, как загрузчик со строкой новее метки — служит по виду и ждёт метку. Код 2 — только при виде ниже метки или при несовпадении `sha256`.

### С6. Вес вида меряется до того, как известен его `rev`

02.3 шаг 7 (02.3:252) строит вид «for the new row» и судит `toolarge`. Строка читается на шаге 9, новый `rev` ставят шаги 12 и 14. А вес вида — `{form, rev, sha256, manifest}` (02.2:760), и приёмка 2 считает цифры `rev` («rev of one digit»).

На границе цифр (rev 9 → 10) одна реализация меряет с заглушкой и пишет, другая меряет после чтения строки и отказывает.

Кроме того, шаг 17 (запись вида после записи строки) исхода `toolarge` не даёт. Если вес изменился между шагом 7 и 17, строка уже записана.

Предложение: шаг 7 меряет с `rev` = текущий + 1 (или с верхней оценкой — 16 цифр `2^53 − 1`), шаги 9–14 этого не меняют.

### С7. Список целей `door.pass.calls` своей подсистемы — без `requests`

02.1:207: «of the own subsystem — only `unit.rows`, a table, `policy`, `next_id`, `operations` with `door.pass.operations`». Связь 131 `02.1-installer.relations.json` (форма — норма) допускает `{@unit.rows, policy, next_id, operations, requests} | keys(tables)`.

Генератор по прозе отказывает `calls: [<своя>/requests]`, генератор по связям — принимает. Случая в `puts.tsv` нет. Правка — проза по связи 131. P/06.3 Н1.9 тоже называет `<s>/requests`.

### С8. Устаревшие классы отказа `value` и `reference`

Н4 02.1 (02.1:1226) знает четыре класса: `text`, `form`, `relations`, `catalogue`; слово — `refused:<класс>`. Но в тексте:
- `vectors/exec/README.md:13`: «the loader refuses `refused:value`» (по `classes.tsv`, `a91_exec_*` → `form`);
- Н5 02.1:1288: `c6_*` — «`value`» (по `classes.tsv`, `c6_secrets_reads_bare` → `form`);
- 02.1:1289: «`reference`» (по `classes.tsv` — `relations`);
- построенные блоки «Форма» 02.1:316 и «Семьи данных» 02.2:155: «`refused:reference`».

README приёмки 1 говорит, что `value` стал `form`, `reference` — `relations`. Генератор может выдать пятое слово.

Правка — проза. Для блоков — источник: описания `02.1-installer.schema.json` у `cut_at` и вид 02.2.

### С9. Пример суррогатной пары записан живым символом

02.1:71: «(`\ud800`, `\U0000d800`, and as a pair `😀` — YAML does not join pairs…)». В тексте стоит живой U+1F600 (байты f0 9f 98 80), в переводе тоже. А случай `acceptance/1/cases/c5_escape_surrogate_pair.subsystem.yaml:25` — `unit: "😀"`, экранами.

По буквам примера живой эмодзи в кавычках — отказ. Генератор может начать отказывать допустимому UTF-8 вне BMP. Экраны пропали при переносе (98de0c654 последним трогал строку). Правка: `` `😀` ``.

### С10. Файл прав при установке — сверять с отказом или писать?

- 02.4 Н1.7 `refuse` (02.4:386): «the rights file is not equal to the generated one (chapter 2.5)» — отказ установки.
- Шаги той же установки (02.4:389): «→ the center: own for configstore, **the rights file**, the group drop-in → enable». И `catalog.tsv` ставит установщика писателем файла.
- P/02.5 Н3 «install» шаг 1 — `--check` против `MANIFEST_DIR`; Data (02.4:33) — файл только в «reads».

Одна реализация переписывает файл на каждом обновлении, другая отказывает каждому обновлению, которое меняет права. P/02.4-08 («refusal on a stale rights file») наследует ту же двусмысленность.

Предложение: сказать порядок. Сверка `refuse` — между файлом, собранным из `MANIFEST_DIR` (P/02.5), и файлом, который пишет шаг «center»? Или установка пишет файл и отказывает только тогда, когда запись не удалась?

### С11. У рабочего на домене (`<sub>domain`) нет комплекта роли

Н1.6 `roles` (02.4:275–284) перечисляет комплекты:
- `configstore`, `configstore-door`;
- `resource`, `console`, `domain`, `domainconsole`, `domainagent`;
- `<sub>controller`, `<sub>worker`.

`<sub>domain` в списке нет. А юнит рабочего на домене идёт с `W2C_ROLE=<sub>domain` (02.4:679), и комплект ищется по `W2C_ROLE`.

Одна реализация выпускает `/etc/w2c/tls/<sub>domain`, другая оставляет без комплекта. Тогда его клиенты `https://` отказывают («https:// without a kit — a refusal»).

### С12. `DOMAIN_SERVER` при повторной установке

02.4:366: «the installation writes the line into w2c.env, like TIMEZONE, and only with yes enables…». 02.4:367 (конец): «The installation does not rewrite an existing w2c.env and does not carry values over».

При повторе с `DOMAIN_SERVER=yes` поверх строки `no` (или без строки) одна реализация правит `w2c.env`, другая — нет. Что с уже включёнными юнитами домена при `no` на следующем повторе — не сказано. У `W2C_DEPLOYMENT` есть отказ при расхождении, у `DOMAIN_SERVER` — нет.

### С13. Какие строки `secrets seal` обходит по умолчанию

- 02.4:37 (Data): «the default of the prefixes is `domain/`».
- 02.4:567: «the default of the prefixes: domain/, identity/ and the rows of units and tables of all manifests».
- 02.4:583: обход — по семьям каталога, где писатель — `admin(w2cctl secrets seal …)`.

Три правила дают разное множество. Например, `identity/` семьи каталога не имеет: по 567 её строки обходятся и дают `unknown-row-form`, код 1; по 583 они вне обхода, код 0.

### С14. Грамматика значений в формах команд неровная

- **`rollout`** (`operator-commands.tsv:11`) — `{"type":"array","items":{"type":"string"},"minItems":1}`. А проза (02.4:463–464): `<sub>=<sha256>`, `<sub>` — по грамматике имени P/02.1, `<sha256>` — 64 строчных hex, повтор `<sub>` — код 2 до действий. У `manifest get` образец хэша в `bad` есть (`daemon-flags.tsv:12`).
- **`mirror`** (`operator-commands.tsv:13`) — любое одно слово. Проза (02.4:428) — `on|off`.
- **`mirror.copies`** (02.4:428) — опции в `daemon-flags.tsv` нет, задать нечем.
- `bad` у `manifest get` кода не несёт, а неверный `--sha256` — это несовпадение, код 2 (02.4:445).

Предложение: `positionals` у `rollout` с `pattern` и `uniqueItems` по `<sub>` (или отказ повтора — строкой каталога, С2); `enum: [on, off]` у `mirror`; опция `-copies`.

## М

### М1. Счёты расходятся с данными

- P/02.1-20 (02.1:1368) и 02.1:1314: «31 reserved words». Схема `subName` (02.1-installer.schema.json; блок «Форма» 02.1:917) — 36.
- 02.3:324 и `acceptance/3/README.md:6`: в `puts.tsv` «82 installations», «3 last» — `calls_first_*`/`calls_second_kind`. В файле 84 случая, последние — `calls_kept_bad`, `calls_pulse_ok`, `calls_pulse_bad`.

### М2. Номера связей вперемешку: прежние и нынешние

- 02.1:242: «rules 46–47 are removed». В `relations.json` строки 46 и 47 есть и значат иное — `placement.affinity.table`, `server_field`.
- 02.1:1285: «row 84 is removed», а строка 84 (`objects.rows[]`) есть.
- Рядом `c8_ref125_*`/`c8_ref126_*` и Н1.3 «row 122» — нынешние номера.

Читатель не знает, какой счёт где. Предложение: «прежние номера» — с пометкой «(до перенумерации …)», или по `id` связи.

### М3. Код отказа на нечитаемой метке: проза «≠ 0», форма и приёмка — 2

02.3:54 и блок семьи метки (02.3:158) — «code ≠ 0». `refusals.tsv` 2.3 стр. 3 (`manifest_mark_unreadable`) — `exit 2`, приёмка 2 сц. 09 `rev_spoiled` — 2, и README приёмки 2:106 сам отмечает расхождение. Форма нормативна, проза отстала: «code 2».

### М4. «manifest put» шаг 3 в 02.2 не называет файлы

02.2:773 определяет «unchanged» как те же yaml, оболочка и вид. 02.3 Н1.5 и шаг 10 добавляют файлы. Прочитанный отдельно, 02.2 назовёт «unchanged» правку одних файлов.

### М5. Висячие ссылки

- 02.1 Н3 шаг 4 (02.1:1150) — «Н1.2 lease, unplaced, places»: в Н1.2 их нет.
- `vectors/canonical/README.md:48` и 02.4:73 — заголовок «Программа воркера из строки». В источнике он «The worker program from the row».
- 02.3:207 — «Проверка при старте»; в `schema.md` заголовок «Check at start».
- P/02.4-12 — «М11/12-02 (sc. 01 of the acceptance of М11/12)»: в `id-map.tsv` М11/12-02 указывает обратно на P/02.4-12.

### М6. Русские имена процедур в английском 02.3

`загрузить` и `загрузить_каталог` — 7 мест в 02.3 (203, 214, 234, 247, 324, 382) и 02.1:1358. В 02.1 те же процедуры — `load`, `load_catalogue`. Это С4 ревью норм ADR-0121 (имена функций), здесь — конкретные места.

### М7. Пункты чеклиста отстали от швов

- P/02.4-09 (02.4:875): «the operator commands … are not executed by TSV».
- P/02.4-14 (02.4:880): `secrets` — векторами и чтением.

А `acceptance/4/seams.tsv` s2–s4 исполняют `w2cctl secrets new|rotate` через `CALL command`, s5–s11 — опрос реализации. P/02.4-22 там же: «not run by an implementation».

Пункты — по швам: что теперь исполняется, что по-прежнему чтением.

### М8. Порядок `enable` при установке и порядок старта

- Установка (02.4:391): ресурс → части → рабочие → контроллеры → консоль.
- Н3 «server start» (02.4:768–776): ресурс → контроллеры → консоль → части → рабочие.

На Linux порядок старта задают `After=` юнитов, так что вреда нет. Но для macOS (launchd порядка не держит, 02.4:774–775) и для читателя стоит один порядок.

### М9. Голосующий без адреса в `members`

`types:` автомата: «members: … a member without -api is absent; may be {}». `send_status` опрашивает голосующего «at members[v]». Голосующий без `-api` (P/01.3:191: «without `-api` the member is not in `members`») ответить не может и живым не станет никогда. Опрос кончится отказом по сроку через 300 с.

Если такой голосующий в группе возможен, нужен предел в `bound` или отказ в `mode` («voter without address»). Если невозможен — строка в `input:` («every voter is in members»).

## Модель: перегонка v120 на нынешней форме автомата

Не кончена. Агент построил `cammeta-quint` `v120f/` (коммит 298a82d, `v120f/ПРЕРВАНО.md`):
- `machine.qnt` порождается из формы скриптом `tools/gen_machine.py` — действия на CEL, в отличие от v120, руками больше не переводятся;
- судьи `rp.qnt` правились, когда пришёл стоп.

Итогов судей и меры доп. (5) п. 2 (в) нет. Первые прогоны дали один ход `c3jl-invQuorum-between`: смена состава после ответов своего члена и лидера в партии прохода. Это предел, названный в `env:` (строка 74) и в `bound`, — не дыра.

Что осталось следующему ревьюеру:
- достроить судей;
- прогнать базы и мутанты (`runs/tracemut.sum` — частичная карта «мутант → трассы»);
- проверить С1 (V = 2 с `-last`) моделью;
- обновить `unproven` по итогу.
