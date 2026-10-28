#!/bin/bash
# render.sh <шаблон> [КЛЮЧ=значение…] — {{имя}} → handle из реестра, КЛЮЧ → значение (NN, LESSON, SLUG, GROUP, SCOPE)
t=$1; shift; s=$(cat "$t")
for kv in "$@"; do k=${kv%%=*}; v=${kv#*=}; s=${s//$k/$v}; done
while [[ $s =~ \{\{([a-z0-9-]+)\}\} ]]; do n=${BASH_REMATCH[1]}; h=$("$(dirname "$0")/registry.sh" get "$n"); s=${s//\{\{$n\}\}/${h:-<нет в реестре: $n>}}; done
printf '%s\n' "$s"
