# D. Карта механизмов кода цикла MiniMax (P01.316, участок «код цикла»)

Источник: голое хранилище `/home/pilot/git/minimax-loop.git`. Ссылки даны в форме `<ревизия>:<файл>:<строка>`.
Ревизии: **6e1881e09** — прогон попытки 8 (паспорт: `loop` = 6e1881e097…, `passport.json` попытки);
**e62185f8b** — P01.226 (перемотка с 6e1881e09); **ebaed1715** — P01.310 (перемотка с e62185f8b).
Задание попытки 8: `/home/pilot/work-p01310/task-a8.orig.json`, sha256 9eeabadb…, совпадает с `task_sha256` паспорта
`/home/pilot/owner-receipts/attempt8-review-inputs/minimax8-rounds/run/passport.json`. Ключи, заданные в нём:
`generation_only: true`, `agent: miniswe`, `miniswe_head: stage`, `miniswe_stage_check: true`, `miniswe_checks: 6`,
`miniswe_steps: 60`, `miniswe_plan_round: true`, `miniswe_plan_steps: 60`, `miniswe_plan_idle_steps: 8`, `miniswe_design_max: 32000`,
`miniswe_focus: true`, `miniswe_stable_prefix: true`, `context_tokens: 200000`, `stall_rounds: 3`,
`stages.norm_trace / norm_trace_mutation / norm_trace_mode / stage_tests / profile_probe: true`, `stages.mech` (build `go build ./...`,
vet, test `go test -race -count=1 ./...`, timeout 1800, `require_own_tests: true`). `max_tokens`, `_out_max`, `miniswe_section_max`,
`miniswe_rest`, `miniswe_bg_jobs`, `profile_complete_from`, `require_build/require_cmd` не заданы.

В режиме mini-SWE один «ход» цикла — это один раунд mini-SWE со свежим разговором: `chat` всегда возвращает циклу вызов `done`
(`6e1881e09:agent_miniswe.py:1381`; `ebaed1715:agent_miniswe.py:1815`), а `done` в режиме этапов вызывает `stage_round`
(`6e1881e09:loop.py:5202`). Значит, **каждый раунд, чем бы он ни кончился (сдача, окно, лимит шагов, ошибка), — это проверка этапа**.

---

## 1. Как это устроено в 6e1881e09

### 1.1. План этапов и ворота в generation_only
- `generation_plan` (`6e1881e09:loop.py:2557`): строки `forms/stages.tsv` M; ворота формы `accept:/seams:/vectors:` судейские и
  **игнорируются** — у каждого этапа ворота `mech` (docstring 2558–2561, `gate="mech"` 2579). Если в ячейке ворот формы есть
  `code:*` — добавляется вторая проверка `code` с `code_n` = номер строки формы (2578–2583). `when` с ключами профиля не
  вычисляется — этап включается и пишется в `when_unevaluated` (2571–2577; у попытки 8 это `group`).
- Подготовка отвергает в generation_only всё судейское: ключи задания `judge_cmd, runner_dir, targets…` и `stages.judge_entry,
  stand, profile, accept_cmd…` (`6e1881e09:variant_b.py:182–184`, `generation_violations`).
- Цепочка ворот `mech` (`6e1881e09:loop.py:4057–4062`), всё — один раз за раунд (кэш), видимые модели строки суммируются:
  1. `mech_gate` (2677): build → vet → test через b11-call model-code на копии work/ (`stages.mech.cwd`); vet и test только
     после зелёной сборки. Итог `variant_b.mech_summary` (`6e1881e09:variant_b.py:360`): 4 пункта (build, vet, tests,
     own tests); «own tests» = в модуле есть хоть одна функция Test* и `go test` дал хоть один пакет `ok`
     (`variant_b.py:423`) — **на весь модуль, не на этап**.
  2. `profile_gate` (3029): полнота профиля против реестра M. Не последний этап — только **совет** (`advice`), не блокирует, не
     входит в подпись застоя (3053–3054, docstring 3030–3034); последний этап — все цели урока, блокирует, в подписи (3055–3060).
  3. `profile_probe_gate` (2752): если `stages.profile_probe: true` (2756) — сборка профиля, каждая объявленная команда
     `vectors` на конвертах строк M (судятся внешняя форма ответа и native-форма строки, **не исход**, `profile_probe.py:1–40`),
     каждая команда `stand` с JSON-примером M — один старт («жив после окна» — зелёный). Пока профиль не читается — пропуск
     (2731, 2772–2773).
  4. `norm_trace_gate` (2934): если `stages.norm_trace: true` (2940) — пункты чек-листа, «положенные» этапу (см. 1.2).
  5. `stage_tests_gate` (3008): если `stages.stage_tests: true` (3011) — каждый не-main пакет, чей код изменился с закрытия
     прошлого этапа, имеет свои тесты и `go test` прогнал их `ok` (`6e1881e09:mutation_trace.py:355–380`; `package main` освобождён,
     365–366).
