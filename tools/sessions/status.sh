#!/bin/bash
# status.sh — строки остановки сессий (ADR-0083 доп. (57)): /private/tmp/cammeta-status/*.txt, свежие сверху
cd /private/tmp/cammeta-status 2>/dev/null || exit 0
for f in $(ls -t *.txt 2>/dev/null); do printf '%-16s %s\n' "${f%.txt}" "$(tail -1 "$f" | cut -c1-160)"; done
