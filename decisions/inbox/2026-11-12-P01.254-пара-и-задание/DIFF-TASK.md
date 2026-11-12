# P01.254 — привязка задания попытки 7

`fill_pair.py` P01.247 изменил шесть полей привязки пары. Затем по note Архитектора
добавлены `miniswe_design_max: 32000` и `miniswe_plan_idle_steps: 3`: P01.260 принята до среза.
Против P01.251 и P01.181 изменены ровно восемь полей; все остальные значения JSON совпадают.

| Основа | Поле | До | После |
|---|---|---|---|
| P01.251 | `/miniswe_design_max` | `null` | `32000` |
| P01.251 | `/miniswe_plan_idle_steps` | `null` | `3` |
| P01.251 | `/name` | `"p01-b-raft-da04d237b656"` | `"p01-b-raft-847ac9d1fb36"` |
| P01.251 | `/seed_files/SPEC_VERSION` | `"da04d237b656aafc8b30fb382c44406a80642cac\n"` | `"847ac9d1fb36bd1153450f99ddc4805c2609877e\n"` |
| P01.251 | `/specs` | `"/srv/b11-isolation/model-specs/da04d237b656aafc8b30fb382c44406a80642cac/tree"` | `"/srv/b11-isolation/model-specs/847ac9d1fb36bd1153450f99ddc4805c2609877e/tree"` |
| P01.251 | `/specs_sha` | `"da04d237b656aafc8b30fb382c44406a80642cac"` | `"847ac9d1fb36bd1153450f99ddc4805c2609877e"` |
| P01.251 | `/stages/m_passport/path` | `"/srv/b11-isolation/model-specs/da04d237b656aafc8b30fb382c44406a80642cac/PASSPORT-M.json"` | `"/srv/b11-isolation/model-specs/847ac9d1fb36bd1153450f99ddc4805c2609877e/PASSPORT-M.json"` |
| P01.251 | `/stages/m_passport/sha256` | `"9dd0c3c1655664b2a704f77c497f7e46a6a268394ec3707a5ffe843462c4de0b"` | `"6bd5488d483ac38d848cbe21eed7099b91729dec3efa2234b766bd872cf96c8f"` |
| P01.181 | `/miniswe_design_max` | `null` | `32000` |
| P01.181 | `/miniswe_plan_idle_steps` | `null` | `3` |
| P01.181 | `/name` | `"p01-b-raft-be48405e645b"` | `"p01-b-raft-847ac9d1fb36"` |
| P01.181 | `/seed_files/SPEC_VERSION` | `"be48405e645b49985d35efc42b6d61c2f304c4d8\n"` | `"847ac9d1fb36bd1153450f99ddc4805c2609877e\n"` |
| P01.181 | `/specs` | `"/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/tree"` | `"/srv/b11-isolation/model-specs/847ac9d1fb36bd1153450f99ddc4805c2609877e/tree"` |
| P01.181 | `/specs_sha` | `"be48405e645b49985d35efc42b6d61c2f304c4d8"` | `"847ac9d1fb36bd1153450f99ddc4805c2609877e"` |
| P01.181 | `/stages/m_passport/path` | `"/srv/b11-isolation/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8/PASSPORT-M.json"` | `"/srv/b11-isolation/model-specs/847ac9d1fb36bd1153450f99ddc4805c2609877e/PASSPORT-M.json"` |
| P01.181 | `/stages/m_passport/sha256` | `"0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01"` | `"6bd5488d483ac38d848cbe21eed7099b91729dec3efa2234b766bd872cf96c8f"` |

`PROMPT-attempt7.txt` побайтно прежний. CONTROL: новый SPEC_VERSION и исполнение ADR-0133 доп. (76):
сняты команда `check` и обратная связь ворот; контроль Opus получает M и задание, пишет свои проверки сам.
Список файлов теперь назван чтением из M, без обещания вставить все тексты в начальный запрос.
Бюджет 150 млн входа с кэшем / 24 часа, 11 этапов, правила окончания и прежние пределы раундов сохранены.
J и суд в задание генерации не входят. Данные для нового движка — J-вход пары этой задачи.

Дифф с попыткой 6 и основания параметров —
[таблица P01.181](../2026-11-12-P01.181-задание-попытки-7/DIFF-attempt6-attempt7.md).

Полная машинная сверка полей — `/home/pilot/run-p01254-task-20261112/TASK-CHECK.json`.

Контроль Opus уже запущен с `/home/pilot/owner-receipts/P01.184-control-task-20261112/TASK.md`
(sha256 `48a875d15732f3c9988ce6f30f166d998e1cc36e5356c5a42e6c9e97c737a44c`). Этот CONTROL — только сверка по note от 12:31:53Z;
[diff](CONTROL-LAUNCHED.diff) содержит различия формулировок, условия и M совпадают.
