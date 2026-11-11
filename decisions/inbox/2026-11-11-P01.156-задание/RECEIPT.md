# P01.156 — задание попытки 6 (окно run, Claude, 2026-11-11)

Задача P01.156, ADR-0133 шаг 28, доп. (46), (47). Образец — задание попытки 5 P01.122 (`task-attempt5.json`, sha256 `a8c06a11…`, `/home/pilot/src103-claude-p0122-task-20261110`). Пара — P02.26: M `bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae`, паспорт M `ccd61598…`.

## Файлы этого каталога

| файл | sha256 | что это |
|---|---|---|
| `task-attempt6.json` | `569d79a1506c87e8bb6c2dc9b1e2251b6955e841e6aea31f4ca2cba954cf94e8` | задание попытки 6 |
| `DIFF-attempt5-attempt6.txt` | `2a6d853d3549c199…` | дифф с заданием попытки 5 |
| `PROMPT-attempt6.txt` | `b8b41c2b8b056cba…` | поле `prompt` задания без изменений, отдельным файлом для контроля P01.162 (и для Opus в Claude Code, доп. (53)) |
| `prep_dryrun.py`, `PREP-DRYRUN.out` | — | проверка подготовки цикла вне стенда |

## Что изменено против попытки 5

Задание собрано из `task-attempt5.json` в том же формате (JSON, отступ 2, LF в конце). Изменено шесть мест:

- `name`: `p01-b-raft-d5bd29ddb2dd` → `p01-b-raft-bf8462085c08`;
- `specs`, `specs_sha`, `seed_files.SPEC_VERSION`: M `d5bd29dd…` → `bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae`;
- `stages.m_passport` (новый ключ, P01.131.1): `{"path": "/srv/b11-isolation/model-specs/bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae/PASSPORT-M.json", "sha256": "ccd61598be4d50b3ed4ddc35088b458c10a34a3ba66d0be612b0d43de27a5ec2"}`. Путь — место паспорта по сценарию доставки P02.26 (`delivery/setup.sh`, как P01.131.2), sha256 — паспорт пары P02.26;
- `stages.profile_probe: true` (новый ключ, P01.153, 8f3b714; ответ Архитектора 1 в P01.157).

Без изменений:

- `prompt` побайтно, с прежними строками «The P/01 group is built in the variant keys.store_build: raft…» и «A run with -group-size 3 must bring up the group…»;
- бюджет и правила окончания: `max_input_tokens`, `max_tokens_run`, `max_tokens_stage` по 150 млн, `max_active_hours` 24, `stall_rounds` 3;
- `stages.norm_trace: true`, `stages.list` (11 этапов), `agent_exec`, `mech`, `head_files` (все 14 есть в M bf846208), `allow`, `miniswe_*`, модель `MiniMax-M3.1-Flash-Preview`, `env_file`.
- Ворота `code:*` отдельным ключом не включаются, как в попытке 5: цикл берёт их из ячеек `code:*` в `stages.tsv` M.

## Проверка подготовки вне стенда

Код цикла: en-generic `561ea2c05a46` (свежий клон `/home/pilot/git/minimax-loop.git`; в нём P01.131.1, P01.150, P02.39, P01.153). M: дерево коммита bf846208 из `M.git` пары P02.26, 769 файлов. Паспорт: копия `passport/PASSPORT-M-bf8462085c08.json` того же sha256 `ccd61598…`, путь в проверке подменён на копию. Вывод — `PREP-DRYRUN.out`, код выхода 0.

- `stage_prep` (generation_plan, проверки кода, norm_trace, profile_probe): 11 этапов. `mech` и `code` у model, launch, jcs, store_core, http, rights_eval, daemon_copy, durable, group. Только `mech` у rights и daemon_doors. `PrepError` нет.
- norm_trace: 55 пунктов. По этапам: model 1, store_core 11, http 8, rights_eval 1, rights 8, daemon_doors 1, daemon_copy 3, durable 6, group 16 — так же, как на M попытки 5.
- group в `when_unevaluated`: сборку задаёт задание, этап включён.
- `profile_probe_cfg` задания — включено.
- `variant_b.prep_violations` с `stages.m_passport`: 0 нарушений; `m_passport_violations` — пусто.
- Контроли: неверный sha256 паспорта и чужая M (d5bd29dd) дают нарушения.

## Пределы и замечания

- Сам стенд не проверен. Цикл на стенде, M bf846208 в `model-specs`, паспорт рядом с ней и строка trial-views — это P01.157 представителя. Если паспорт ляжет по другому пути, нужно поправить `stages.m_passport.path`; sha256 менять не нужно.
- `env_file` остаётся `/srv/minimax-loop/minimax.env`, как в попытке 5. При обходе P01.123 подтверждено, что служба второго дерева его читает. Для P01.157 это нужно подтвердить снова.
- Задание в дерево цикла я не устанавливал: это делает представитель в P01.157. Путь задания для обвязки Kimi Code (P01.162) называет представитель. Текст задания — `PROMPT-attempt6.txt`, побайтно поле `prompt`.
- Попутно найдено в цикле (не правил): проверка `stages.profile_probe not in (None, True, False)` пропускает `1` и `0`, потому что в Python `1 == True`. Затем `profile_probe_cfg` (`is True`) молча выключает ворота. В этом задании стоит литерал `true`, так что его это не касается. Для цикла это совет: проверять `isinstance(v, bool)`.

Доказательства: этот каталог; рабочие копии — `/home/pilot/run-p01156-task-20261111`.