- `code` (`6e1881e09:loop.py:4053–4056`): `code_gate` (2619) — анализатор `tools/codecheck` по строкам `forms/code-rules.tsv` урока
  в копии модели; `code_view` (2664) берёт строки с `from_n <= code_n` (2669) — накопительно. Строка без отображения в поле
  профиля `code` — красная до анализа.
- `run_stage_gate` (3885): этап зелёный, когда **все** его проверки ok; мера — сумма green/total; подпись застоя — список
  подписей проверок (3906). При одной проверке возвращается `dict(rs[0], …)` (3897–3898), при нескольких — новый словарь
  **без ключа `mech`** (3903–3904).

### 1.2. Норм-трасса (`// norm: <ID>`)
- `norm_trace.py` одинаков во всех трёх ревизиях. Пункт = строка `- [ ] **<ID>** …` в `<урок>/spec/*.norms.md`
  (`6e1881e09:norm_trace.py:14`). Связь — строка `// norm: <ID>[, <ID>…]` **прямо над** `func TestXxx(t *testing.T)` в
  `_test.go` модуля; другие строки-комментарии между ними допустимы, пустая строка или код рвут связь (`annotations`, 187–215;
  `NORM_LINE_RX` 16, `TEST_FUNC_RX` 17).
- Этап пункта — только из колонки `norms` формы этапов (`cell_items` 150, `explicit_assign` 157, `stage_map` 179); пункт, не
  названный ни одним этапом, — отказ подготовки.
- Положено этапу i: пункты с этапом ≤ i; на **последнем** этапе — все (`6e1881e09:loop.py:2950–2952`); пункты с пометкой без
  `test` (только `[reading]`/`[stand]`) исключены и показываются нейтральной строкой (2953–2954, 2961–2962; P01.248).
- Запуск: только связанные тесты, `go test -json -count=1 -run '^(…)$' <пакеты>` (`norm_trace.py:229–240`).
- Вердикт `judge` (337): **«no test names it»** (350) — ни одна строка `// norm:` не называет пункт; иначе каждый связанный тест
  должен `pass` (skip, fail, «did not run», пакет не собрался — красный, 354–367). Модуль сам говорит: «The check never proves that
  a test checks the norm — the court and the reading of the code do» (`norm_trace.py:7–8`, и `NOTE` 414–420 для модели).
- Над трассой (если включено в задании; в попытке 8 включено): мутации (`norm_trace_mutation`, `mutation_trace.py:1–16`; до 8
  мутантов на пакет, 48 за раунд, `PER_PACKAGE/PER_ROUND` 31–33) и режим (`norm_trace_mode`, `mode_trace.py:1–25`).
- Подготовка попытки 8 (паспорт `prep.norm_trace`): 53 пункта; по этапам store_core 11, http 8, rights_eval 1, rights 8,
  daemon_doors 1, daemon_copy 3, durable 5, group 16; у `model`, `launch`, `jcs` пунктов нет; 12 пунктов без `test`.

### 1.3. Закрытие этапа, переход, generation_done
- `stage_round` (`6e1881e09:loop.py:4392`): `go = generation_only` (4416); **в generation_only прежние этапы не перепроверяются**
  (`regress = []`, 4417) — регресс ловится только тем, что наборы норм и `code`-строк накопительные, а mech общий на модуль.
- Этап закрыт, если `g["ok"]` (4438–4440), затем `S["cur"] += 1` (4445); в generation_only — **один этап за раунд** (4449–4450),
  следующий получает свою записку этапа в начале следующего хода (`S["pending"]="advance"` → `stage_begin`, 4926).
