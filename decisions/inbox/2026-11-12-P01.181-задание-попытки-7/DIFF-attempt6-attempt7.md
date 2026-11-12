# Дифф: задание попытки 6 (P01.156) → задание попытки 7 (P01.181)

Слева `decisions/inbox/2026-11-11-P01.156-задание/task-attempt6.json` (sha256 `569d79a1…`), справа `task-attempt7.json` этого каталога (sha256 `8116f57a…`). Задание попытки 7 — черновик P01.247 (`task-attempt7.draft.json`, sha256 `300e47d3…`) с хешами пары P01.180, вписанными `fill_pair.py`. Других байтов против черновика нет.

| ключ | попытка 6 | попытка 7 | основание |
|---|---|---|---|
| `name` | `p01-b-raft-bf8462085c08` | `p01-b-raft-be48405e645b` | пара P01.180 |
| `specs` | `/srv/b11-isolation/model-specs/bf8462085c08…/tree` | `/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/tree` | пара P01.180 |
| `specs_sha` | `bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae` | `be48405e645b49985d35efc42b6d61c2f304c4d8` | пара P01.180 |
| `seed_files.SPEC_VERSION` | `bf846208…\n` | `be48405e645b49985d35efc42b6d61c2f304c4d8\n` | пара P01.180 |
| `miniswe_steps` | нет (в цикле 80) | `60` | ADR-0133 доп. (73) п. 1 |
| `miniswe_round_max_input_tokens` | нет | `6000000` | доп. (73) п. 1 |
| `miniswe_plan_round` | нет (выкл.) | `true` | доп. (68), P01.174 |
| `miniswe_plan_steps` | нет | `30` | доп. (73) п. 2; верхний предел, план кончается по окну около 20-го вызова (P01.238, note Архитектора) |
| `miniswe_plan_round_max_input_tokens` | нет | `6000000` | доп. (73) п. 2, P01.238 |
| `miniswe_stable_prefix` | нет (выкл.) | `true` | доп. (68), P01.202 |
| `context_tokens` | нет (в цикле 200000) | `200000` | доп. (73) п. 3: окно модели — параметр задания; доля 90 % — постоянная цикла `WINDOW_SHARE` |
| `stages.norm_trace_mutation` | нет | `true` | доп. (68), P01.179 |
| `stages.norm_trace_mode` | нет | `true` | доп. (68), P01.216; метки способа проверки читает цикл P01.248 |
| `stages.stage_tests` | нет | `true` | доп. (68), P01.179 |
| `stages.m_passport.path` | `…/model-specs/bf846208…/PASSPORT-M.json` | `/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/PASSPORT-M.json` | пара P01.180; тот же путь ставит `delivery/setup.sh` P01.180 |
| `stages.m_passport.sha256` | `ccd61598be4d50b3ed4ddc35088b458c10a34a3ba66d0be612b0d43de27a5ec2` | `0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01` | паспорт M пары P01.180 |

Без изменений: `prompt` побайтно (`PROMPT-attempt7.txt` = `PROMPT-attempt6.txt` P01.156), `variant`, `generation_only` true, `module`, `lesson`, `agent`, `model`, `env_file`, `allow`, `head_files` (14 файлов, все есть в M `be48405e`), `miniswe_head`, `miniswe_focus`, `miniswe_group`, `miniswe_stage_check`, `miniswe_checks`, бюджет и правила окончания (`max_input_tokens`, `max_tokens_run`, `max_tokens_stage` по 150 млн, вход с кэшем; `max_active_hours` 24; `stall_rounds` 3), `stages.form`, `stages.list` (11 этапов, как в `forms/stages.tsv` M), `stages.agent_exec`, `stages.mech`, `stages.norm_trace` true, `stages.profile_probe` true.

Ключей суда и J нет: по доп. (69) вердиктов движка в генерации нет, суд — после генерации (P01.185).

Не заданы ключом, действуют по коду цикла: `max_tokens` (32000, доп. (73) п. 3), `miniswe_design_max` (DESIGN.md, P01.174), разбор heredoc (P01.240), ворота профиля P01.194, P01.199, P01.225 (внутри `stages.profile_probe`; входы и значения только из M — доп. (74), (75)), cached по `round_usage` в паспорте (P01.202), ошибки записи траекторий (P01.213).

## Построчный дифф

```diff
--- "2026-11-11-P01.156-\320\267\320\260\320\264\320\260\320\275\320\270\320\265/task-attempt6.json"	2026-11-12 00:31:14.474959621 +0000
+++ "2026-11-12-P01.181-\320\267\320\260\320\264\320\260\320\275\320\270\320\265-\320\277\320\276\320\277\321\213\321\202\320\272\320\270-7/task-attempt7.json"	2026-11-12 00:32:10.976595487 +0000
@@ -1,5 +1,5 @@
 {
-  "name": "p01-b-raft-bf8462085c08",
+  "name": "p01-b-raft-be48405e645b",
   "variant": "B",
   "generation_only": true,
   "module": "Platform",
@@ -11,10 +11,10 @@
     "env GOPROXY=off GOSUMDB=off GOTOOLCHAIN=local GOWORK=off GOENV=off (GOFLAGS=-mod=mod )?go (build|vet|test|mod tidy|mod init [A-Za-z0-9./_-]+)( [^;&|`$<>]*)?",
     "gofmt -(l|w|d) [^;&|`$<>]+"
   ],
-  "specs": "/srv/b11-isolation/model-specs/bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae/tree",
-  "specs_sha": "bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae",
+  "specs": "/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/tree",
+  "specs_sha": "be48405e645b49985d35efc42b6d61c2f304c4d8",
   "seed_files": {
-    "SPEC_VERSION": "bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae\n"
+    "SPEC_VERSION": "be48405e645b49985d35efc42b6d61c2f304c4d8\n"
   },
   "head_files": [
     "Platform/01-store/README.md",
@@ -38,6 +38,13 @@
   "miniswe_group": 6,
   "miniswe_stage_check": true,
   "miniswe_checks": 6,
+  "miniswe_steps": 60,
+  "miniswe_round_max_input_tokens": 6000000,
+  "miniswe_plan_round": true,
+  "miniswe_plan_steps": 30,
+  "miniswe_plan_round_max_input_tokens": 6000000,
+  "miniswe_stable_prefix": true,
+  "context_tokens": 200000,
   "max_input_tokens": 150000000,
   "max_active_hours": 24,
   "max_tokens_run": 150000000,
@@ -86,9 +93,12 @@
       "require_own_tests": true
     },
     "norm_trace": true,
+    "norm_trace_mutation": true,
+    "norm_trace_mode": true,
+    "stage_tests": true,
     "m_passport": {
-      "path": "/srv/b11-isolation/model-specs/bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae/PASSPORT-M.json",
-      "sha256": "ccd61598be4d50b3ed4ddc35088b458c10a34a3ba66d0be612b0d43de27a5ec2"
+      "path": "/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/PASSPORT-M.json",
+      "sha256": "0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01"
     },
     "profile_probe": true
   }
```
