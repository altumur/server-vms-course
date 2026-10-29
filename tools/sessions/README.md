# tools/sessions — запуск, адреса и статус сессий

Ведёт «Архитектор». Здесь всё, что нужно, чтобы завести, перезапустить или найти сессию, не вспоминая прошлые разговоры.
Состав и роли — `СЕССИИ.md` §2, машины и доступы — `ИНФРАСТРУКТУРА.md`, решения — ADR-0083 доп. (50)–(57).

## Адреса: реестр сессий

`/Users/murat/w2c/cammeta-status/sessions.tsv` — имя, handle окна Orca, модель, каталог, роль, `session_id` Codex.
Реестр вне курса: линии Go и Python курс не читают, а адреса нужны и им. Имя окна меняется при каждом перезапуске —
скрипты ниже переписывают строку сами; руками — `registry.sh set <имя> <handle> [session_id]`.

```sh
tools/sessions/registry.sh list            # кто есть
tools/sessions/registry.sh get runner      # handle для orca terminal send
```

## Статус: строка остановки

Сессия, которой нечего делать, кончает ход строкой `СТОП: <почему> | ЖДУ: <чего> от <кого>` последней в окне
(ADR-0083 доп. (57); правило — в `CLAUDE.md` курса, `AGENTS.md`/`CLAUDE.md` каждого репозитория и в шаблонах
`prompts/`). Файлов статуса нет (уточнение 2026-10-29): «Сторож» читает окна — занято или стоит, строка `СТОП:` с
экрана; строки нет на экране — сессия работает. Сводка — `/Users/murat/w2c/cammeta-status/windows.json`, `status.sh`. Простой по журналам сессий за час —
`idle_claude.py <журналы Claude>` и `idle_codex.py` (время без хода; причину даёт строка остановки). Отчёт владельцу (ведёт «Сторож», раз в 5 минут) — локальная
страница `file:///Users/murat/w2c/cammeta-watch/report.html` (страница claude.ai не используется).

## Запуск и перезапуск

| Скрипт | Что делает |
|---|---|
| `launch-go-lessons.sh [NN…]` | окна сессий уроков Go по `prompts/go-lesson.tpl` |
| `launch-acc.sh [slug…]` | окна сессий приёмки по `prompts/acc-stand.tpl` |
| `launch-py-lessons.sh NN:LESSON:PROCESS…` | окна сессий уроков Python В7 по шаблону ведущей `cammeta-c-python-v7/tools/sessions/python-lesson.tpl`, волнами по 3–4 |
| `launch-codex.sh <имя> <заголовок> <worktree> <cwd> <промпт>` | одно окно Codex |
| `relaunch-codex.sh <имя> <session_id> <заголовок> <worktree> <cwd> [текст]` | закрыть окно и продолжить тот же разговор Codex |
| `render.sh <шаблон> КЛЮЧ=значение…` | шаблон → промпт; `{{имя}}` — handle из реестра |
| `broadcast.sh <файл> [имя…]` | одно сообщение всем или названным сессиям |

Правила, выученные на ошибках 2026-10-28:

- **Codex — только `-s danger-full-access -a never`** (решение владельца «полный доступ»). В `-s workspace-write`
  песочница держит `.git` только для чтения даже внутри `writable_roots` и закрывает очередь проверок
  `cammeta-checks/spool`: сессия не может ни коммитить, ни ставить проверки. `/permissions` в работающей сессии
  помогает не всегда; надёжно — `relaunch-codex.sh` (тот же разговор через `codex resume`).
- **Перезапуск — только в простое:** нет строки `esc to interrupt` на экране и нет исполнителя
  (`pgrep -f '^claude -p'` с `CLAUDE_CONFIG_DIR` урока). Занятость не узнать по одному слову `Working`: у Codex бывают
  `Waiting for background terminal`, `Compacting context`, `Messages to be submitted`.
- **Не слать клавиши в занятое окно:** меню `/permissions`, открытое посреди хода, висит в окне и путает сессию.
- **`-c check_for_update_on_startup=false`** — иначе вопрос об обновлении съедает первый промпт.
- Исполнитель MiniMax — `claude -p` с `CLAUDE_CONFIG_DIR=/Users/murat/w2c/minimax-c-go-NN-config` и ключом из
  `/Users/murat/w2c/assist-pilot/.env` (не печатать); один на урок одновременно.

## Шаблоны `prompts/`

`go-lesson.tpl` (NN, LESSON), `acc-stand.tpl` (SLUG, GROUP, SCOPE), `c-python-v7.md`, `fuzz.md`. В каждом — «Кому
писать» (маршруты доп. (55)–(57)) и строка остановки. Ведущие (`{{c-go}}`, `{{runner}}`, `{{spec}}` …) подставляются
из реестра при `render.sh`.
