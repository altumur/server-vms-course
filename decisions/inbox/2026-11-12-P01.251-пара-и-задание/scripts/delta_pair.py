"""P01.251: exact per-path differences from P01.180 for M, J and J-input, with grouped counts and critical rows.
Uses only Git roster/mode/blob/size metadata, plus the one /v1/copy row explicitly required by the task.
"""
from pathlib import Path
import subprocess,json,collections
B=Path(__file__).resolve().parent.parent;C=(B/'C.txt').read_text().strip();P=B/('pair-'+C[:12]);OP=Path('/home/pilot/run-p01180-pair-20261112');D=Path('/home/pilot/wt-task-P01.251/decisions/inbox/2026-11-12-P01.251-пара-и-задание')
def g(d,*a):return subprocess.check_output(['git','--git-dir',str(d),*a])
def tree(d,c):
 r={}
 for e in g(d,'ls-tree','-r','-l','-z',c).split(b'\0'):
  if e:
   meta,path=e.split(b'\t',1);mode,kind,blob,size=meta.decode().split();r[path.decode()]={'mode':mode,'type':kind,'blob':blob,'bytes':int(size)}
 return r
V={'M':(OP/'pair-41a9493fb08c/M.git','be48405e645b49985d35efc42b6d61c2f304c4d8',P/'M.git','da04d237b656aafc8b30fb382c44406a80642cac'),'J':(OP/'pair-41a9493fb08c/J.git','605f12bb9b4664e5e7e9517722fcf5464faf219b',P/'J.git','f0855df6131ee0eda2bf1e4c93ef4ca8ca5f961c'),'J-input':(OP/'ji-41a9493fb0/JI.git','9daca227dbc08ce3d4a14c6d47c6ea3f94e55034',B/('ji-'+C[:12])/'JI.git','c0f91c726a635db26f4d22449b93731813042251')}
res={'from_C':'41a9493fb08c293a570c006019995a64a599f68b','to_C':C,'views':{}}
rows=[]
for name,(od,oc,nd,nc) in V.items():
 a,b=tree(od,oc),tree(nd,nc);changes=[];groups=collections.defaultdict(lambda:collections.Counter({'add':0,'modify':0,'delete':0}))
 for p in sorted(set(a)|set(b)):
  if a.get(p)==b.get(p):continue
  action='add' if p not in a else ('delete' if p not in b else 'modify');group=p.split('/')[1] if p!='Platform/COURSE_COMMIT' else 'COURSE_COMMIT'
  groups[group][action]+=1;changes.append({'path':p,'action':action,'before':a.get(p),'after':b.get(p)})
 counts=collections.Counter(x['action'] for x in changes);r={'before':{'commit':oc,'files':len(a),'bytes':sum(x['bytes'] for x in a.values())},'after':{'commit':nc,'files':len(b),'bytes':sum(x['bytes'] for x in b.values())},'counts':{k:counts[k] for k in ['add','modify','delete']},'groups':dict(sorted(groups.items())),'paths':changes};res['views'][name]=r
 for group,cs in sorted(groups.items()):rows.append(f"| {name} | {group} | {cs['add']} | {cs['modify']} | {cs['delete']} |")
headpath='Platform/01-store/forms/process-1.3.scenarios.tsv'
def headrow(gd,c):return next(x for x in g(gd,'show',c+':'+headpath).decode().splitlines() if x.startswith('32-copy-raw\t5\t'))
od,oc,nd,nc=V['J'];before,after=headrow(od,oc),headrow(nd,nc);assert before.endswith('200 @empty') and after.endswith('405 @empty @header Allow: =GET')
res['HEAD_copy_row']={'path':headpath,'before':before,'after':after,'M_absent':headpath not in tree(V['M'][2],V['M'][3])}
assert res['HEAD_copy_row']['M_absent']
form='Platform/common/acceptance/forms/stand-environment.tsv'
res['stand_environment']={n:{'before':form in tree(v[0],v[1]),'after':form in tree(v[2],v[3])} for n,v in V.items()}
assert all(not x['before'] and x['after'] for x in res['stand_environment'].values())
for n,r in res['views'].items():assert r['counts']['delete']==0
(B/'DELTA-PAIR.json').write_text(json.dumps(res,ensure_ascii=False,indent=1)+'\n')
lines=['# P01.251 — дельта пары против P01.180','',f"Исходный C: `41a9493fb08c293a570c006019995a64a599f68b`. Новый C: `{C}`. Сравнены полный путь, режим, тип объекта и blob каждого файла; байтовые размеры приведены для оценки объёма чтения. Полная опись всех изменений — `/home/pilot/run-p01251-pair-20261112-r2/DELTA-PAIR.json`.",'','| Выгрузка | Файлов до → после | Добавлено | Изменено | Удалено | Байтов до → после |','|---|---:|---:|---:|---:|---:|']
for n,r in res['views'].items():lines.append(f"| {n} | {r['before']['files']} → {r['after']['files']} | {r['counts']['add']} | {r['counts']['modify']} | {r['counts']['delete']} | {r['before']['bytes']} → {r['after']['bytes']} |")
lines+=['','## Изменения по участкам','','Строка `COURSE_COMMIT` — смена маркера C в каждой выгрузке. Числа включают её отдельно.','','| Выгрузка | Участок Platform | Добавлено | Изменено | Удалено |','|---|---|---:|---:|---:|',*rows,'','## Изменения, названные в задании','','| Файл/место | M | J | J-вход | Содержание |','|---|---|---|---|---|',f'| `common/acceptance/forms/stand-environment.tsv` | добавлен | добавлен | добавлен | 45 имён, значения и области процессов из P01.250 |',f'| `01-store/forms/process-1.3.scenarios.tsv`, `32-copy-raw`, шаг 5 | отсутствует | изменён | изменён | `admin HEAD /v1/copy`: `200 @empty` → `405 @empty @header Allow: =GET` (P01.249) |',f'| `common/acceptance/forms/stand-environment.tsv.schema.json` | отсутствует | добавлен | отсутствует | схема формы, `judge_only` / `exclude` |',f'| `05-resource/forms/decision-order.tsv` | добавлен | добавлен | отсутствует | форма P05.7, классифицирована P05.9 как `model_and_judge` / `exclude` |',f'| `05-resource/forms/decision-order.tsv.schema.json` | отсутствует | добавлен | отсутствует | схема P05.7, классифицирована P05.9 как `judge_only` / `exclude` |','','## Остальная дельта main','','C включает принятые изменения P02/P03/P04/P05 и OBSH.45, а также снятие `See also` в P/01 (24182a5c4). Поэтому дельта шире ожидавшихся формы окружения и строки HEAD. Изменения общих фильтров — ровно четыре добавленные записи (P01.250 и P05.9), снятых и переклассифицированных записей нет; списки уроков 01–03 неизменны. Полная дельта фильтров — `FILTER-DELTA.json`; обзоры каждой добавки — `FILTER-REVIEWS.json`.','','J содержит все файлы Platform C побайтно и добавленный маркер `Platform/COURSE_COMMIT`. M и J-вход — подмножества по фильтрам; ручного вырезания файлов не было. Названные изменения других уроков входят в действующий main и не правились этой задачей.']
D.mkdir(exist_ok=True);(D/'DELTA-PAIR.md').write_text('\n'.join(lines)+'\n');print(json.dumps({n:r['counts'] for n,r in res['views'].items()},ensure_ascii=False,indent=1))
