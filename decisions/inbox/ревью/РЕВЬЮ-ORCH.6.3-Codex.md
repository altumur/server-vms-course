# Ревью ORCH.6.3 — сигналы оркестратора

2026-11-10, judge-1 / Codex. **Вердикт: с правками. Б/С/М: 0/4/0.**

Проверен репозиторий `/home/pilot/git/cammeta-watch.git`, ветка `architect/block-a-20261109`.
Целевые коммиты: `fc5a65b27aa9787300990708794229dc0adc3257`,
`bcb90bb16953e9695239e96c62608d2a993e2864`,
`b7fc1a35258f1ce34474f414a3be11a32e5399ff`,
`5d3e0fd38574c2f37f4b91913293407d99fdf422`.
Контекст и все номера строк ниже — срез последнего из них, `5d3e0fd`.
Основание — цель ORCH.6.3 и заявленное поведение целевых коммитов.
Б — блокирующая, С — существенная, М — мелкая находка. Все четыре находки меняют наблюдаемую доставку сигналов.

Исходники прочитаны через Git; оригинал не менялся. Тесты исполнены только на копиях во временных каталогах,
с подставными данными и доставкой. Живые Orca, очереди и окна не вызывались. Чужие отчёты по этой задаче не читались.
Фоновый агент внутри окна проверил новые сигналы; judge-1 прочитал доказательства и соответствующие пути исходников.

## С1. Завершённый без сдачи ход через очередь исключён из сигнала о простое

**Место:** `queues.py:303`, коммит `bcb90bb`.
Цитата: `if model.state_of(tid) != taskfiles.WORKING or tid in model.children:`.

**Сценарий:** шаг выдан через очередь, исполнитель отметил начало в 09:00, поработал и остановился в 09:10,
но не сдал результат. В 10:00 `record_turns()` отмечает конец хода (`queues.py:191`),
`task_state()` возвращает `turn ended` (`queues.py:555`), а модель — «ход закончен, не сдано» (`tasks.py:646`).
Новый фильтр пропускает только «идёт» и исключает этот шаг. Самостоятельно начатый шаг с той же отметкой
и тем же остановленным окном остаётся «идёт» и получает сигнал.

**Доказательство F1:** `direct_state="идёт"`, `queued_state="ход закончен, не сдано"`;
сигналов соответственно 1 и 0 при 50 минутах простоя. Сдачи нет в обоих случаях.
Старый контроль `stuck_jobs()` также пропускает запись с `ended_at` (`queues.py:451`).
Обещание сигналить о начатом несданном шаге независимо от способа начала не выполняется для обычной выдачи через очередь.

**Рекомендация:** проверять отметку начала и отсутствие сдачи также в состоянии «ход закончен, не сдано»;
сохранять исключения для принятого, отменённого, сданного и ожидающего решения шага.

## С2. Время чтения несвежего вывода подменяет начало простоя и меняет ключ сигнала

**Место:** `queues.py:315` и `queues.py:318`, коммит `bcb90bb`.
Цитата: `idle = _epoch(row.get('read_utc') if str(row.get('fresh')) == 'False' else row.get('since')) or started`.

**Сценарий пропуска:** шаг начат в 09:00. Отрисованный экран недоступен; чтение возвращает один и тот же
накопленный хвост с признаком работы. Это штатный путь `windows.py:203`, с `noscreen=True`.
`windows.collect()` при каждом чтении ставит текущее `read_utc` (`windows.py:237`),
а `collector.row_for()` переносит его в строку с `fresh=False` (`collector.py:154`).
Проверка выбирает текущее время чтения вместо начала периода без свежего подтверждения работы.

**Доказательство F2:** при чтениях в 09:05, 09:35 и 10:00 значение `since` остаётся 09:05,
`read_utc` продвигается до текущего чтения, число сигналов — `[0, 0, 0]`.
Через 55 минут без свежего экрана тридцатиминутный порог так и не достигается.
Это расходится с условием нового сигнала: только свежая «РАБОТАЮ» подтверждает работу.

**Сценарий повтора с той же причиной:** свежий СТОП с 09:10 в 10:00 уже дал сигнал
`stall:A:1794301800`. После ошибки чтения сборщик сохраняет прежние `since` и `read_utc`,
ставит `cached=True`, `fresh=False` (`collector.py:145`). В 10:30 проверка берёт `read_utc=10:00`
и создаёт новый ключ `stall:A:1794304800`. Работы между ними не было.