- `generation_done`: после закрытия последнего этапа `cur is None` (4461–4462), кандидат замораживается
  (`freeze_candidate`, 4507–4508). Условие последнего этапа включает **финальную полноту профиля** (3055–3060) и **все** пункты
  трассы (2950–2952). У попытки 8 последний этап `group` был красным: 71/83 (mech 47/59, code 24/24) в раундах 22–24 → `stuck`.
- Этап может закрыться **только по mech** (без единого пункта чек-листа): если ему не положено ни одного пункта (норм-трасса
  ничего не добавляет при пустом `due`) и нет `code:*`. В попытке 8 так у `model`, `launch`, `jcs` (код у них был), а у
  `daemon_doors`, `rights` нет и `code` — только mech+пробы+трасса.

### 1.4. Проверки «форма как данные» (table_driven: C05, C13, C15)
- Строки M (пин c4a17f05 и текущий курс одинаковы): `C05 table_driven daemon_flags {"form": ".../daemon-flags.tsv", "min_cell": 9}`
  этап launch; `C13 … refusals …/refusals.tsv` этап http; `C15 … runtime_constants …/runtime-constants.tsv` этап http
  (`3be948e5d:Platform/01-store/forms/code-rules.tsv:12,20,22`).
- Цикл: ячейки формы ≥ `min_cell` кодовых точек (строки без `#`, включая заголовок) → 16-символьные хэши sha256
  (`6e1881e09:code_checks.py:185–218`, `derive` 249–259).
- Анализатор `tableDriven` (`6e1881e09:tools/codecheck/main.go:377–440`) проверяет в **одном каталоге пакета**, отображённого
  моделью в поле профиля `code` (`parseDir` — не рекурсивно, только не-тестовые `.go`, 225–250):
  (1) есть `//go:embed`, совпадающий по sha256 байтов с формой; (2) ни один строковый литерал не равен ячейке.
- Литерал — только `*ast.BasicLit` типа STRING по значению как написан (`stringLit`, 952–959); в комментарии: «no trimming, no
  folding of expressions, calls or constants» (371–373). **Склейку `"a"+"b"`, `fmt.Sprintf`, `strings.Join`, срезы рун/байт,
  литералы короче `min_cell` по частям — проверка не видит.** Не видит и литералы в других пакетах (например, в `main` демона),
  если модель отобразила имя строки на другой пакет. Embed проверяется на наличие, а не на то, что таблица из него читается.
- В попытке 8 последняя запись `code_checks` — 24/24 зелёных (паспорт, раунд 24).

### 1.5. Детектор застоя
- Порог: `budget(task)["stall_rounds"]` = `task.stall_rounds`, по умолчанию 3 для варианта B (`6e1881e09:variant_b.py:40, 801`).
  `STALL_ROUNDS = 3` в `loop.py:66` — для старого режима.
- Правило generation_only — `mech_stall_update` (`variant_b.py:777–792`): подпись `[текущий этап, mech_sig]` (786); тот же
  результат подряд → счёт +1, иной → 1; раунды, запущенные циклом сам (`auto`), не считаются (784). `mech_sig` = подпись
  `run_stage_gate` (`loop.py:4539`) — для mech это `[b_ok, диагностики сборки, v_ok, диагностики vet, t_ok, упавшие тесты,
  статусы пакетов, own_ok]` (`variant_b.py:431`) плюс красные ID трассы, подпись проб, профиля (на финальном этапе),
  stage_tests, code. Любая смена набора красного сбрасывает счёт; изменение файлов без смены результата — нет.
- Вызов и стоп: `loop.py:5354–5366` → `pp["stuck"]` (`rule`, `mech`, `green`), статус `stuck`, `stop_candidate`.
- Особенность: `pp.stuck.mech` берётся из `rnd["mech"]` (`loop.py:4505`), а у этапа с двумя проверками (`mech`+`code`)
  `run_stage_gate` ключа `mech` не возвращает (1.1) → в паспорте попытки 8 `stuck.mech: null`, у всех раундов group `mech: null`;
  так же теряется `per["own_tests"]` (4444).
