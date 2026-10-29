#!/bin/bash
# status.sh — статус сессий с окон (ADR-0083 доп. (57), (58), уточнение 2026-10-29): сводка «Сторожа» windows.json
python3 - <<'PY'
import json
try: d=json.load(open('/Users/murat/w2c/cammeta-status/windows.json'))
except Exception as e: print('windows.json не читается:', e); raise SystemExit
rows=d.get('windows', d) if isinstance(d, dict) else d
for r in (rows.values() if isinstance(rows, dict) else rows):
    if isinstance(r, dict): print(f"{str(r.get('name','?')):16} {str(r.get('state','?')):10} {str(r.get('line',''))[:140]}")
PY