**Доказательство F5:** настоящий `task_events()` с первым ключом в `signals.sent` возвращает второй сигнал.
Один непрерывный простой повторно объявлен новым; повторов может быть больше при чередовании доступности экрана.

**Рекомендация:** хранить начало непрерывного периода без свежего подтверждения работы отдельно от времени опроса;
использовать его и для возраста, и для ключа. Ошибка чтения и чтение накопленного вывода не должны начинать новый период.

## С3. Ответ получает первая роль задачи вместо спросившей сессии

**Место:** `tasks.py:513`, коммит `b7fc1a3`.
Цитата: `target = current_session(names[0])`.

**Сценарий:** публичный API принимает задачу с `role: spec103, ops103`.
Сессия `ops103` задаёт вопрос: `ask()` разрешает это каждому участнику роли и записывает `question_by`
(`tasks.py:1563`, `tasks.py:1571`). `answer()` удаляет `question_by`, сохраняя только текст вопроса
(`tasks.py:1587`). Затем `answer_notices()` выбирает первого участника текущего `role`.

**Доказательство F3:** настоящие `add_task() → ask() → answer()` на временных файлах дают
`asker="ops103"`, но уведомление `("spec103", "answer:ASK:2026-11-10T09:59:30Z", ...)`.
В планировщике этот адрес используется напрямую (`queues.py:1278`), а общий ключ исключает последующее уведомление
спросившей сессии. Ответ Архитектора уходит другой сессии; спросившая продолжает ждать.

**Рекомендация:** при записи ответа сохранять его адресата из `question_by`, применяя существующий переход
к преемнику сессии. Доставку привязать к этому адресату, а не к позиции в списке ролей.

## С4. Разбор UTC через локальное летнее время делает свежий ответ просроченным

**Место:** `tasks.py:507`, коммит `b7fc1a3`.
Цитата: `moment = time.mktime(time.strptime(found.group(1), '%Y-%m-%dT%H:%M:%SZ')) - time.timezone`.

**Сценарий:** процесс работает в зоне с летним временем. `mktime()` разбирает строку как местное время,
с учётом летнего сдвига; `time.timezone` содержит стандартный зимний сдвиг.
Буква `Z` в формате — литерал и UTC не задаёт. В результате метка ответа сдвигается на час назад,
после чего проверка возраста (`tasks.py:511`) отбрасывает свежий ответ.

**Доказательство F4:** при настоящем UTC `now=2026-07-10T12:00:00Z` ответ
`2026-07-10T11:42:31Z` имеет возраст 17 минут 29 секунд. `answer_notices()` возвращает одно уведомление
при `TZ=UTC` и ни одного при `TZ=Europe/Berlin`.
В текущем UTC-окружении CT 103 этот дефект не проявляется; условие воспроизведения — зона с действующим летним временем.
Штатный тест `test_queues.py:2493` вычисляет `now` тем же выражением и скрывает ошибку.

**Рекомендация:** разбирать `Z` как UTC через `calendar.timegm()` либо `datetime` с явным `timezone.utc`.
Сравнивать с независимо заданным UTC `now`.

## Проверки и пределы вывода

- На копии `5d3e0fd` прошли 26 тестов `test_queues.Composer` и `test_queues.TurnEnd`.
  Проверены пустые и непустые экранные поля Claude/Codex/Kimi, неотрисованный экран и повторная проверка конца хода.
  Для `fc5a65b` новых подтверждённых дефектов в этом охвате нет.
- Прошли ещё 4 штатных теста: `test_queues.StalledStart`, `test_queues.AnswerNotices`, `test_queues.OwnerReady`.
  Итого **30/30**, код выхода 0. Их успех не покрывает контрпримеры С1–С4.
- Дополнительный сценарий владельца использовал настоящую модель: уведомляется READY;
  HOLD, ASKED, WAIT, STARTED и HANDED не уведомляются. Настоящий планировщик после
  `reserve() → settle(accepted=True)` выдаёт 0 повторных уведомлений вместо 1 на первом проходе.
  Для `5d3e0fd` новых подтверждённых дефектов в этом охвате нет.
- Проверки на синтетических данных не доказывают состояние развёрнутой службы или фактическую доставку Orca.
  Исправления кода не выполнялись.

Задача ORCH.6.3 повторно прочитана целиком перед оформлением сдачи: note прежний, поля answered нет.
После `git fetch origin` базис курса — `f7edb12f468f0c50c329b1f408ab103fad6f60d6`, новых входящих коммитов нет.
Задача не ссылается на конкретный ADR, дополнений к указанному в ней ADR нет.

