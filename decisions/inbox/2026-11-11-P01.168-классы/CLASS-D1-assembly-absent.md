# D1 — в корне реализации нет `assembly.yaml`: зачётный прогон без вердикта

**Случаев:** 12 запусков зачёта (12 целей кандидата `902ce3f6`), ни одного отчёта. Диагностика P01.188 добавила минимальную `assembly.yaml` (`format: 1`, `modules: 01-store: 01-store/acceptance.yaml`) и дала отчёты всех 12 целей. Остальные классы разбора строятся по ней.

## Наблюдение движка
`/home/pilot/owner-receipts/P01.188-court-claude-20261111/out/claude/<цель>/engine.log` у всех 12 целей:
`judge: run: assembly: stat /srv/calib-p0180/p0188/cand/claude/work/assembly.yaml: no such file or directory`, код выхода 1, `engine.json` нет (`summary-official.txt`: `no_report`).

Код движка `ef7dcf9` — `engine/cmd/judge/main.go:137–139`: `os.Stat(*assembly)`, при ошибке — `run: assembly: …`, отказ всего запуска до сборки. Повтора не нужно: причина видна в журнале.

## Норма
M `bf846208` = J-вход `49e62279` по этим файлам байт в байт (`Platform/common/acceptance/PROFILE.md`, `README.md`):
- PROFILE.md:7 — «The profile is `acceptance.yaml`, with integer `format: 2`. The composition is `assembly.yaml`, with integer `format: 1`.»
- PROFILE.md:11 — «The assembly maps module identities to profile files. The implementation repository has a root `SPEC_VERSION`…»
- PROFILE.md:13 — «A format error of a profile or of the assembly … refuses the whole run before any build or target starts: the run reports the error, and no target has a result.»
- PROFILE.md:160–166 («Assembly and input identity») — поля `format`, `modules`; «The default directory selector uses `assembly.yaml`».
- README общей приёмки:44 — «**Composition of the stand.** The root `assembly.yaml` (`format: 1`, `modules`) is only the map «module → profile file»…»; README:12 — пример полной сборки.

Ни одна фраза не говорит прямо, что **реализация кладёт** `assembly.yaml` в свой корень. Слово «root» в README:44 и «implementation repository has a root `SPEC_VERSION`» в PROFILE.md:11 стоят рядом, но обязанность реализации названа только для `SPEC_VERSION`.

Отказ движка без отчёта верен по PROFILE.md:13: нет сборки — нет результата ни у одной цели.

## Код кандидата
`cand-diag/claude/work` без добавленной диагностикой `assembly.yaml` равен архиву `902ce3f6` за вычетом `bin/` (84 файла; сверено по `candidate.files.sha256` P01.166). Профиль `01-store/acceptance.yaml` есть и полон: `format: 2`, `build`, `unit`, `stand`, `keys`, `adapters`, `vectors`, `artifacts`, `code`. Сборки нет.

## Что видела модель
- **Задание.** `TASK.md` контроля (`CTL-isolation-20261111/src/TASK.md`, sha256 `9290f9b5…`) об `assembly.yaml` молчит: «It is the implementation root and already holds SPEC_VERSION; the lesson module is the directory 01-store in it.» Задание цикла (`PROMPT-attempt6.txt`) — тоже.
- **SYSTEM нашего цикла** (`/srv/minimax-loop/runs/p01-b-raft-bf8462085c08/miniswe/round-003.json`, цикл `561ea2c`): «The runner starts acceptance by the profile: work/ is the implementation root (SPEC_VERSION, assembly.yaml), and the lesson module has its own directory with acceptance.yaml (format: 2). … without these files acceptance does not start.» У модели в Claude Code этой фразы не было.
- **M.** PROFILE.md модель прочла целиком: вызов 25 (`cat PROFILE.md | head -c 32000`, вывод сохранён в файл) и вызов 26 (`Read` того же вывода, строки 1–169, включая §«Assembly and input identity»). Строку README:44 она видела в выдаче `grep` (вызов 29).
- В `PLAN.md`, `NOTES.md`, `GUESSES.md`, `ARCHITECTURE.md` и `RETRO-ANSWER.md` слова `assembly` нет. Догадки нет.
- Ворот не было: Claude Code не исполнял ни профиль, ни движок. Модель закончила сама при 40,2 млн из 150 млн и 0,79 ч из 24.

## Мнение
Исход — **кандидат**: сборки нет, зачёт без вердикта.

Причина по доп. (41), (42), (44):
- главная — **обвязка/задание** (по note Архитектора 12:53:31Z). Наш цикл называет `assembly.yaml` в SYSTEM, задание контроля — нет. Сравнивать генерации по этому классу нельзя.
- вторая — **норма**. Обязанность реализации класть `assembly.yaml` в M прямо не записана (выше). Пункт «норма однозначна» доп. (44) п. 1.1 не выполнен, поэтому метки «модель» нет. Текст при этом модели был виден целиком.

Предложение:
- **норма** — в PROFILE.md §«Files and scalar syntax», рядом с `SPEC_VERSION` (стр. 11), одна фраза: «The implementation repository root also holds `assembly.yaml` that names the profile of each module it implements; the judge reads it by that name.»
- **задание контролей** — та же строка, что в SYSTEM цикла, чтобы условия трёх генераций совпадали.

## Вопросы ревьюеру
1. Достаточно ли README:44 («The root `assembly.yaml`») и PROFILE.md:166 («The default directory selector uses `assembly.yaml`»), чтобы считать обязанность реализации однозначной? Тогда вторая причина — модель (без обратной связи), а не норма.
2. Верно ли, что отказ без отчёта по PROFILE.md:13 относится и к **отсутствию** файла сборки, а не только к ошибке его формы? Или по PROFILE.md:162 («absence of a part required by a selected target blocks that target») каждая цель должна быть `blocked` с отчётом?
