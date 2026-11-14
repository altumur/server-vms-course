"""Write an exact source-text change journal from the two immutable M rosters."""
from pathlib import Path
import hashlib
import html
import json
import subprocess
import sys
B,D=map(lambda p:Path(p).resolve(),sys.argv[1:3])
I=json.loads((B/'IDENTITIES.json').read_text())
A=json.loads((B/'CHANGED-NORMS-DETAILS.json').read_text())
delta=json.loads((B/'DELTA-PAIR.json').read_text())['baselines']['M8″']
def cell(v):
 return html.escape(v or '—',quote=False).replace('|','&#124;').replace('\n','<br>')
lines=['# Изменения M8″ → M13','',
 'Исходный вход M8″: `d378d59f11beeced0198ec53398c800a428d5ba6`, C: `0fbe6e55ceb0b07e4a70727e813934a2f06edb1b`. '+f"Новый вход M13: `{I['M']}`, C: `{I['C']}`.",'',
 'Журнал описывает только разницу входов. Полный M13 задаёт действующие правила. Пути начинаются от `Platform/`. Таблицы ниже дословно сопоставляют английский источник до и после; символ — означает отсутствие абзаца или пункта. Неизменённый текст внутри изменённого абзаца сохранён, чтобы условия не теряли контекст. Соседние надгробия id и горизонтальные разделители не входят в тело абзаца; их изменения остаются в полном патче.','',
 'Для урока 1 существенны: строгая форма JSON файла прав и копии; подтверждённый набор при непустой копии; отказ открытия при доказанной порче середины журнала; границы fsync, повторного recover и удаления прежнего raft; наблюдаемые условия часов и производственных целей. Общие JCS и права перенесены в common; M включает обязательные общие модули и точные зависимости. Внешние договоры других уроков сравниваются на тех же основаниях, что и собственные нормы.','',
 '## M8″ → M13','',
 '| R-id | Файл | Было в M8″ | Стало в M13 |','|---|---|---|---|']
for req,row in A['paragraphs'].items():
 lines.append(f"| {req} | {row['path'].removeprefix('Platform/')} | {cell(row['before'])} | {cell(row['after'])} |")
lines+=['','Изменения пунктов перечней:','','| Пункт | Файл | Было в M8″ | Стало в M13 |','|---|---|---|---|']
for req,row in A['checks'].items():
 lines.append(f"| {req} | {row['path'].removeprefix('Platform/')} | {cell(row['before'])} | {cell(row['after'])} |")
lines+=['','Все изменённые файлы M, включая текст без собственного R-id:','','| Файл | Изменение | Строк добавлено | Строк удалено |','|---|---|---:|---:|']
changes={r['path']:r for r in delta['views']['M']['paths'] if r['path']!='Platform/COURSE_COMMIT'}
assert changes.keys()==A['files'].keys()
for path,r in changes.items():lines.append(f"| {path.removeprefix('Platform/')} | {r['action']} | {r['lines_added']} | {r['lines_deleted']} |")
lines+=['','[CHANGED-M.patch](CHANGED-M.patch) даёт точную полную разницу всех 59 исходных файлов M, в том числе указателей, форм, зависимостей, производственных обязательств и переноса двух README в common. Маркер транспорта в журнал норм не входит. Патч содержит только M и не раскрывает ожидаемые ответы судьи.','',
 '## Изменённые источники J-входа','',
 'Таблица даёт адреса и вид изменения без раскрытия ожидаемых ответов. Полный J-вход хранится отдельно.','','| Путь | Изменение | Строк добавлено | Строк удалено |','|---|---|---:|---:|']
for row in delta['views']['J-input']['paths']:
 if row['path']=='Platform/COURSE_COMMIT':continue
 lines.append(f"| `{row['path'].removeprefix('Platform/')}` | {row['action']} | {row['lines_added']} | {row['lines_deleted']} |")
lines+=['','Процедуры квалификации, таблицы сценариев, фикстуры и результаты проверок не задают новых обязательств M. Журнал сравнивает источники входов; он не заменяет полный новый вход.','']
(D/'CHANGED-NORMS.md').write_text('\n'.join(lines))
raw=subprocess.check_output(['git','--git-dir',str(B/'delta.git'),'diff','--no-ext-diff','--no-renames', 'd378d59f11beeced0198ec53398c800a428d5ba6',I['M'],'--',*sorted(changes)])
(D/'CHANGED-M.patch').write_bytes(raw)
print(json.dumps({'paragraphs':len(A['paragraphs']),'checklist':len(A['checks']),'M_files':len(changes),'patch_sha256':hashlib.sha256(raw).hexdigest()}))
