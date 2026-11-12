"""Write the P01.251 pair-only report and preserve its reproducible scripts in the task's inbox."""
from pathlib import Path
import hashlib,json,shutil
B=Path(__file__).resolve().parent.parent
D=Path('/home/pilot/wt-task-P01.251/decisions/inbox/2026-11-12-P01.251-пара-и-задание');(D/'scripts').mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ops={p.name:sha(p) for p in (B/'operator').glob('*.py')};(B/'OPERATOR-HASHES.json').write_text(json.dumps(ops,indent=1)+'\n')
old=Path('/home/pilot/run-p01180-pair-20261112/operator')
unchanged={n:sha(old/n)==sha(B/'operator'/n) for n in ['b7_export_pair.py','judge_input_export.py','m_passport.py','check_m_passport.py']};assert all(unchanged.values());(B/'OPERATOR-UNCHANGED.json').write_text(json.dumps(unchanged,indent=1)+'\n')
r=json.loads((B/'VERIFY.json').read_text());mp=B/'passport/PASSPORT-M-da04d237b656.json';jp=B/'ji-2d101991ac6e/PASSPORT-JI.json'
report=f'''# P01.251 — результат пересреза пары

Точный исходный C — `2d101991ac6eb656421f6e86a1ce742af994363d` (main после P01.249, P01.250, P05.9 и 24182a5c4). Доказательства: `{B}`. Старый отказ на двух непокрытых файлах P05.7 сохранён в `/home/pilot/run-p01251-pair-20261112`.

## Идентичности

| Объект | Значение |
|---|---|
| M | `da04d237b656aafc8b30fb382c44406a80642cac`, 788 файлов |
| J | `f0855df6131ee0eda2bf1e4c93ef4ca8ca5f961c`, 3562 файла |
| Каталог пары | `{B}/pair-2d101991ac6e/{{M.git,J.git}}` |
| M filter | blob `288dbeccdde4e40967fbba2bc794919ed159b370`, `pair-2d101991ac6e/FILTER-M.json` |
| Паспорт M | `{mp}`; sha256 `{sha(mp)}` |
| J-вход | `c0f91c726a635db26f4d22449b93731813042251`, 2118 файлов; `{B}/ji-2d101991ac6e/JI.git` |
| Паспорт J-входа | `{jp}`; sha256 `{sha(jp)}` |
| J-input filter | blob `8e6d572fe37041b96031257fed1e2acf67565759`, `ji-2d101991ac6e/FILTER-JI.json` |

## Проверки

`CHECK-SPEC-C.run.json`: `/home/pilot/venv-spec/bin/python -B skills/lesson-spec/scripts/check_spec.py --scope platform` на архиве точного C — код 0, PASS, `export_unlisted=0`, по 3562 записи фильтров. `PREFLIGHT.json`: classification, case_boundary и lexical_guard — pass, 157 таблиц случаев снято из M.

Операторы пары и J-входа — принятые P02.52, паспорт и его проверка — P01.131. Их байты равны использованным в P01.180 (`OPERATOR-UNCHANGED.json`); 51 тест операторов — OK (`OPERATOR-TESTS.out`). Пара выпущена одним вызовом, код 0 (`RUN.json`).

`VERIFY-ALL.json` — PASS с исполняемыми assert. J равна Platform C плюс маркер; сборные фильтры сверены с `export_lists` check_spec; фильтр J даёт ровно M. `M-SUBSET-J.json`: 788/788, режимы и blob совпадают. В M нет таблиц случаев wire, сценариев, ru, файлов PAC и объектов только для J. Общий blob по разным путям остался один, как в P01.180.

У M/J единственная ссылка и один коммит без родителей; физические объекты равны достижимым ({r['M_objects']} / {r['J_objects']}); `fsck --full --strict` — код 0. Лишних hooks/info/logs/файлов нет.

`passport/CONTROLS.json`: M как есть — код 0; каждый отдельный отрицательный контроль — код 1: J с паспортом M, подмена байтов, пропажа файла, символическая ссылка, дополнительный файл только из J, дерево прежней M P01.180, прежний SHA M при новом дереве. Фикстуры и выводы сохранены в `passport/controls/`.

J-вход равен всем `include` сборного фильтра побайтно, без лишних путей. Реестры целей и маршрутов уроков 01–03 на месте; `forms/export.json` уроков, фильтр, корпуса вердиктов и мутанты не попали. Единственный коммит без родителей, единственная ссылка `refs/heads/judge-input`, `fsck` чистый, физические объекты равны достижимым.

`VERIFY-JI-raw.json` по прежним широким правилам даёт красный, как P01.180: четыре `.js`-фикстуры testsub2 внутри acceptance inputs и `acceptance/1/verdicts.tsv`. `VERIFY-JI.json` объясняет каждый hit по принятым правилам P02.45; других hits нет. 158 файлов каталогов целей отсутствуют по фильтру: 140 — корпус вердиктов, 17 — схемы check_spec OBSH.39/P01.228, один — список export.json урока. Итог классифицированной проверки — OK.

## Происхождение фильтров и разрешения

От P01.180 унаследованы принятые источники фильтров, операторы и матрица прежних обзоров. Новая семантическая дельта фильтров — ровно четыре добавленные записи, без снятий и переклассификации; списки уроков 01–03 неизменны. P01.250: автор Claude (Anthropic), независимый приём Codex (OpenAI). P05.9: автор Codex (OpenAI), независимый приём Claude (Anthropic). `FILTER-REVIEWS.json` связывает все четыре записи с этими обзорами, хешами и квитанциями приёма. Один провайдер не объявляется автором всего сборного фильтра.

`SOURCE-CLOSURE-P01-251.json` связывает точный C, preflight, зелёный check_spec и матрицу обзоров. `AUTHORIZATION.json` использует предусмотренную оператором метку `ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW`, как принятая P01.180, в пределах поручения P01.251 на тот же порядок выпуска. Это метаданные локального выпуска; доставки, нового разрешения root и выбора пина эта задача не выполняла.

Прежняя оговорка P01.180 сохраняется: девять схем P01.228 не имели обзора другого провайдера; все они закрыты для M и J-входа. Механические проверки не доказывают полноту норм или реализацию.

## Дельта и пределы

Полная дельта M/J/J-входа к P01.180 — `DELTA-PAIR.json`; таблица — [DELTA-PAIR.md](DELTA-PAIR.md). C содержит другие принятые изменения main; они не скрыты и вручную не вырезались.

Доставка, права учётных записей стенда, канарейка, модели, кандидаты, генерации и пробы продукта не выполнялись. Пару как пин не выбирали. Сборку задания и подготовку цикла оформляет основной ход окна отдельно. По note/answered Архитектора от 2026-11-12T01:37:40Z условие о пробе старта перенесено в P01.252; P01.251 его не закрывает.
'''
(D/'PAIR-RESULT.md').write_text(report)
for p in (B/'scripts').glob('*.py'):shutil.copy2(p,D/'scripts'/p.name)
for n in ['preflight.py','filter_delta.py','ji_filter_blob.py']:shutil.copy2(B/n,D/'scripts'/n)
print('J-input passport sha256',sha(jp));print('operator unchanged',unchanged)
