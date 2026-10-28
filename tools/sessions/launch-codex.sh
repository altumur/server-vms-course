#!/bin/bash
# launch-codex.sh <имя в реестре> <заголовок окна> <worktree Orca> <cwd> <файл промпта>
# Новое окно Codex без песочницы (решение владельца 2026-10-28 «полный доступ», ADR-0083 доп. (54), правка):
# в -s workspace-write песочница держит .git только для чтения и закрывает очередь проверок.
set -e; n=$1; title=$2; wt=$3; cwd=$4; p=$5
cmd="cd $cwd && codex -s danger-full-access -a never -c check_for_update_on_startup=false -c model_reasoning_effort=medium \"\$(cat $p)\""
h=$(orca terminal create --worktree path:$wt --title "$title" --json --command "$cmd" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["terminal"]["handle"])')
"$(dirname "$0")/registry.sh" set "$n" "$h"; echo "$n $h"
