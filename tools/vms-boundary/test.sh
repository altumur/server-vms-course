#!/bin/sh
# Проба границы VMS на временном репозитории: каждая закрытая группа путей отклоняется хуком, коммит белого списка с
# трейлером проходит, pre-push и проверка диапазона ловят обход --no-verify и правку Source/vms/.
#   tools/vms-boundary/test.sh
set -u
src=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git init -q --bare "$tmp/origin.git"
git init -q -b main "$tmp/work"
cd "$tmp/work" || exit 1
git config user.email t@example.invalid; git config user.name test
mkdir -p tools && cp -R "$src" tools/vms-boundary
for f in VMS/01-cam/cam.subsystem.yaml М10B_ServerVMS/01.md Platform/a.md skills/b.md decisions/README.md \
         decisions/inbox/2026-10-22-разбор.md Source/vms/x.py Source/w2cplatform/c.py CLAUDE.md СЕССИИ.md ХОД-Архитектор.md; do
  mkdir -p "$(dirname "$f")"; echo base > "$f"
done
git add -- . && git commit -q -m base && git remote add origin "$tmp/origin.git" && git push -q origin main
tools/vms-boundary/install.sh "Спецификация VMS" >/dev/null || { echo "FAIL install"; exit 1; }
fails=0
expect() {  # expect ok|refused <описание> <путь> [<сообщение>]
  want=$1 what=$2 path=$3 msg=${4:-"проба

Session: Спецификация VMS"}
  mkdir -p "$(dirname "$path")"; echo "$what $(date +%s%N)" >> "$path"
  git add -- "$path"
  if git commit -q -m "$msg" >/dev/null 2>"$tmp/err"; then got=ok; else got=refused; git reset -q; git checkout -q -- . 2>/dev/null; git clean -qfd >/dev/null; fi
  if [ "$got" = "$want" ]; then echo "ok    $want: $what"; else echo "FAIL  $what: ждали $want, получили $got"; cat "$tmp/err"; fails=$((fails+1)); fi
}
expect refused "ветка main, а не vms/<тема>" VMS/01-cam/cam.subsystem.yaml
git checkout -q -b vms/probe
for p in Platform/a.md skills/b.md decisions/README.md decisions/inbox/2026-10-22-разбор.md Source/vms/x.py \
         Source/w2cplatform/c.py CLAUDE.md СЕССИИ.md ХОД-Архитектор.md; do
  expect refused "закрытый путь $p" "$p"
done
expect refused "открытый путь без трейлера" VMS/01-cam/cam.subsystem.yaml "проба без трейлера"
expect refused "чужой трейлер" VMS/01-cam/cam.subsystem.yaml "проба

Session: Архитектор"
for p in VMS/01-cam/cam.subsystem.yaml М10B_ServerVMS/01.md ХОД-Спецификация-VMS.md \
         decisions/inbox/2026-10-23-запрос-vms-проба.md decisions/inbox/2026-10-23-решение-владельца-vms-проба.md; do
  expect ok "белый список $p" "$p"
done
if git push -q origin vms/probe 2>"$tmp/err"; then echo "ok    pre-push: чистый диапазон проходит"; else echo "FAIL  pre-push чистого диапазона"; cat "$tmp/err"; fails=$((fails+1)); fi
echo bypass >> Platform/a.md; git add -- Platform/a.md
git commit -q --no-verify -m "обход

Session: Спецификация VMS"
if git push -q origin vms/probe 2>"$tmp/err"; then echo "FAIL  pre-push пропустил обход --no-verify"; fails=$((fails+1)); else echo "ok    pre-push: обход --no-verify в Platform/ отклонён"; fi
git reset -q --hard HEAD~1
git checkout -q main
echo edit >> Source/vms/x.py; git add -- Source/vms/x.py
git -c core.hooksPath=/dev/null commit -q -m "правка свидетеля не сессией VMS"
if python3 tools/vms-boundary/check.py range origin/main..HEAD 2>"$tmp/err"; then echo "FAIL  диапазон пропустил правку Source/vms/"; fails=$((fails+1)); else echo "ok    диапазон: правка Source/vms/ кем угодно отклонена"; fi
[ $fails -eq 0 ] && echo "PASS vms-boundary" || { echo "FAIL vms-boundary: $fails"; exit 1; }