- `REPEAT_MAX = 3` (`loop.py:68`, 5297–5301) — напоминание о трёх одинаковых вызовах подряд, к застою отношения не имеет (в
  попытке 8 сработало на трёх `done` подряд — `repeats: [{turn 24, tool done, n 3}]`).
- `stage-check` внутри раунда — до `miniswe_checks` (6) раз (`agent_miniswe.py:1136`), только текущий этап (1146), ничего не
  закрывает и в застой не считается.

### 1.6. Стоп по окну, резерв ответа, обрезка вывода
- Внутри раунда mini-SWE (свежий разговор, без сжатия) перед каждым вызовом `LenientModel.query` → `budget_check`
  (`6e1881e09:agent_miniswe.py:1071–1073`, 1021–1063). Оценка следующего входа `lp` = prompt последнего вызова + его ответ +
  новый текст/4 (1038; `CHARS_PER_TOKEN = 4`, 992). Сначала лимиты прогона и раунда (`max_input_tokens`, `max_tokens_run`,
  `max_cached_run`, `miniswe_round_max_input_tokens`, 1043–1055), затем окно: `limit = int(WINDOW_SHARE × context_window)`
  (1057) = 0,9 × 200000 = **180000**; стоп, если `lp + answer_tokens ≥ limit` (1058), где резерв ответа `MAX_TOKENS = 32000`
  или `task.max_tokens` (993, 996–998) — т. е. фактически раунд кончается при оценке входа ≈ **148000** токенов. Исход
  `window_in_round` кончает **только раунд**; затем, как всегда, `done` → проверка этапа. В попытке 8 — 15 из 24 этапных раундов
  (`passport.window_in_round`, `next_estimate` 148–151 тыс.).
- `WINDOW_SHARE = 0.9`, `CONTEXT_TOKENS = 200000` (`loop.py:56–57`), `context_window` (2991).
- `KEEP_TURNS = 6`, `KEEP_CHARS = 30000`, `WORK_MAX = 200000`, `READ_LINES = 400`, `READ_LINES_TIGHT = 150` (`loop.py:48–62`) —
  механизм сжатия и `read_file` **собственного разговора цикла** (`compact` 1019, `tool_call` read_file 353, переключение
  5092–5097); внутри раунда mini-SWE (bash) они не действуют. У попытки 8 `compactions: 0`.
- `HEAD_MAX = 360000` (`loop.py:51`) в режиме этапа ограничивает только место под правила code-checks в голове
  (`agent_miniswe.py:520–524`).
- Обрезка вывода команды: `shell/agent_shell` → `clip(..., MAX_OUT = 12000 (или task._out_max) − длина шапки, hint=True)`
  (`loop.py:49`, 539, 595). В 6e1881e09 — пятая часть на голову, остальное на **хвост** для любого вывода (`clip`, 280–316),
  пометка называет строки вывода, а не файла. По замеру P01.310 (`reads.json`): 912 команд, 6,27 млн знаков наблюдений,
  385 обрезанных выводов; до первой записи в раунде — 420 команд, 3,73 млн знаков.

### 1.7. Голова этапа
- Режим `miniswe_head: stage` + `stable_prefix` (по умолчанию вкл., `agent_miniswe.py:335–338`): системная часть
  `head_const` (528–536) — слова системы, текст задания, список файлов урока, правила code-checks, `work/DESIGN.md` целиком до
  `miniswe_design_max` (32000, 428; обрезка с пометкой — `design_text` 486–503); голова этапа открывает задание раунда
  (`stage_prompt` 792–801).
- `stage_head` (621–715): `rules/KIT.md`; README урока — **только на первом этапе** (684–686); строки пунктов чек-листа,
  названных ячейкой `norms` этапа, дословно (`due_items_text` 587–606); для каждой ссылки `P/NN.K Nx` — `N0` главы и сам раздел;
  ссылки `forms/…`, `vectors/…`, `data/…`, `acceptance/…` — текст файла. Блок больше `SECTION_MAX = 20000` **байт** (341;
  `miniswe_section_max`, 350–352; 0 — без лимита) показывается оглавлением с номерами строк (`outline_text` 384–400) или
  началом до лимита с точной командой `sed` (`truncated_text` 403–424). Отсутствующий в M путь (`cited_missing`) в
  6e1881e09 **молча выпадает** из головы (708–712).
