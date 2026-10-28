#!/bin/bash
# Реестр сессий: /Users/murat/w2c/cammeta-status/sessions.tsv — имя<TAB>handle<TAB>модель<TAB>каталог<TAB>роль<TAB>session_id
#   registry.sh get <имя>            — handle
#   registry.sh set <имя> <handle> [session_id]
#   registry.sh list
F=${CAMMETA_SESSIONS:-/Users/murat/w2c/cammeta-status/sessions.tsv}
case "$1" in
  get)  awk -F'\t' -v n="$2" '$1==n{print $2}' "$F";;
  set)  python3 - "$F" "$2" "$3" "${4:-}" <<'P'
import sys
f,n,h,sid=sys.argv[1:5]; rows=[l.rstrip('\n').split('\t') for l in open(f)]
for r in rows:
    if r[0]==n:
        r[1]=h
        if sid: r[5:6]=[sid] if len(r)>5 else r.extend(['']*(5-len(r))) or [sid]
open(f,'w').write(''.join('\t'.join(r)+'\n' for r in rows))
P
  ;;
  list) column -t -s $'\t' "$F";;
  *) echo "usage: registry.sh get|set|list" >&2; exit 2;;
esac
