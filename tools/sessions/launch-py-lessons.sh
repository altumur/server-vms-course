#!/bin/bash
# launch-py-lessons.sh NN:LESSON:PROCESS … — окна сессий уроков Python В7 (ADR-0083 правка доп. (52), (54) от 2026-10-29):
# Codex без песочницы в дереве урока /Users/murat/w2c/cammeta-c-python-v7-lesson/NN, промпт — шаблон ведущей
# /Users/murat/w2c/cammeta-c-python-v7/tools/sessions/python-lesson.tpl с подстановками @NN@ @LESSON@ @PROCESS@ @SESSION@;
# имя в реестре — c-python-v7-NN. Волнами по 3–4 урока. Пример: launch-py-lessons.sh 01:01-store:store 02:02-installer:installer
set -e
tpl=/Users/murat/w2c/cammeta-c-python-v7/tools/sessions/python-lesson.tpl
out=/Users/murat/w2c/cammeta-status/prompts; mkdir -p "$out"
for spec in "$@"; do
  IFS=: read -r nn lesson proc <<<"$spec"
  name=c-python-v7-$nn; dir=/Users/murat/w2c/cammeta-c-python-v7-lesson/$nn; p=$out/$name.md
  [ -d "$dir" ] || { echo "нет дерева $dir"; exit 1; }
  sed -e "s/@NN@/$nn/g" -e "s/@LESSON@/$lesson/g" -e "s/@PROCESS@/$proc/g" -e "s/@SESSION@/$name/g" "$tpl" > "$p"
  cmd="cd $dir && codex -s danger-full-access -a never -c check_for_update_on_startup=false -c model_reasoning_effort=medium \"\$(cat $p)\""
  h=$(orca terminal create --worktree path:/Users/murat/w2c/cammeta-c-python-v7 --title "Python урок $nn ($lesson)" --json --command "$cmd" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["terminal"]["handle"])')
  if grep -q "^$name	" /Users/murat/w2c/cammeta-status/sessions.tsv; then
    "$(dirname "$0")/registry.sh" set "$name" "$h"
  else
    printf '%s\t%s\tCodex+MiniMax\t%s\tсессия урока Python %s (%s)\t\n' "$name" "$h" "$dir" "$nn" "$lesson" >> /Users/murat/w2c/cammeta-status/sessions.tsv
  fi
  echo "$name $h"
done