- Записка этапа `stage_note_text` (`loop.py:4624–4675`): цель, нормы, ворота словами, «This attempt has no judge…» (4655–4658),
  NOTE трассы/мутаций/режима/stage_tests/проб.
- Размер (замер P01.310 `heads/base/sizes.json`, этап group): system 41535 зн., user 48610 (первый раунд) / 47151 (продолжение).

### 1.8. Раунд плана (plan_idle)
- `plan_round_due` (`agent_miniswe.py:578–581`): `miniswe_plan_round` + `miniswe_head: stage` + нет `work/DESIGN.md`; один раз
  перед первым этапным раундом. `plan_round` (1212–1252): шагов `miniswe_plan_steps` (по умолчанию `PLAN_STEPS = 60`, 434).
- `plan_idle_check` (967–990): после появления `DESIGN.md` — стоп, если `miniswe_plan_idle_steps` (по умолчанию 8, 430; 0 —
  выкл.) шагов подряд не меняли ни один из `DESIGN.md, PLAN.md, NOTES.md, GUESSES.md` (952–964). Попытка 8: раунд плана
  кончился `plan_idle_in_round` на 33-м вызове, DESIGN 18155 зн., 1,06 млн входных токенов (паспорт `plan_round`).
- Проверки содержания DESIGN.md (карты файлов) нет — только наличие файла (`plan_round_due`) и показ в голове.

### 1.9. Что делает цикл в generation_only
- Судьи нет: `run_gate` ветка `mech` — «no judge at all» (`loop.py:4057`); без `judge_cmd` цикл допускает только
  generation_only (4700); суд кандидата — отдельно после генерации (`GEN_COURT`, `variant_b.py:187`).
- **Сценарии приёмки M не исполняются** (ворота формы игнорируются, 1.1). Исполняется только: mech (build/vet/test), связанные
  тесты трассы (+мутации, +режим), code-checks (статический анализ), пробы профиля (объявленные команды `vectors` по форме ответа и
  один старт `stand`-команд с JSON-примером M).
- Слова модели противоречивы: `SYSTEM` (`loop.py:1079–1081`) говорит «The runner starts acceptance by the profile … without these
  files acceptance does not start», а `GEN_SUBMIT/GEN_CHECK_EXTRA` (`agent_miniswe.py:44–51`) и записка — что судьи нет (это Н1,
  исправлено в ebaed1715).

---

## 2. Что изменили e62185f8b (P01.226) и ebaed1715 (P01.310), и чего не изменили

### 2.1. e62185f8b (P01.226)
- **$WORK как корень** (только b11): псевдоним `$WORK` в выводе (`e62185f8b:loop.py:189`), `export WORK=…` в префиксе команды
  (`variant_b.work_prefix`, `e62185f8b:variant_b.py:1403`; `JudgedEnv.prefix`), `WORK_NOTE` (`variant_b.py:1389`), слова
  `work/…` → `"$WORK/…"` в текстах цикла (`b11_paths`), строка mini-SWE «cd /path/to/working/dir» заменена
  (`INSTANCE_CD_B11`, `e62185f8b:agent_miniswe.py:86`, 985).
- **Обрезка по виду команды**: `command_kind` (`e62185f8b:loop.py:290`, `LOG_CMD_RX` 284) — сборка/тест/`stage-check` держат
  хвост, всё прочее — **голову** (4/5, 357); команда, печатающая один файл (`file_read`, 297–333), получает в пометке строки
  **этого файла** и точную `sed`-команду (374–380). Предел **не изменён**: `MAX_OUT = 12000` (49); в слова системы добавлено
  «output over about {out_max} characters is cut…, read a file in parts … about 150 lines» (`agent_miniswe.py:62–64`, 988).
