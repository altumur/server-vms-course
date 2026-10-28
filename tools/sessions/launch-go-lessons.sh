#!/bin/bash
# launch-go-lessons.sh [NN…] — окна сессий уроков Go (ADR-0083 доп. (54)): Codex без песочницы, промпт prompts/go-lesson.tpl.
# Без аргументов — все 01–10. Окно урока, уже записанное в реестре, сначала закрыть (или перезапустить relaunch-codex.sh).
set -e; T=$(cd "$(dirname "$0")" && pwd); D=/Users/murat/w2c/cammeta-c-go-lesson/.prompts; mkdir -p "$D"
L="01 01-store
02 02-installer
03 03-worker
04 04-controller
05 05-resource
06 06-console
07 07-console-module
08 08-domain
09 09-agent
10 10-domain-console"
want=${*:-01 02 03 04 05 06 07 08 09 10}
echo "$L" | while read n l; do
  case " $want " in *" $n "*) ;; *) continue;; esac
  "$T/render.sh" "$T/prompts/go-lesson.tpl" NN=$n LESSON=$l > "$D/$n.md"
  "$T/launch-codex.sh" c-go-$n "c-go $n ($l, Codex)" /Users/murat/w2c/cammeta-c-go /Users/murat/w2c/cammeta-c-go-lesson "$D/$n.md"
done
