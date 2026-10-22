#!/bin/sh
# Поставить хуки границы VMS в это рабочее дерево (ADR-0090 доп. (1)): core.hooksPath и vms.session — в config.worktree.
#   tools/vms-boundary/install.sh "Спецификация VMS"
set -eu
[ $# -eq 1 ] || { echo "usage: $0 <сессия из tools/vms-boundary/sessions.txt>" >&2; exit 2; }
top=$(git rev-parse --show-toplevel)
grep -qxF "$1" "$top/tools/vms-boundary/sessions.txt" || { echo "vms-boundary: $1 нет в sessions.txt" >&2; exit 2; }
git config extensions.worktreeConfig true
git config --worktree core.hooksPath "$top/tools/vms-boundary/hooks"
git config --worktree vms.session "$1"
echo "vms-boundary: хуки поставлены в $top для «$1»"
