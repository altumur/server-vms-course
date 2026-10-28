#!/bin/bash
# launch-acc.sh [slug…] — окна сессий приёмки (ADR-0083 доп. (54)): Codex без песочницы, задачи ставит раннер.
set -e; T=$(cd "$(dirname "$0")" && pwd); B=/Users/murat/w2c/cammeta-acceptance-stands; D=$B/.prompts; mkdir -p "$D"
L='vectors|векторы|пакеты векторов всех уроков (единая команда vectors, family-read, yaml-suite, canonical, корпус P/02.1)
stand-0102|стенд 01–02|процессные цели уроков 01 и 02 (хранилище, установщик) на их стенде
stand-0106|стенд 01–06 и 07|процессные цели уроков 03–06 на общем стенде 01–06 и модуль 07 байтами
stand-domain|стенд домена 08–10|процессные цели уроков 08–10 и P/06.7 на стенде домена'
want=${*:-vectors stand-0102 stand-0106 stand-domain}
echo "$L" | while IFS='|' read slug group scope; do
  case " $want " in *" $slug "*) ;; *) continue;; esac
  mkdir -p "$B/$slug"; "$T/render.sh" "$T/prompts/acc-stand.tpl" SLUG=$slug GROUP="$group" SCOPE="$scope" > "$D/$slug.md"
  "$T/launch-codex.sh" acc-$slug "acc $slug (Codex)" /Users/murat/w2c/cammeta-acceptance $B "$D/$slug.md"
done