## Воспроизводимые доказательства

Полный скрипт и результат включены ниже, поэтому квитанция не зависит от сохранности `/tmp`.
Рабочие копии доказательств: `/tmp/orch63-signals-nlljvrmn/repro_signals.py` и `results.txt`;
штатные тесты запускались в `/tmp/judge1-orch63-composer-ld2nvzq0`.
Скрипт дважды дал одинаковый вывод; SHA-256 `results.txt`:
`398c139a794e3034c75d0e96fab82d33dbb211050d9452fd547b284c7359c739`.

Для повторения создать временный каталог, извлечь туда через
`git --git-dir=/home/pilot/git/cammeta-watch.git show 5d3e0fd:<имя>` файлы
`windows.py`, `watchcfg.py`, `automation.py`, `tasks.py`, `queues.py`, `collector.py`, `inbox.py`, `planlinks.py`.
Сохранить следующий блок как `repro_signals.py` рядом с ними и выполнить `python3 repro_signals.py` из этого каталога.
Он использует только собственные временные файлы и не вызывает транспорт.

```python
import calendar
import copy
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import time

ROOT = Path(__file__).resolve().parent
fixture = tempfile.TemporaryDirectory(prefix='fixture-', dir=ROOT)
FIXTURE = Path(fixture.name)
os.environ['TZ'] = 'UTC'
time.tzset()
os.environ.update({
    'CAMMETA_BASE': str(FIXTURE),
    'CAMMETA_SESSIONS': str(FIXTURE / 'sessions'),
    'CAMMETA_COURSE': str(FIXTURE / 'course'),
    'CAMMETA_SNAPSHOT_DIR': str(FIXTURE / 'snapshot'),
})
import watchcfg
# Defeat any inherited path overrides before importing the modules under test.
for config_name, value in list(vars(watchcfg).items()):
    if config_name.isupper() and isinstance(value, str) and os.path.isabs(value):
        setattr(watchcfg, config_name, str(FIXTURE / config_name.lower()))
import tasks
import queues
import windows
import collector

def epoch(s):
    return calendar.timegm(time.strptime(s, '%Y-%m-%dT%H:%M:%SZ'))

def fields(role='ops103'):
    return dict(title='fixture', lesson='Общее', role=role, accept='architect', goal='fixture')

def model(turns=None, marks=None, data=None):
    return tasks.Model((data or {'A': fields()}, {}, []), {}, '', turns or {}, queues.ALLOWED, marks=marks)

START = '2026-11-10T09:00:00Z'
NOW = epoch('2026-11-10T10:00:00Z')
marks = {'A': {'utc': START, 'from': 'ops103'}}
rows = {'ops103': dict(state='СТОП', fresh=True, since='2026-11-10T09:10:00Z', read_utc='2026-11-10T10:00:00Z',
                      status_line='СТОП: отложил сдачу | ЖДУ: события', screen_changed='2026-11-10T09:10:00Z')}

# A start mark and the same stopped window: direct start vs a queue-issued start.
direct = model(marks=marks)
ledger = {'version': 1, 'sessions': {'ops103': {'A': dict(id='A', status='issued', issued_epoch=epoch('2026-11-10T08:59:00Z'),
          issued_at='2026-11-10T08:59:00Z', sends=[{'utc':'2026-11-10T08:59:00Z'}], seen_working=True,
          line_at_issue='СТОП: свободен | ЖДУ: поручения')}}}
queues.record_turns(ledger, rows, NOW)
queued = model(turns=queues.turn_view(ledger, NOW, marks), marks=marks)
direct_events = queues.stalled_start_events(direct, rows, marks, NOW)
queued_events = queues.stalled_start_events(queued, rows, marks, NOW)
assert len(direct_events) == 1 and not queued_events
print('F1 queue-stop:', json.dumps(dict(direct_state=direct.state_of('A'), queued_state=queued.state_of('A'),
      direct_events=direct_events, queued_events=queued_events, ended_at=ledger['sessions']['ops103']['A']['ended_at']), ensure_ascii=False))

# The successful noscreen fallback is re-read on each observed pass. Its read_utc advances,
# although the same accumulated tail stays frozen. No real Orca call is made.
registry = {'ops103': dict(handle='term_fixture', model='Claude', path='ct103:/tmp/fixture', note='')}
orig_one = windows.one
windows.one = lambda name, handle: (name, dict(ok=True, fresh=False, noscreen=True, busy=True,
    busy_signal='esc to interrupt', line=None, tail='esc to interrupt', sig='frozen-tail'))
state, previous = {}, None
reads, counts = [], []
try:
    for hhmm in ('09:05', '09:35', '10:00'):
        stamp = dt.datetime.fromisoformat('2026-11-10T'+hhmm+':00+00:00')
        obs = windows.collect(registry, state, stamp)
        row = collector.row_for('ops103', registry['ops103'], obs, previous, None, stamp)
        events = queues.stalled_start_events(direct, {'ops103': row}, marks, stamp.timestamp())
        reads.append({k: row[k] for k in ('state', 'fresh', 'since', 'read_utc')})
        counts.append(len(events))
        previous = row
finally:
    windows.one = orig_one
assert counts == [0, 0, 0]
print('F2 noscreen:', json.dumps(dict(reads=reads, event_counts=counts), ensure_ascii=False))

# The task API permits a comma-separated role, and either named session may ask.
# The answer command deletes question_by before the notification is built.
task_dir = Path(watchcfg.TASKS)
task_dir.mkdir(parents=True)
tasks.add_task('architect', 'fixture', 'fixture', 'spec103, ops103', ident='ASK', lesson='Общее', req='З-1', accept_by='architect', now=NOW-120)
tasks.ask('ASK', 'ops103', 'Нужен ответ', now=NOW-60)
before = tasks.load_files(task_dir)[0]['ASK']
tasks.answer('ASK', 'architect', 'Продолжай', now=NOW-30)
after = tasks.load_files(task_dir)[0]['ASK']
notice_model = tasks.Model(({'ASK':after}, {}, []), {}, '', {}, queues.ALLOWED)
out = notice_model.answer_notices(NOW)
assert before['question_by'] == 'ops103' and out[0][0] == 'spec103'
print('F3 wrong-role:', json.dumps(dict(asker=before['question_by'], role=after['role'], answer_notice=out), ensure_ascii=False))

# UTC input must not change meaning in DST. The actual epoch is always UTC.
old_tz = os.environ.get('TZ')
try:
    summer_now=epoch('2026-07-10T12:00:00Z')
    summer_model = model(data={'DST':dict(fields(), answered='2026-07-10T11:42:31Z architect: да (вопрос: как?)')})
    dst_counts={}
    for tz in ('UTC', 'Europe/Berlin'):
        os.environ['TZ']=tz
        time.tzset()
        dst_counts[tz]=len(summer_model.answer_notices(summer_now))
    assert dst_counts == {'UTC':1,'Europe/Berlin':0}
    print('F4 DST:', json.dumps(dst_counts, ensure_ascii=False))
finally:
    if old_tz is None:
        os.environ.pop('TZ', None)
    else:
        os.environ['TZ']=old_tz
    time.tzset()

# A continuous stopped interval is notified again merely because the terminal
# becomes unreadable after the first signal, without any working state between.
first=queues.stalled_start_events(direct, rows, marks, NOW)[0]
later_row=dict(rows['ops103'], fresh=False, cached=True, read_utc='2026-11-10T10:00:00Z')
later=queues.stalled_start_events(direct, {'ops103':later_row}, marks, NOW+1800)[0]
assert first[0] != later[0]
events_ledger = {'version': 1, 'sessions': {}, 'signals': {'sent': {first[0]: {'status': 'issued'}}}}
repeated = [e for e in queues.task_events(direct, None, events_ledger, marks, NOW+1800, [], None,
            {'ops103': later_row}) if e[1] == 'step_stalled']
assert len(repeated) == 1 and repeated[0][0] == later[0]
print('F5 duplicate:', json.dumps(dict(first_key=first[0], later_key=later[0],
      first_text=first[3], later_text=later[3], task_events_after_first_sent=repeated), ensure_ascii=False))

# Positive and negative owner-ready boundaries from the real Model.
owner_data = {
    'READY': fields('owner'),
    'HOLD': dict(fields('owner'), owner=True),
    'ASKED': dict(fields('owner'), question='жду решения'),
    'WAIT': dict(fields('owner'), after=['PENDING']),
    'PENDING': fields(),
    'STARTED': fields('owner'),
    'HANDED': fields('owner'),
}
owner_model = tasks.Model((owner_data, {}, []), {}, '', {}, queues.ALLOWED,
    marks={'STARTED': {'utc':START,'from':'owner'}}, handed={'HANDED': {'commit':'abc1234'}})
owner_notices=owner_model.owner_ready_notices()
assert [(n[0],n[1]) for n in owner_notices] == [('owner', 'owner-ready:READY:0')]
print('Owner-ready boundaries:', json.dumps(dict(states={tid:owner_model.state_of(tid) for tid in owner_data},
      notices=owner_notices), ensure_ascii=False))

# Real queue planner: a sent owner-ready key is not planned on the next pass.
tasks.add_task('architect', 'проба', 'проба', 'owner', ident='OWNER', lesson='Общее', req='З-1', accept_by='architect', now=NOW)
Path(watchcfg.PLAN).write_text('', encoding='utf-8')
plan1=queues.plan([], {}, {}, NOW, force=True)
owner_jobs1=[job for job in plan1.jobs if job[1]=='owner']
assert len(owner_jobs1)==1 and owner_jobs1[0][2]=='owner-ready:OWNER:0'
plan1.save=lambda path,data: Path(path).write_text(json.dumps(data), encoding='utf-8')
reservation=plan1.reserve('handin', 'owner', owner_jobs1[0][2], NOW)
reservation['accepted']=True
plan1.settle('handin', reservation)
plan2=queues.plan([], {}, {}, NOW+60, force=True)
owner_jobs2=[job for job in plan2.jobs if job[1]=='owner']
assert owner_jobs2==[]
print('Owner-ready queue deduplication:', json.dumps(dict(first_pass=owner_jobs1, next_pass=owner_jobs2), ensure_ascii=False))

print('ALL ASSERTIONS PASSED')
print('LIMITS: synthetic data only; direct calls from copied source; no live Orca, sends, probes, candidates, or course-code execution.')
fixture.cleanup()
```

