# Пересборка задания попытки 7 — P01.251

Задание получено неизменённым `fill_pair.py` P01.247. Против P01.181 изменены ровно шесть полей привязки к M и паспорту.

| поле | P01.181 | P01.251 |
|---|---|---|
| `/name` | `p01-b-raft-be48405e645b` | `p01-b-raft-da04d237b656` |
| `/specs` | `/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/tree` | `/srv/b11-isolation/model-specs/da04d237b656aafc8b30fb382c44406a80642cac/tree` |
| `/specs_sha` | `be48405e645b49985d35efc42b6d61c2f304c4d8` | `da04d237b656aafc8b30fb382c44406a80642cac` |
| `/seed_files/SPEC_VERSION` | `be48405e645b49985d35efc42b6d61c2f304c4d8\n` | `da04d237b656aafc8b30fb382c44406a80642cac\n` |
| `/stages/m_passport/path` | `/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/PASSPORT-M.json` | `/srv/b11-isolation/model-specs/da04d237b656aafc8b30fb382c44406a80642cac/PASSPORT-M.json` |
| `/stages/m_passport/sha256` | `0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01` | `9dd0c3c1655664b2a704f77c497f7e46a6a268394ec3707a5ffe843462c4de0b` |

`prompt` побайтно равен P01.181 и P01.156. Бюджет 150 млн / 24 ч, параметры раундов, 11 этапов, `code:*`, трассировка, `profile_probe`, окружение запуска, модель и правила окончания прежние. В задание контроля Opus вписан только новый SPEC_VERSION; ключей J и суда нет.

Дифф с попыткой 6 и основания параметров — [таблица P01.181](../2026-11-12-P01.181-задание-попытки-7/DIFF-attempt6-attempt7.md); значения M и паспорта в ней заменены этой сдачей. Машинная сверка всех полей — `/home/pilot/run-p01251-task-20261112/TASK-CHECK.json`.

```diff
--- P01.181/task-attempt7.json
+++ P01.251/task-attempt7.json
@@ -1,5 +1,5 @@
 {
-  "name": "p01-b-raft-be48405e645b",
+  "name": "p01-b-raft-da04d237b656",
   "variant": "B",
   "generation_only": true,
   "module": "Platform",
@@ -11,10 +11,10 @@
     "env GOPROXY=off GOSUMDB=off GOTOOLCHAIN=local GOWORK=off GOENV=off (GOFLAGS=-mod=mod )?go (build|vet|test|mod tidy|mod init [A-Za-z0-9./_-]+)( [^;&|`$<>]*)?",
     "gofmt -(l|w|d) [^;&|`$<>]+"
   ],
-  "specs": "/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/tree",
-  "specs_sha": "be48405e645b49985d35efc42b6d61c2f304c4d8",
+  "specs": "/srv/b11-isolation/model-specs/da04d237b656aafc8b30fb382c44406a80642cac/tree",
+  "specs_sha": "da04d237b656aafc8b30fb382c44406a80642cac",
   "seed_files": {
-    "SPEC_VERSION": "be48405e645b49985d35efc42b6d61c2f304c4d8\n"
+    "SPEC_VERSION": "da04d237b656aafc8b30fb382c44406a80642cac\n"
   },
   "head_files": [
     "Platform/01-store/README.md",
@@ -97,8 +97,8 @@
     "norm_trace_mode": true,
     "stage_tests": true,
     "m_passport": {
-      "path": "/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/PASSPORT-M.json",
-      "sha256": "0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01"
+      "path": "/srv/b11-isolation/model-specs/da04d237b656aafc8b30fb382c44406a80642cac/PASSPORT-M.json",
+      "sha256": "9dd0c3c1655664b2a704f77c497f7e46a6a268394ec3707a5ffe843462c4de0b"
     },
     "profile_probe": true
   }
```
