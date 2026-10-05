#!/bin/sh
# Тесты консоли курса — модуля платформы (w2cplatform/console.js), платформенной страницы и страницы VMS (vms/shell.html) —
# в jsdom: поддельный API, без сервера и браузера. Падением считаем и ошибку выполнения, и строку FAILED.
# Один раз перед первым запуском: npm install (здесь, в tests/console; node_modules в git не идёт). tests/run.py гоняет их сам.
cd "$(dirname "$0")"
[ -d node_modules/jsdom ] || { echo "нет jsdom: выполните npm install в $(pwd)"; exit 2; }
ok=1
for t in *.test.js; do
  out=$(node "$t" 2>&1) || { printf "%-24s КРАХ\n" "$t"; echo "$out" | head -4; ok=0; continue; }
  if echo "$out" | grep -q "^FAILED"; then
    printf "%-24s %s\n" "$t" "$(echo "$out" | grep '^FAILED')"; ok=0
  else printf "%-24s ok\n" "$t"; fi
done
[ $ok -eq 1 ] && echo "— все тесты консоли прошли" || { echo "— есть незакрытые проверки"; exit 1; }