Фактический вывод:

```text
F1 queue-stop: {"direct_state": "идёт", "queued_state": "ход закончен, не сдано", "direct_events": [["stall:A:1794301800", "step_stalled", "A", "Шаг A (критический путь) начат 2026-11-10T09:00, не сдан, окно ops103 не работает 50 мин"]], "queued_events": [], "ended_at": "2026-11-10T10:00:00Z"}
F2 noscreen: {"reads": [{"state": "РАБОТАЮ", "fresh": false, "since": "2026-11-10T09:05:00Z", "read_utc": "2026-11-10T09:05:00Z"}, {"state": "РАБОТАЮ", "fresh": false, "since": "2026-11-10T09:05:00Z", "read_utc": "2026-11-10T09:35:00Z"}, {"state": "РАБОТАЮ", "fresh": false, "since": "2026-11-10T09:05:00Z", "read_utc": "2026-11-10T10:00:00Z"}], "event_counts": [0, 0, 0]}
F3 wrong-role: {"asker": "ops103", "role": "spec103, ops103", "answer_notice": [["spec103", "answer:ASK:2026-11-10T09:59:30Z", "Ответ Архитектора по ASK: Продолжай"]]}
F4 DST: {"UTC": 1, "Europe/Berlin": 0}
F5 duplicate: {"first_key": "stall:A:1794301800", "later_key": "stall:A:1794304800", "first_text": "Шаг A (критический путь) начат 2026-11-10T09:00, не сдан, окно ops103 не работает 50 мин", "later_text": "Шаг A (критический путь) начат 2026-11-10T09:00, не сдан, окно ops103 не работает 30 мин", "task_events_after_first_sent": [["stall:A:1794304800", "step_stalled", "A", "Шаг A (критический путь) начат 2026-11-10T09:00, не сдан, окно ops103 не работает 30 мин"]]}
Owner-ready boundaries: {"states": {"READY": "готова", "HOLD": "ждёт владельца", "ASKED": "ждёт решения", "WAIT": "ждёт", "PENDING": "готова", "STARTED": "идёт", "HANDED": "на приёме"}, "notices": [["owner", "owner-ready:READY:0", "Шаг READY готов к началу (роль владельца): fixture"]]}
Owner-ready queue deduplication: {"first_pass": [["handin", "owner", "owner-ready:OWNER:0", "Шаг OWNER готов к началу (роль владельца): проба"]], "next_pass": []}
ALL ASSERTIONS PASSED
LIMITS: synthetic data only; direct calls from copied source; no live Orca, sends, probes, candidates, or course-code execution.
```
