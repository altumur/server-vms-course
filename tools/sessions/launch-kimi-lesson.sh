#!/bin/bash
# launch-kimi-lesson.sh <NN> <LESSON> — урок Go на сессии Kimi вместо Codex (ADR-0083 правка доп. (54) от 2026-10-29):
# закрыть прежнее окно урока, открыть `kimi --auto` в дереве урока и отдать промпт prompts/go-lesson-kimi.tpl
# (сессия начинает с HANDOFF.md урока). Пример: launch-kimi-lesson.sh 09 09-agent
set -e; T=$(cd "$(dirname "$0")" && pwd); n=$1; l=$2; name=c-go-$n
D=/Users/murat/w2c/cammeta-c-go-lesson/.prompts; mkdir -p "$D"; p="$D/$n-kimi.md"
"$T/render.sh" "$T/prompts/go-lesson-kimi.tpl" NN=$n LESSON=$l > "$p"
old=$("$T/registry.sh" get "$name"); [ -n "$old" ] && [ "$old" != "-" ] && orca terminal close --terminal "$old" >/dev/null 2>&1 || true
dir=/Users/murat/w2c/cammeta-c-go-lesson/$n
h=$(orca terminal create --worktree path:/Users/murat/w2c/cammeta-c-go --title "c-go $n ($l, Kimi)" --json --command "cd $dir && kimi --auto" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["terminal"]["handle"])')
"$T/registry.sh" set "$name" "$h"
for i in $(seq 1 30); do orca terminal read --terminal "$h" 2>/dev/null | grep -q "No session yet\|Kimi Code" && break; sleep 2; done
sleep 3; orca terminal send --terminal "$h" --text "Прочти и выполни поручение: $p" >/dev/null; sleep 1
orca terminal send --terminal "$h" --text "" --enter >/dev/null   # Kimi: текст и Enter — раздельно
echo "$name $h"