- **heredoc**: слова «один heredoc с кавычками, файл до ~300 строк, правка точной заменой» (65–69); после команды с heredoc
  ≥ `miniswe_heredoc_lines` (по умолчанию 300, 79; 0 — нет) или незакавыченным с `$`/`` ` `` — заметка цикла (`heredoc_note`,
  1114; вызов 280). Команда при этом исполняется как есть.
- **bg-run/bg-status**: `BgJobs` (128), только при `miniswe_bg_jobs: true` и b11 (`available`, 139–141) — **по умолчанию выкл.**;
  до `BG_MAX = 2` заданий (115), таймаут `miniswe_bg_timeout` или 1800 (116); `stage-check`, сдача и конец раунда их
  останавливают (`JudgedEnv.execute` 250–283).
- Ничего в воротах, трассе, застое, окне, голове этапа не менялось (диф: `loop.py` только Roots/clip/shell, `variant_b.py`
  только `$WORK`).

### 2.2. ebaed1715 (P01.310)
- **(2) составной stage-check → отказ**: `command_words` (`ebaed1715:agent_miniswe.py:143`), `loop_word_misuse` (181);
  `stage-check`/`bg-status` не одни в команде, `bg-run` не в начале — команда **не исполняется**, ответ с кодом 2 (324–327);
  счёт `loop_word_refusals`.
- **(3) остаток этапа в голове продолжения**: каждая проверка кладёт `remain` — mech (`mech_remain`, `ebaed1715:loop.py:2817`;
  2776), code (только **число** красных строк, 2751–2752), probe (только число, 2928–2929), norm (ID, 3106–3107), stage_tests
  (3164–3165), profile (ключ — цель — строка M, 3234–3238); `run_stage_gate` их сводит (4092–4098); `stage_rest` (4776) пишет
  `S["remain"]` (+ `build_regressed`, регресс), вызов 4682. Голова раунда: `rest_state`/`rest_block`/`rest_text`
  (`agent_miniswe.py:1126–1168`), блок вставляется после головы этапа и до отчёта (`stage_prompt` 1084–1098), до `REST_MAX = 16`
  пунктов на вид (1112). Включено по умолчанию в режиме `stage` (`rest_on` 1121–1123; выкл. — `miniswe_rest: false`).
- **(4) без повторного обзора при DESIGN**: `continues` (1139–1141) = есть остаток + `miniswe_plan_round` + `work/DESIGN.md`;
  тогда `CONTINUE_WORDS` (1113) и шаг 1 шаблона mini-SWE заменён (`CONTINUE_WORKFLOW` 1117, `round_config(cont=True)` 1171,
  1760). Это слова, не запрет: чтение не ограничивается.
- **(6) stuck.outcome**: каждый раунд пишет `work_tree` (`ebaed1715:loop.py:4701`); `stuck_files` (4746–4773) даёт `outcome`
  (`same_result_files_changed / _no_file_changes / _files_unknown`), `files`, `rounds_detail`; в `pp.stuck` (5605), `result.json`
  и строку notify (5653–5654, 5673–5674). **Правило застоя не изменено** (`mech_stall_update` тот же, `ebaed1715:variant_b.py:912`).
- **cited_missing**: нейтральная строка `CITED_MISSING` в голове этапа (`agent_miniswe.py:997`, 1005–1006).
- **Н1**: в generation_only предложение SYSTEM о раннере заменяется (`generation_words`, 519–543, вызов 507–508); без целей
  модуля в реестре M — без слов о профиле (`module_has_targets`).
- **stages.profile_complete_from**: `profile_from_index/violations` (`loop.py:3177–3191`), проверка на подготовке (2680–2682);
  с названного этапа `final = last or i >= k_from` (3209) — полная блокирующая проверка; строки называют строку и колонку формы
  реестра (`registry_form_where`, `ebaed1715:variant_b.py:567`; `profile_completeness` 807). **По умолчанию не задан → только
  последний этап, как было.**
- **Н1-доп. stages.mech.require_build / require_cmd**: `MECH_KEYS` расширен (`variant_b.py:186`), `mech_require` (265),
  `mech_require_script/summary` (271–335); `mech_require_gate` (`loop.py:2790`) после зелёной сборки модуля: один вызов на сборки,
  по вызову на команду, +1 к мере каждая (2777–2786). **Не заданы — ворота как прежде.**
- **Н3**: `trap 'rm -rf -- "$D"' EXIT` в командах code_checks, mutation_trace, mode_trace, profile_probe; `tests/_tmproot.py`.

### 2.3. Что НЕ изменено ни e62185f8b, ни ebaed1715
- **Исполнение сценариев/проб M во время генерации** — нет: `generation_plan` и запреты `GEN_FORBID_*` те же (единственная правка
  в `generation_plan` — проверка `profile_complete_from`, `ebaed1715:loop.py:2680`). Пробы профиля — те же (только `trap`).
- **Закрытие этапа по mech без пункта чек-листа** — логика `norm_trace_gate`/`stage_round` та же (добавлен только `remain`).
  `regress = []` в generation_only (`ebaed1715:loop.py:4611`), один этап за раунд (4643).
- **table_driven и склейка литералов** — `tools/codecheck/main.go` не менялся (`git diff --stat 6e1881e09 ebaed1715 -- tools/`
  трогает только head-capture и m-invariance); `stringLit` по-прежнему только `BasicLit`.
- **Окно/MAX_OUT/бюджет чтения**: `MAX_OUT = 12000`, `WINDOW_SHARE = 0.9`, `MAX_TOKENS = 32000` те же
  (`ebaed1715:loop.py:49,57`; `ebaed1715:agent_miniswe.py:1416`, `budget_check` 1444–1486). Квитанция P01.310: «Меры по окну
  (MAX_OUT, бюджет чтения) — не включены: сначала замер reads.py на следующем прогоне»; в INDEX.md — предложение (а) MAX_OUT
  12000→6000 для mini-SWE, (б) бюджет чтения раунда ~250 тыс. знаков без записи, «нужно слово». `read_budget` (доп. (90))
  есть только для инструментов собственного разговора цикла (`6e1881e09:loop.py:5214–5221`), не для bash mini-SWE.
- **Проверка карты файлов DESIGN.md против кода** — нет ни в одной ревизии (DESIGN только показывается и служит признаком
  `continues`).
- **Что тесты что-то проверяют** — трасса по-прежнему судит только «назван, исполнен, прошёл» (`norm_trace.py:7–8`, не менялся);
  мутации/режим — прежние опции задания. own tests mech — по-прежнему «хоть один тест в модуле» (`ebaed1715:variant_b.py:449`
  `mech_summary`, без изменений логики).
- **Полнота профиля с этапа** — ручка добавлена, но **по умолчанию выключена**.
- **Подключение пакета к демону** — ни одна проверка не смотрит, что пакеты реализации достижимы из `main` демона:
  `stage_tests` освобождает `package main` (`mutation_trace.py:365–366`), code-checks смотрят пакет, выбранный моделью в профиле,
  `requires_module` — использование модуля пакетом, проба профиля — только что `stand`-команда стартует и жива. Частично
  закрывается заданием через `require_build/require_cmd` (сборка бинаря и короткий вызов) — по умолчанию не заданы.
- **Каждый раунд = проверка этапа**: раунд, кончившийся окном, по-прежнему идёт в проверку и в счёт застоя (`chat` всегда
  `done`).
- **`stuck.mech: null` у этапов с `code:*`** — не исправлено: `run_stage_gate` по-прежнему не переносит `mech` при нескольких
  проверках (`ebaed1715:loop.py:4086–4103`), а `rnd["mech"]` берётся оттуда же (4700). `stuck_files` берёт меру из `gates`, так что
  `stuck.outcome` от этого не зависит.

---

## 3. Ручки задания (без правки кода), значения по умолчанию (по ebaed1715)

| Ключ задания | Что делает | По умолчанию | Ссылка |
|---|---|---|---|
| `stages.profile_complete_from: "<этап>"` | полная блокирующая полнота профиля с этого этапа | нет (только последний этап) | `ebaed1715:loop.py:3177–3209` |
| `stages.mech.require_build` (строка/список) | сборки, которые должны дать 0, +1 к мере каждая | нет | `ebaed1715:variant_b.py:186, 265`; `loop.py:2777` |
| `stages.mech.require_cmd` (строка/список) | команды после сборок, должны дать 0 | нет | там же |
| `stages.mech.require_own_tests` | own tests в mech | true | `variant_b.py` `generation_violations`, `mech_summary` |
| `stages.norm_trace`, `norm_trace_mutation`, `norm_trace_mode`, `stage_tests`, `profile_probe` | ворота поверх mech | выкл. (в попытке 8 все вкл.) | `6e1881e09:loop.py:2756, 2940, 3011`; `mutation_trace.py:133–138`; `mode_trace.py:183` |
| `miniswe_rest` | остаток этапа и слова продолжения | вкл. при `miniswe_head: stage` | `ebaed1715:agent_miniswe.py:1121–1123` |
| `miniswe_bg_jobs` | bg-run/bg-status (только b11) | выкл. | `e62185f8b:agent_miniswe.py:139–141` |
| `miniswe_bg_timeout` | таймаут фонового задания, с | 1800 (≤ предела b11) | `ebaed1715:agent_miniswe.py:225` |
| `miniswe_heredoc_lines` | порог заметки о длинном heredoc (0 — нет) | 300 | `ebaed1715:agent_miniswe.py:79, 1304` |
| `miniswe_plan_round` | раунд плана, DESIGN.md | выкл. | `6e1881e09:agent_miniswe.py:578` |
| `miniswe_plan_steps` | шагов раунда плана | 60 | `6e1881e09:agent_miniswe.py:434` |
| `miniswe_plan_idle_steps` | стоп раунда плана без изменений файлов плана (0 — выкл.) | 8 | `6e1881e09:agent_miniswe.py:430, 975–977` |
| `miniswe_design_max` | знаков DESIGN.md в голове | 32000 | `6e1881e09:agent_miniswe.py:428` |
| `miniswe_section_max` | байт блока нормы в голове (0 — без лимита) | 20000 | `6e1881e09:agent_miniswe.py:341, 350` |
| `miniswe_readme` | глобы README урока для головы первого этапа | `spec/*.README.md` | `6e1881e09:agent_miniswe.py:345, 355` |
| `miniswe_stable_prefix` | стабильный префикс головы | true | `6e1881e09:agent_miniswe.py:335` |
| `miniswe_steps` | лимит шагов этапного раунда | 80 (в попытке 8 — 60) | `6e1881e09:agent_miniswe.py:815` |
| `miniswe_checks` | `stage-check` за раунд | 6 | `6e1881e09:agent_miniswe.py:1136` |
| `miniswe_check_held` | `stage-check` перепроверяет и закрытые этапы | выкл. | `6e1881e09:agent_miniswe.py:1146` |
| `miniswe_round_max_input_tokens`, `miniswe_plan_round_max_input_tokens` | вход раунда | нет | `6e1881e09:agent_miniswe.py:1043–1044` |
| `max_tokens` | резерв ответа в оценке окна и `max_tokens` вызова | 32000 | `6e1881e09:agent_miniswe.py:993, 996` |
| `context_tokens` | окно модели | 200000 | `6e1881e09:loop.py:56, 2991` |
| `stall_rounds` | порог застоя | 3 (вариант B) | `6e1881e09:variant_b.py:40, 801` |
| `run_timeout` | таймаут одной команды модели, с | 600 | `ebaed1715:agent_miniswe.py:345` |
| `max_input_tokens`, `max_tokens_run`, `max_cached_run`, `max_active_hours` | бюджеты прогона | 150 млн / по бюджету / 200 млн / 24 ч | `variant_b.py:38–39`; `loop.py` `token_ceilings` |
| `_out_max` | предел вывода команды вместо `MAX_OUT` | 12000 | `6e1881e09:loop.py:539, 595` |

Замечания к таблице:
- `_out_max` — служебный ключ «вызывающего» (`PROFILES.md:918`), не описан как ключ задания, но `load_task` не фильтрует ключи
  (`6e1881e09:loop.py:125–150`), так что значение из JSON задания будет прочитано; с e62185f8b оно же подставляется в слова
  модели (`{out_max}`). Решения владельца на это нет (P01.310: «нужно слово»).
- Порог окна меняется только через `max_tokens`/`context_tokens` (`WINDOW_SHARE` — константа кода): стоп при
  `оценка входа + max_tokens ≥ 0,9 × context_tokens`.
- Бюджета чтения для раунда mini-SWE ручкой нет (нужна правка кода).
- Проверки склейки литералов, карты DESIGN, подключения пакетов к `main`, исполнения сценариев M в генерации — ручкой не
  включаются (нужна правка кода или данных M).
