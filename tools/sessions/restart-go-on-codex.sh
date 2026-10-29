#!/bin/bash
# restart-go-on-codex.sh [имя…] — перевести сессии линии Go с Kimi на Codex (слово владельца 2026-10-29: «все сессии c-go —
# только Codex»; прежние окна Kimi остановлены лимитом 429 и HANDOFF не писали). Закрывает окно по реестру, открывает Codex
# в том же дереве (launch-codex.sh) с прежним поручением и вводной «продолжай с дерева». Исполнитель кода — MiniMax, как было.
# Без аргументов — все: c-go-exec, c-go-08, срезы 08, c-go-09, срезы 09.
set -e; T=$(cd "$(dirname "$0")" && pwd); P=/Users/murat/w2c/cammeta-status/prompts; D=$P/codex; mkdir -p "$D"
E=/Users/murat/w2c/cammeta-c-go-exec; L=/Users/murat/w2c/cammeta-c-go-lesson
all="c-go-exec c-go-08 c-go-08-people c-go-08-members c-go-08-tokens c-go-08-passes c-go-08-shared c-go-09 c-go-09-alarms c-go-09-cli"
pre() { cat <<EOF
**Перезапуск на Codex** (слово владельца 2026-10-29: все сессии линии Go — только Codex; прежняя сессия $1 на Kimi
остановлена лимитом 429 «5-hour usage limit» и HANDOFF не писала). Первым делом — \`git status\`, \`git diff\` и последние
коммиты своего дерева: незакоммиченное там — работа прежней сессии, продолжай с неё, без причины не отбрасывай. Файлов
слотов MiniMax прежней сессии нет (сняты). Затем одна строка ведущей c-go (адрес — реестр
\`/Users/murat/w2c/cammeta-status/sessions.tsv\`): «$1 → ведущая: перезапущен на Codex, вижу <состояние>». Ниже — прежнее
поручение; где оно называет Kimi — читай Codex, адреса окон — только из реестра.

EOF
}
for n in ${*:-$all}; do
  case $n in
    c-go-exec) cwd=$E; src=$P/c-go-exec-kimi.md;;
    c-go-08|c-go-09) nn=${n#c-go-}; cwd=$L/$nn; src=$L/.prompts/$nn-kimi.md;;
    c-go-0?-*) s=${n#c-go-}; cwd=$E/$s; src=$P/$n.md;;
    *) echo "unknown $n" >&2; exit 2;;
  esac
  [ -f "$src" ] || { echo "no prompt $src" >&2; exit 2; }
  p=$D/$n.md; { pre "$n"; sed -e 's/сессия Kimi + MiniMax/сессия Codex + MiniMax/g' -e 's/Kimi + MiniMax/Codex + MiniMax/g' "$src"; } > "$p"
  old=$("$T/registry.sh" get "$n" 2>/dev/null || true)
  [ -n "$old" ] && [ "$old" != "-" ] && orca terminal close --terminal "$old" >/dev/null 2>&1 || true
  "$T/launch-codex.sh" "$n" "$n (Codex)" /Users/murat/w2c/cammeta-c-go "$cwd" "$p"
done
