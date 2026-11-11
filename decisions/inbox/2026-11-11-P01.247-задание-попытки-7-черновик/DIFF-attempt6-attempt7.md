# Дифф: задание попытки 6 (P01.156) → черновик задания попытки 7 (P01.247)

Слева `decisions/inbox/2026-11-11-P01.156-задание/task-attempt6.json` (sha256 `569d79a1…`), справа `task-attempt7.draft.json` этого каталога. Метки `<PAIR_*>` заполняет `fill_pair.py`, когда выйдет пара P01.180.

| ключ | попытка 6 | попытка 7, черновик | основание |
|---|---|---|---|
| `name` | `p01-b-raft-bf8462085c08` | `p01-b-raft-<PAIR_M_SHA12>` | новая пара P01.180 |
| `specs` | `…/model-specs/bf846208…/tree` | `…/model-specs/<PAIR_M_SHA>/tree` | новая пара |
| `specs_sha` | `bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae` | `<PAIR_M_SHA>` | новая пара |
| `seed_files.SPEC_VERSION` | `bf846208…\n` | `<PAIR_M_SHA>\n` | новая пара |
| `miniswe_steps` | нет (в цикле 80) | `60` | ADR-0133 доп. (73) п. 1 |
| `miniswe_round_max_input_tokens` | нет | `6000000` | доп. (73) п. 1, P01.223 |
| `miniswe_plan_round` | нет (выкл.) | `true` | доп. (68) п. 1, P01.174 |
| `miniswe_plan_steps` | нет | `30` | доп. (73) п. 2; на деле план кончается по окну около 20-го вызова (P01.238) |
| `miniswe_plan_round_max_input_tokens` | нет | `6000000` | доп. (73) п. 2, P01.238 |
| `miniswe_stable_prefix` | нет (выкл.) | `true` | доп. (68) п. 1, P01.202 |
| `context_tokens` | нет (в цикле 200000) | `200000` | доп. (73) п. 3, P01.238: окно модели — параметр задания; доля 90 % — постоянная цикла `WINDOW_SHARE` |
| `stages.norm_trace_mutation` | нет | `true` | доп. (60) п. 1, (68), P01.179 |
| `stages.norm_trace_mode` | нет | `true` | P01.216; метки способа проверки P01.176 и P01.228 — см. условие в `RECEIPT.md` |
| `stages.stage_tests` | нет | `true` | доп. (60) п. 1, (68), P01.179 |
| `stages.m_passport.path` | `…/model-specs/bf846208…/PASSPORT-M.json` | `…/model-specs/<PAIR_M_SHA>/PASSPORT-M.json` | новая пара |
| `stages.m_passport.sha256` | `ccd61598…` | `<PAIR_M_PASSPORT_SHA256>` | паспорт M новой пары |

Без изменений: `prompt` побайтно (`PROMPT-attempt7.txt` = `PROMPT-attempt6.txt`), `variant`, `generation_only`, `module`, `lesson`, `agent`, `model`, `env_file`, `allow`, `head_files` (14 файлов, все есть в нынешнем `main`), `miniswe_head`, `miniswe_focus`, `miniswe_group`, `miniswe_stage_check`, `miniswe_checks`, бюджет и правила окончания (`max_input_tokens`, `max_tokens_run`, `max_tokens_stage` по 150 млн, `max_active_hours` 24, `stall_rounds` 3), `stages.form`, `stages.list` (11 этапов), `stages.agent_exec`, `stages.mech`, `stages.norm_trace`, `stages.profile_probe`.

Не заданы ключом, действуют по коду цикла: `max_tokens` (32000, не снижать — доп. (73) п. 3), `miniswe_design_max` (24000 знаков DESIGN.md, P01.174), разбор heredoc (P01.240), ворота профиля P01.194, P01.199, P01.225 (внутри `stages.profile_probe`; входы и значения только из M — доп. (74), (75)).

## Построчный дифф

```diff
--- "2026-11-11-P01.156-\320\267\320\260\320\264\320\260\320\275\320\270\320\265/task-attempt6.json"	2026-11-11 22:27:04.436816100 +0000
+++ "2026-11-11-P01.247-\320\267\320\260\320\264\320\260\320\275\320\270\320\265-\320\277\320\276\320\277\321\213\321\202\320\272\320\270-7-\321\207\320\265\321\200\320\275\320\276\320\262\320\270\320\272/task-attempt7.draft.json"	2026-11-11 22:29:53.748024164 +0000
@@ -1,5 +1,5 @@
 {
-  "name": "p01-b-raft-bf8462085c08",
+  "name": "p01-b-raft-<PAIR_M_SHA12>",
   "variant": "B",
   "generation_only": true,
   "module": "Platform",
@@ -11,10 +11,10 @@
     "env GOPROXY=off GOSUMDB=off GOTOOLCHAIN=local GOWORK=off GOENV=off (GOFLAGS=-mod=mod )?go (build|vet|test|mod tidy|mod init [A-Za-z0-9./_-]+)( [^;&|`$<>]*)?",
     "gofmt -(l|w|d) [^;&|`$<>]+"
   ],
-  "specs": "/srv/b11-isolation/model-specs/bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae/tree",
-  "specs_sha": "bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae",
+  "specs": "/srv/b11-isolation/model-specs/<PAIR_M_SHA>/tree",
+  "specs_sha": "<PAIR_M_SHA>",
   "seed_files": {
-    "SPEC_VERSION": "bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae\n"
+    "SPEC_VERSION": "<PAIR_M_SHA>\n"
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
+      "path": "/srv/b11-isolation/model-specs/<PAIR_M_SHA>/PASSPORT-M.json",
+      "sha256": "<PAIR_M_PASSPORT_SHA256>"
     },
     "profile_probe": true
   }
```
