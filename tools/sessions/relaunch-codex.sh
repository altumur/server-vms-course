#!/bin/bash
# relaunch-codex.sh <имя в реестре> <session_id Codex> <заголовок> <worktree Orca> <cwd> [текст первого хода]
# Закрыть окно и продолжить ТОТ ЖЕ разговор без песочницы. Только когда у сессии нет исполнителя
# (`pgrep -f '^claude -p'` + CLAUDE_CONFIG_DIR урока) и строки «esc to interrupt» на экране.
set -e; n=$1; sid=$2; title=$3; wt=$4; cwd=$5
msg=${6:-"Перезапуск окна «Архитектором»: сессия без песочницы. Продолжай с места остановки; несостоявшиеся git и check.py повтори."}
old=$("$(dirname "$0")/registry.sh" get "$n"); [ -n "$old" ] && orca terminal close --terminal "$old" >/dev/null 2>&1 || true; sleep 2
cmd="cd $cwd && codex resume $sid -s danger-full-access -a never -c check_for_update_on_startup=false -c model_reasoning_effort=medium \"$msg\""
h=$(orca terminal create --worktree path:$wt --title "$title" --json --command "$cmd" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["terminal"]["handle"])')
"$(dirname "$0")/registry.sh" set "$n" "$h" "$sid"; echo "$n $h (было $old)"
