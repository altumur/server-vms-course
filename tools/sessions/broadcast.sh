#!/bin/bash
# broadcast.sh <файл текста> [имя…] — одно сообщение сессиям из реестра (все — без имён); {{name}} в тексте — имя получателя.
T=$(cd "$(dirname "$0")" && pwd); F=${CAMMETA_SESSIONS:-/Users/murat/w2c/cammeta-status/sessions.tsv}; txt=$(cat "$1"); shift
names=${*:-$(cut -f1 "$F" | grep -v -e '^architect$' -e '^fuzz$')}
for n in $names; do h=$("$T/registry.sh" get "$n"); [ -n "$h" ] || { echo "нет $n"; continue; }
  orca terminal send --terminal "$h" --enter --text "${txt//\{\{name\}\}/$n}" >/dev/null 2>&1 && echo "ok $n" || echo "FAIL $n"; done
