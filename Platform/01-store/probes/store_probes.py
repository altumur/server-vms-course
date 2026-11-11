"""Named, runnable Z21 probes over independently captured raw observations.

This is an internal acceptance component, not profile2/assembly1 or a platform
wire. It never discovers a process, starts a stand, or accepts a JSON claim of
provider qualification. The CLI judges observations; native execution needs the
explicit missing bindings listed in REGISTRY. Owned controls are labelled as
such, never promoted to candidate/production PASS.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from store_fitness import same
import copy_stream
import store_fitness as fitness
import store_probe_http as wire


SOURCE = 'a08ef6ef101514c926e68d3fb00c8d121da60e01'
SOURCE21 = 'ecb501b3582834ad4181d8e3e6dc23e4dfd0df5d'
OWNER = 'bbf445f12e81b94453b0fe72978541eaa5b055b2'
OWNERSHIP_DECISION = '4e1391687364394ed2f6e41d2c8dabcf07ff40a0'
OWNERSHIP_SOURCE = '5916920c210eecd1e723d05767dd399f27b27b8f'
OWNERSHIP_CLARIFICATION = '9ca2c10197d9d06d17ad5768d4d0e20f2f1a2c4f'
MissingBinding = fitness.MissingBinding
InstrumentationError = fitness.InstrumentationError
REGISTRY = {
    '01-connections': dict(number=1, refs=['P/01.3-R008', 'P/01.3-R017', 'P/01.1-R144', 'P/01.1-R145'], groups=[],
        required=['permitted isolated daemon argv/cwd/env and immutable executable/profile identity',
                  'separate -max-conns/-api-conns endpoints and declared limits',
                  'independent server accepted-connection/held-close observer']),
    '02-input-drain': dict(number=2, refs=['P/01.1-R147', 'P/01.1-R050', 'P/01.1-R054', 'P/01.1-R386', 'P/01.1-R387', 'P/01.1-R388', 'P/01.1-R389', 'P/01.1-R391'],
        groups=['RUN-T01', 'RUN-T02', 'RUN-T03'],
        required=['permitted isolated raw socket (adapters.door is insufficient)',
                  'declared finite idle/header/body/drain intervals and raw-byte bound',
                  'calibrated duplex full-send/drain-start/close observer and applied-id state oracle']),
    '03-lock-wait': dict(number=3, refs=['P/01.1-R144', 'P/01.3-R034'], groups=['RUN-L02'],
        required=['actual declared local-lock wait and measurement allowance',
                  'independent relevant-lock holder/activation/release binding',
                  'permitted native request and business/id before-after oracle']),
    '04-barrier-replay': dict(number=4, refs=['P/01.1-R144'],
        groups=['RUN-F03'],
        required=['independent complete-recoverable-record/post-rename barrier fault activation',
                  'independent native same-id request/reply and barrier-hit observations',
                  'distinct original/repeated-failure/success live and reopened business/id snapshots',
                  'pre-effect and uncertain-medium providers for those separate stages']),
    '05-data-ownership': dict(number=5, refs=['P/01.3-R006', 'P/01.3-R029'], groups=[],
        new_decision=OWNERSHIP_DECISION,
        normative_source_pin=OWNERSHIP_SOURCE,
        clarification=OWNERSHIP_CLARIFICATION,
        new_source_carriers={'Platform/01-store/spec/01.3-store.norms.md': [178, 409, 410],
                             'Platform/01-store/forms/refusals.tsv': [72, 73]},
        required=['two explicitly permitted own isolated daemon argv/cwd/env with one fresh fixture -dir',
                  'existing import and restore native command bindings and immutable copy',
                  'independent first-owner liveness/lock ownership and complete directory fingerprint',
                  'legitimate shutdown and stopped-daemon/fresh-dir positive contexts',
                  'independent simultaneous acquisition/empty-dir race and directory-check priority observer']),
    '06-cost-id': dict(number=6, refs=['P/01.1-R148', 'P/01.1-R141', 'P/01.1-R399', 'P/01.1-R400'],
        groups=['RUN-W01', 'RUN-W02', 'RUN-W03', 'RUN-W04'],
        required=['capacity-qualified experiment sizes/resources and declared cost model',
                  'independent foreground/background/checkpoint work/bytes and import-prefix observer',
                  'qualified clock/distinct successful id-application count and replay/reopen oracle',
                  'RAM-cache/durable-index/eligible-backlog observer and finite declared collection budget']),
    '07-framing': dict(number=7, refs=['P/01.1-R049', 'P/01.1-R050', 'P/01.1-R054', 'P/01.1-R333', 'P/01.1-R334', 'P/01.1-R335', 'P/01.1-R336', 'P/01.1-R337', 'P/01.1-R386', 'P/01.1-R387'],
        groups=['RUN-T02', 'RUN-H02'],
        required=['permitted isolated raw socket and known effective body limit',
                  'framing-controlled raw sender/receiver with actual EOF',
                  'independent business/id before-after oracle and valid-request control']),
    '08-backup-rows': dict(number=8, refs=['P/01.1-R028', 'P/01.3-R006', 'P/01.3-R018', 'P/01.3-R033'],
        groups=['RUN-L01', 'RUN-H01', 'RUN-H02', 'RUN-H03'],
        required=['permitted independent storage fixture via stand.spoil-row {data}/{key}/{what}',
                  'existing stand.backup {socket}/{file} and actual native exit/log/artifact',
                  'raw GET /v1/copy binding for separate HTTP result (not inferred from backup CLI)',
                  'known-version/unreadable/index_lost public oracle and previous artifact fingerprint']),
}


def need(obj, name):
    if not isinstance(obj, dict):
        raise InstrumentationError('observation record must be an object')
    if name not in obj or obj[name] is None:
        raise MissingBinding('missing actual observation: ' + name)
    return obj[name]


def flag(obj, name):
    value = need(obj, name)
    if type(value) is not bool:
        raise InstrumentationError(name + ' must be an actual boolean')
    return value


def active(obj, name):
    if not flag(obj, name):
        raise InstrumentationError(name + ' was not independently activated')


def integer(obj, name, minimum=0):
    value = need(obj, name)
    if type(value) is not int or value < minimum:
        raise InstrumentationError(name + ' must be an observed integer >= ' + str(minimum))
    return value


def seq(obj, name, *, nonempty=True):
    value = need(obj, name)
    if not isinstance(value, list) or nonempty and not value:
        raise InstrumentationError(name + ' must be an observation list')
    return value


def stamp(obj, name):
    return fitness.number(need(obj, name))


def unchanged(obj, before, after, label):
    return [] if same(need(obj, before), need(obj, after)) else [label]


def reply(obj, name):
    item = need(obj, name)
    return wire.response(wire.bytes_from(need(item, 'raw_b64')), closed=flag(item, 'closed'))


def success(value, expected=None):
    errors = [] if value['status'] == 200 else ['valid/recovery control did not succeed']
    if expected is not None and not same(wire.strict_json(value['body']), expected):
        errors.append('valid/recovery raw response differs from independent expected answer')
    return errors


def effects_absent(obj):
    return unchanged(obj, 'before', 'after', 'refusal changed business/version/applied-id state')


def connections(obs):
    rows = seq(obs, 'doors')
    if {need(row, 'role') for row in rows} != {'process', 'api'} or len(rows) != 2:
        raise MissingBinding('separate process-door and API connection-limit observations required')
    errors = []
    for row in rows:
        active(row, 'accept_observer_active')
        active(row, 'noninterfering_accounting_domain_proved')
        limit, held = integer(row, 'limit', 1), seq(row, 'held_accept_ids')
        if any(not isinstance(x, str) or not x for x in held) or len(set(held)) != len(held):
            raise InstrumentationError('accepted connection identities are not distinct')
        overflow, recovered = need(row, 'overflow_accept_id'), need(row, 'recovered_accept_id')
        if overflow in held or recovered in [*held, overflow]:
            raise InstrumentationError('overflow/recovered connections lack fresh accepted identities')
        if len(held) != limit or integer(row, 'held_alive_at_overflow') != limit:
            raise InstrumentationError('declared limit was not actually held at crossing')
        if need(row, 'released_accept_id') not in held:
            raise InstrumentationError('the released connection was not one of the held peers')
        if not stamp(row, 'overflow_at') < stamp(row, 'released_at') < stamp(row, 'recovered_at'):
            raise InstrumentationError('crossing/release/recovery order is not observed')
        errors += wire.fault_errors(reply(row, 'overflow'), 503, 'unavailable',
                                    headers={'retry-after': '1'})
        errors += success(reply(row, 'recovered'), need(row, 'expected_recovered'))
        errors += effects_absent(row)
    return errors


def input_drain(obs):
    budgets = fitness.PhaseBudgets(**need(obs, 'budgets'))
    allowance = fitness.number(need(obs, 'measurement_allowance'))
    phases = seq(obs, 'phases')
    names = {'idle', 'partial-line', 'header-trickle', 'body-no-byte', 'body-trickle', 'eof'}
    if {need(row, 'case') for row in phases} != names or len(phases) != len(names):
        raise MissingBinding('all six idle/header/body/EOF phase controls required')
    errors = []
    for row in phases:
        active(row, 'clock_active')
        name = need(row, 'case')
        sent = b''.join(wire.bytes_from(need(item, 'raw_b64')) for item in seq(row, 'sent_chunks', nonempty=False))
        complete_line = b'POST /v1/write HTTP/1.1\r\n' in sent
        if flag(row, 'valid_request_line') != complete_line:
            raise InstrumentationError('line-validity observation contradicts actual sent prefix')
        if name == 'idle' and sent or name == 'partial-line' and b'\r\n' in sent:
            raise InstrumentationError('idle/partial-line recipe contains a complete request')
        if name.startswith('body-') and b'\r\n\r\n' not in sent:
            raise InstrumentationError('body phase never established complete headers')
        if name.startswith('body-'):
            length = re.search(rb'\r\nContent-Length: ([0-9]+)\r\n', sent)
            if not length or not 0 < int(length[1]) <= integer(obs, 'body_limit', 1):
                raise InstrumentationError('body timeout recipe instead triggers early size/framing refusal')
        if name == 'body-no-byte' and sent.partition(b'\r\n\r\n')[2]:
            raise InstrumentationError('no-first-body-byte recipe actually sent a body byte')
        send_times = [stamp(item, 'at') for item in row['sent_chunks']]
        if send_times != sorted(send_times):
            raise InstrumentationError('send event order contradicts monotonic clock')
        actual = reply(row, 'response') if need(row, 'response')['raw_b64'] else None
        r = None if actual is None else (actual['status'], wire.strict_json(actual['body']))
        closed = flag(need(row, 'response'), 'closed')
        if name != 'eof':
            phase = 'idle' if name == 'idle' else 'header' if name in ('partial-line', 'header-trickle') else 'body'
            deadline = fitness.phase_deadline(phase, budgets,
                accepted_at=row.get('accepted_at'), first_request_byte_at=row.get('first_request_byte_at'),
                headers_complete_at=row.get('headers_complete_at'))
            errors += fitness.phase_close_errors(deadline, need(row, 'closed_at'),
                                                  measurement_allowance=allowance)
        errors += fitness.input_timeout_errors(valid_request_line=flag(row, 'valid_request_line'),
            response_started=False, eof=name == 'eof', actual_reply=r, request_method='POST',
            actual_closed=closed, executed=flag(row, 'executed'), occupied_id=flag(row, 'occupied_id'),
            connection_close_header=actual is not None and 'close' in
                [token.strip().lower() for value in actual['headers'].get('connection', []) for token in value.split(',')])
        errors += effects_absent(row)
    drains = seq(obs, 'early')
    if {need(row, 'case') for row in drains} != {'declared', 'chunked-never-final'} or len(drains) != 2:
        raise MissingBinding('declared-size and nonterminating chunked early-refusal traces required')
    for row in drains:
        sent = wire.bytes_from(need(row, 'request_prefix_b64'))
        if row['case'] == 'declared':
            length = integer(row, 'declared_length', 1)
            if length <= integer(obs, 'body_limit', 1) or b'Content-Length: ' + str(length).encode() not in sent:
                raise InstrumentationError('early declared-length refusal did not announce excess body')
        elif b'Transfer-Encoding: chunked\r\n' not in sent or sent.endswith(b'0\r\n\r\n'):
            raise InstrumentationError('chunked early-refusal recipe accidentally completed the stream')
        errors += wire.fault_errors(reply(row, 'response'), 413, 'toolarge',
            headers={'connection': 'close'}, required={'limit': integer(obs, 'body_limit', 1)},
            optional=('size',) if row['case'] == 'declared' else ())
        args = {name: need(row, name) for name in ('latch_activated', 'refusal_sent_complete_at',
            'refusal_received_complete_at', 'drain_started_at', 'sender_released_at', 'closed_at', 'drained_bytes')}
        errors += fitness.early_refusal_errors(budgets, **args, measurement_allowance=allowance)
        if not flag(need(row, 'response'), 'closed'):
            errors.append('early refusal did not close')
        if row['case'] == 'declared' and integer(row, 'drained_bytes') > integer(row, 'declared_length', 1):
            errors.append('discard exceeded declared body length')
        if integer(row, 'responses') != 1:
            errors.append('early refusal added another response')
        errors += effects_absent(row)
    errors += success(reply(obs, 'valid_control'), need(obs, 'valid_control_expected'))
    return errors


def lock_wait(obs):
    active(obs, 'lock_held_independently')
    if need(obs, 'required_lock_domain') != need(obs, 'observed_lock_domain'):
        raise InstrumentationError('held lock is not the independently identified mutation-lock domain')
    wait = fitness.number(need(obs, 'declared_wait'), positive=True)
    allowance = fitness.number(need(obs, 'measurement_allowance'))
    held, started, refused, released, recovered = [stamp(obs, k) for k in
        ('held_at', 'request_at', 'refusal_at', 'released_at', 'recovery_at')]
    if not held <= started <= refused < released < recovered:
        raise InstrumentationError('lock/refusal/release/retry event order is contradictory')
    errors = wire.fault_errors(reply(obs, 'refusal'), 503, 'unavailable')
    if refused - started > wait + allowance:
        errors.append('lock wait exceeded its actual declared finite bound')
    errors += effects_absent(obs)
    errors += success(reply(obs, 'recovery'), need(obs, 'expected_recovery_answer'))
    errors += unchanged(obs, 'expected_recovery', 'actual_recovery', 'retry after release has wrong state')
    return errors


def barrier_replay(obs):
    active(obs, 'fault_observer_active')
    stage = need(obs, 'stage')
    if stage not in ('pre-effect', 'complete-record'):
        raise MissingBinding('uncertain-medium stage needs its separate qualified medium-model callable')
    if stage == 'complete-record':
        if need(obs, 'barrier_observer_kind') != 'storage-durability':
            raise InstrumentationError('Raft Barrier/Shutdown/API success is not a storage durability observation')
        active(obs, 'recoverable_record_proved')
        active(obs, 'post_rename_barrier_proved')
        if integer(obs, 'failed_barrier_hits') < 2:
            raise InstrumentationError('initial and repeated same-id barrier faults were not activated')
        if integer(obs, 'successful_barrier_hits', 1) < 1:
            raise InstrumentationError('successful retry did not observe required barrier completion')
        requests = seq(obs, 'requests_b64')
        if len(requests) != 3 or len({wire.bytes_from(x) for x in requests}) != 1:
            raise InstrumentationError('the three actual requests were not the same-id command')
        raw = wire.bytes_from(requests[0])
        if not raw.startswith(b'POST /v1/write HTTP/1.1\r\n'):
            raise InstrumentationError('barrier experiment did not issue a public write')
        command = wire.strict_json(raw.partition(b'\r\n\r\n')[2])
        if not isinstance(command, dict) or not isinstance(command.get('id'), str) or not command['id']:
            raise InstrumentationError('barrier experiment lacks a real same-id input')
    args = {k: need(obs, k) for k in ('before', 'published', 'after', 'reopened')}
    first = reply(obs, 'reply')
    args['reply'] = (first['status'], wire.strict_json(first['body']))
    if stage == 'complete-record':
        for key in ('repeated_failure', 'replay'):
            value = reply(obs, key)
            args[key] = (value['status'], wire.strict_json(value['body']))
        for key in ('first_answer', 'repeated_after', 'repeated_reopened', 'retry_after', 'retry_reopened'):
            args[key] = need(obs, key)
        args['post_observation_order'] = tuple(seq(obs, 'post_observation_order'))
    return fitness.barrier_errors(stage, activated=True, **args)


def directory_fingerprint(root, *, byte_guard, entry_guard):
    """Fingerprint an explicitly supplied own fixture without following links.

    Capacity is an observer prerequisite, not a store limit. Metadata detects
    replacement/same-byte rewrites; independent write attribution is still
    required while the legitimate owner is live. No global filesystem scan.
    """
    if type(byte_guard) is not int or type(entry_guard) is not int or min(byte_guard, entry_guard) <= 0:
        raise MissingBinding('explicit permitted fixture fingerprint capacity required')
    result, consumed = {}, 0
    def identity(st):
        return (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid,
                st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    def visit(folder_fd, prefix):
        nonlocal consumed
        with os.scandir(folder_fd) as entries:
            names = []
            for entry in entries:
                if len(names) + len(result) >= entry_guard:
                    raise MissingBinding('fixture fingerprint entry capacity exhausted')
                names.append(entry.name)
            names.sort(key=os.fsencode)
        for leaf in names:
            if len(result) >= entry_guard:
                raise MissingBinding('fixture fingerprint entry capacity exhausted')
            before = os.stat(leaf, dir_fd=folder_fd, follow_symlinks=False)
            row = dict(mode=stat.S_IMODE(before.st_mode), uid=before.st_uid, gid=before.st_gid,
                       device=before.st_dev, inode=before.st_ino,
                       mtime_ns=before.st_mtime_ns, ctime_ns=before.st_ctime_ns)
            name = prefix + leaf
            if stat.S_ISLNK(before.st_mode):
                row.update(type='link', target=os.readlink(leaf, dir_fd=folder_fd))
            elif stat.S_ISDIR(before.st_mode):
                row['type'] = 'directory'
            elif stat.S_ISREG(before.st_mode):
                if consumed + before.st_size > byte_guard:
                    raise MissingBinding('fixture fingerprint byte capacity exhausted')
                digest = hashlib.sha256()
                fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=folder_fd)
                with os.fdopen(fd, 'rb') as stream:
                    if identity(os.fstat(stream.fileno())) != identity(before):
                        raise InstrumentationError('fixture entry changed during fingerprint')
                    for chunk in iter(lambda: stream.read(65536), b''):
                        consumed += len(chunk)
                        if consumed > byte_guard:
                            raise MissingBinding('fixture fingerprint byte capacity exhausted')
                        digest.update(chunk)
                row.update(type='file', size=before.st_size, sha256=digest.hexdigest())
            else:
                raise MissingBinding('non-file fixture entry needs an explicit observer: ' + name)
            result[name] = row
            if row['type'] == 'directory':
                child_fd = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=folder_fd)
                try:
                    if identity(os.fstat(child_fd)) != identity(before):
                        raise InstrumentationError('fixture directory changed during fingerprint')
                    visit(child_fd, name + '/')
                finally:
                    os.close(child_fd)
            if identity(os.stat(leaf, dir_fd=folder_fd, follow_symlinks=False)) != identity(before):
                raise InstrumentationError('fixture metadata changed during fingerprint')
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise MissingBinding('an explicit real own fixture directory is required') from exc
    try:
        visit(fd, '')
    finally:
        os.close(fd)
    return result


def data_ownership(obs):
    active(obs, 'first_daemon_alive')
    active(obs, 'independent_lock_observer')
    active(obs, 'quiescence_or_writer_attribution_proved')
    first = integer(obs, 'first_pid', 1)
    before = need(obs, 'directory_before')
    if not isinstance(before, dict) or not before:
        raise InstrumentationError('complete nonempty fixture directory fingerprint required')
    actions = seq(obs, 'blocked_operations')
    if {need(row, 'operation') for row in actions} != {'second-daemon', 'import', 'restore', 'recover'} or len(actions) != 4:
        raise MissingBinding('second-daemon/import/restore/local-recover ownership traces required')
    errors = []
    races = seq(obs, 'atomic_races')
    if {need(row, 'initial_state') for row in races} != {'empty', 'healthy-completed'} or len(races) != 2:
        raise MissingBinding('simultaneous starts on empty AND healthy completed fixture required')
    for race in races:
        active(race, 'simultaneous_latch_active')
        attempts = seq(race, 'attempts')
        if len(attempts) != 2 or len({integer(row, 'pid', 1) for row in attempts}) != 2:
            raise InstrumentationError('atomic race needs two distinct owned contenders')
        winners = [row for row in attempts if flag(row, 'became_ready')]
        if len(winners) != 1:
            errors.append('simultaneous start did not acquire exactly one owner')
        elif integer(race, 'owner_after', 1) != winners[0]['pid'] or not flag(race, 'winner_still_alive'):
            errors.append('race winner did not retain exclusive ownership')
        for row in attempts:
            if not row['became_ready']:
                if integer(row, 'exit') != 2:
                    errors.append('atomic acquisition loser used wrong startup exit')
                if need(race, 'data_path').encode() not in wire.bytes_from(need(row, 'log_b64')):
                    errors.append('race loser did not log the fixture directory')
                if seq(row, 'attributed_write_events', nonempty=False):
                    errors.append('race loser wrote the directory')
    for row in actions:
        if integer(row, 'pid', 1) == first:
            raise InstrumentationError('a second own process identity is required')
        if need(row, 'data_identity') != need(obs, 'data_identity'):
            raise InstrumentationError('refusal probe did not use the same fixture data directory')
        if seq(row, 'attributed_write_events', nonempty=False):
            errors.append('refused contender wrote the live-owned directory before readiness/refusal')
        if not flag(row, 'ownership_before_other_directory_checks'):
            errors.append('another directory-dependent refusal preceded the live ownership check')
        if not flag(row, 'exited_normally'):
            raise InstrumentationError('a harness-killed process is not a native ownership refusal')
        if need(obs, 'data_path').encode('utf-8') not in wire.bytes_from(need(row, 'log_b64')):
            errors.append('ownership refusal log did not name the fixture directory')
        # This exit is the NEW explicit ADR0130(2) decision, not an assertion
        # about the old a08 startup FORMAT/refusal surface.
        if row['operation'] == 'second-daemon':
            if integer(row, 'exit') != 2 or flag(row, 'became_ready'):
                errors.append('second daemon acquired readiness while first owned the directory')
        elif integer(row, 'exit') == 0:
            errors.append('live data import/restore was not refused: ' + row['operation'])
        if not same(before, need(row, 'directory_after')):
            errors.append('refused operation changed directory bytes/mode/type')
        if integer(row, 'lock_owner_after', 1) != first or not flag(row, 'first_still_alive'):
            errors.append('refused operation stole lock or disturbed first daemon')
    endings = seq(obs, 'owner_endings')
    if {need(row, 'kind') for row in endings} != {'normal', 'sigkill'} or len(endings) != 2:
        raise MissingBinding('normal-stop AND own-child SIGKILL ownership-release observations required')
    for row in endings:
        active(row, 'first_exit_observed')
        if flag(row, 'manual_ownership_cleanup'):
            errors.append('next start required manual stale-ownership cleanup')
        if need(row, 'restart_fixture') != 'healthy-completed':
            raise InstrumentationError('positive restart improperly used a foreign FORMAT/unfinished transfer fixture')
        if integer(row, 'next_start_exit') != 0:
            errors.append('positive control after owner exit failed')
        errors += unchanged(row, 'expected_state', 'actual_state', 'post-owner start changed data')
    preconditions = seq(obs, 'post_exit_preconditions')
    if {need(row, 'case') for row in preconditions} != {'foreign-format', 'unfinished-transfer'} or len(preconditions) != 2:
        raise MissingBinding('separate FORMAT and unfinished-transfer post-death negative controls required')
    for row in preconditions:
        if integer(row, 'exit') != 2 or flag(row, 'old_ownership_refused'):
            errors.append('owner death erased a different startup precondition or retained stale ownership')
        errors += unchanged(row, 'before', 'after', 'post-death refusal changed invalid fixture')
    return errors


def cost_id(obs):
    if not flag(obs, 'capacity_qualified'):
        raise MissingBinding('real permitted capacity for this experiment is not qualified')
    for key in ('storage_observer_active', 'memory_observer_active',
                'clock_observer_active', 'successful_application_counter_active'):
        active(obs, key)
    errors = []
    samples = seq(obs, 'cost_samples')
    if {need(row, 'operation') for row in samples} != {'write', 'import'}:
        raise MissingBinding('separate write and import measured samples required')
    for op in ('write', 'import'):
        series = [row for row in samples if row['operation'] == op]
        if len({integer(row, 'stored_rows', 1) for row in series}) < 2:
            raise MissingBinding('measured workload must vary stored cardinality separately: ' + op)
        for row in series:
            integer(row, 'input_bytes', 1)
            events = seq(row, 'storage_events')
            total = 0
            for item in events:
                size = integer(item, 'bytes')
                total += size
                kind = need(item, 'kind')
                if kind not in ('incremental', 'checkpoint', 'import-build'):
                    raise InstrumentationError('unknown observed persistence-work category')
                # Partial indexed/page collateral is not a forbidden full
                # store rewrite. These independent full-scope counters must be
                # supplied by the qualified observer, never inferred merely
                # from one unchanged row touched or a producer feature flag.
                integer(item, 'unchanged_rows_written')
                integer(item, 'processed_prefix_rewritten')
                if kind == 'incremental' and (integer(item, 'whole_unchanged_store_serializations') or
                                              integer(item, 'whole_unchanged_store_rewrites')):
                    errors.append('ordinary application serialized/rewrote the whole unchanged store')
                if kind == 'import-build' and integer(item, 'full_processed_prefix_rewrites'):
                    errors.append('import repeatedly rewrote the whole processed prefix')
            if total != integer(row, 'independent_total_bytes'):
                raise InstrumentationError('foreground/background/checkpoint total contradicts independent counter')
            if not isinstance(need(row, 'declared_model'), str) or not row['declared_model']:
                raise MissingBinding('declared qualified cost model absent')
            if total > integer(row, 'declared_model_byte_bound', 1):
                errors.append('measured total exceeds declared qualified cost model')
    replays = seq(obs, 'replays')
    boundaries = set()
    for row in replays:
        age = stamp(row, 'age')
        later = integer(row, 'later_successful_distinct_id_records')
        if not flag(row, 'count_is_independent_successful_applications'):
            raise InstrumentationError('request/refusal/replay count is not a distinct applied-id count')
        eligible = age > 120 and later >= 50000  # existing Source constants, not new budgets
        boundaries.add((age > 120, later >= 50000))
        if not eligible:
            if not flag(row, 'again') or flag(row, 'new_apply'):
                errors.append('forgot an id before both strict age AND count minima')
            errors += unchanged(row, 'original_answer', 'actual_answer', 'required replay changed answer/version')
            errors += unchanged(row, 'expected_reopened', 'actual_reopened', 'required id not retained across cache/reopen')
    if boundaries != {(False, False), (True, False), (False, True), (True, True)}:
        raise MissingBinding('age/count four-way retention boundary controls required')
    memory = need(obs, 'memory')
    if integer(memory, 'resident_id_entries') != integer(memory, 'independent_resident_id_entries'):
        raise InstrumentationError('resident id gauge contradicts independent memory/index observation')
    if integer(memory, 'resident_id_entries') > integer(memory, 'declared_cache_entries', 1):
        errors.append('resident replay cache exceeds its qualified declared bound')
    if not flag(memory, 'required_ids_still_indexed'):
        errors.append('RAM eviction discarded required durable indexed ids')
    if stamp(memory, 'collection_completed_at') > stamp(memory, 'eligible_at') + fitness.number(need(memory, 'declared_collection_interval'), positive=True):
        errors.append('eligible backlog not collected within declared finite budget')
    if integer(memory, 'eligible_backlog_after') != 0:
        errors.append('eligible backlog remains after measured collection interval')
    return errors


def chunked_request(raw):
    """Decode the fixed public raw request recipe, never serialize its body."""
    if not isinstance(raw, bytes):
        raise InstrumentationError('raw recipe must be bytes')
    head, separator, body = raw.partition(b'\r\n\r\n')
    if not separator:
        raise InstrumentationError('raw recipe lacks complete headers')
    lines = head.split(b'\r\n')
    headers = {}
    for line in lines[1:]:
        key, value = copy_stream.field(line)
        headers.setdefault(key, []).append(value)
    if headers.get(b'transfer-encoding') != [b'chunked']:
        raise InstrumentationError('recipe must carry exactly chunked')
    reader, chunks = copy_stream.Reader([body], 65536), []
    while True:
        size = copy_stream.chunk_size(reader.line())
        if not size:
            if reader.line() or reader.buffer:
                raise InstrumentationError('fixed recipe has trailers or extra bytes')
            return lines[0], headers, b''.join(chunks)
        chunks.append(reader.exact(size))
        if reader.exact(2) != b'\r\n':
            raise InstrumentationError('fixed recipe chunk lacks CRLF')


def framing_requests(command, *, body_limit, observer_capacity):
    """Actual public input bytes. Large generation requires explicit capacity.

    command is the independent valid write fixture, never a candidate output.
    The internal guard blocks this generator rather than changing a norm.
    """
    if type(body_limit) is not int or body_limit <= 0 or type(observer_capacity) is not int:
        raise MissingBinding('actual body limit and permitted input-generation capacity required')
    if body_limit + 1 > observer_capacity:
        raise MissingBinding('capacity is insufficient for the chunked over-limit input')
    obj = wire.strict_json(command)
    if not isinstance(obj, dict) or not isinstance(obj.get('id'), str) or not obj['id']:
        raise InstrumentationError('valid independent same-id write fixture required')
    if len(command) > body_limit:
        raise MissingBinding('valid CL+TE command fixture exceeds the actual configured body limit')
    def request(version, data, extra=b''):
        return (b'POST /v1/write ' + version + b'\r\nTransfer-Encoding: chunked\r\n' + extra +
                b'\r\n%x\r\n' % len(data) + data + b'\r\n0\r\n\r\n')
    return {'http10-te': request(b'HTTP/1.0', command),
            'http11-cl-te': request(b'HTTP/1.1', command, b'Content-Length: 1\r\n'),
            'chunked-over-limit': request(b'HTTP/1.1', b' ' * (body_limit + 1))}


def framing(obs):
    rows = seq(obs, 'cases')
    wanted = {'http10-te', 'http11-cl-te', 'chunked-over-limit'}
    if {need(row, 'case') for row in rows} != wanted or len(rows) != len(wanted):
        raise MissingBinding('all three raw framing cases required')
    errors = []
    for row in rows:
        raw = wire.bytes_from(need(row, 'request_b64'))
        case = row['case']
        # Recipes are fixed public HTTP inputs, not output aliases or a private
        # vector envelope. Different ordinary command fixtures are permitted.
        line, headers, decoded = chunked_request(raw)
        version = b'HTTP/1.0' if case == 'http10-te' else b'HTTP/1.1'
        if line != b'POST /v1/write ' + version:
            raise InstrumentationError('wrong raw method/path/version recipe')
        r = reply(row, 'response')
        if flag(need(row, 'response'), 'client_half_closed'):
            raise InstrumentationError('client EOF cannot establish the mandatory server framing close')
        if not r['closed']:
            errors.append('framing case did not close the connection')
        if case == 'http11-cl-te':
            if headers.get(b'content-length') != [b'1'] or len(decoded) <= 1:
                raise InstrumentationError('CL+TE control did not actually include Content-Length')
            if not same(wire.strict_json(decoded), need(obs, 'command')):
                raise InstrumentationError('CL+TE decoded command differs from independent fixture')
            if len(decoded) > integer(obs, 'body_limit', 1):
                raise InstrumentationError('ordinary CL+TE fixture instead triggers a body-size refusal')
            errors += success(r, need(row, 'expected_answer'))
            errors += unchanged(row, 'expected_after', 'after', 'CL+TE applied state/id differs')
        elif case == 'http10-te':
            errors += wire.fault_errors(r, 400, 'badrequest')
            errors += effects_absent(row)
        else:
            if len(decoded) <= integer(obs, 'body_limit', 1):
                raise InstrumentationError('chunked input did not exceed actual body limit')
            errors += wire.fault_errors(r, 413, 'toolarge', required={'limit': integer(obs, 'body_limit', 1)})
            errors += effects_absent(row)
    errors += success(reply(obs, 'valid_control'), need(obs, 'valid_control_expected'))
    return errors


def copy_rows(raw):
    """Writer copy grammar, including damaged-body rows with known versions.

    This is NOT import/restore validation: unreadable input is refused there.
    index_lost cannot acquire an invented version or disappear from a completed
    copy. Its native failure is checked separately by backup_rows.
    """
    if not isinstance(raw, bytes) or not raw.endswith(b'\n'):
        raise copy_stream.CopyProtocolError('copy is not LF-terminated UTF-8 JSONL')
    try:
        lines = [wire.strict_json(line) for line in raw[:-1].split(b'\n')]
    except (ValueError, UnicodeError) as exc:
        raise copy_stream.CopyProtocolError('invalid strict copy JSONL') from exc
    if not lines or not isinstance(lines[0], dict):
        raise copy_stream.CopyProtocolError('missing copy header')
    head = lines[0]
    dec = lambda x: isinstance(x, str) and re.fullmatch(r'0|[1-9][0-9]{0,19}', x)
    if (set(head) != {'format', 'version', 'index'} or head['format'] != 'w2c-configstore-copy' or
            type(head['version']) is not int or head['version'] != 1 or not dec(head['index'])):
        raise copy_stream.CopyProtocolError('invalid closed copy header')
    previous = None
    for row in lines[1:]:
        if not isinstance(row, dict):
            raise copy_stream.CopyProtocolError('copy row is not an object')
        key = row.get('key')
        if (not isinstance(key, str) or not key or key.startswith('/') or '..' in key.split('/') or
                not dec(row.get('index'))):
            raise copy_stream.CopyProtocolError('invalid copy key/version')
        try:
            encoded = key.encode('utf-8')
        except UnicodeError as exc:
            raise copy_stream.CopyProtocolError('copy key is not UTF-8') from exc
        if previous is not None and encoded <= previous:
            raise copy_stream.CopyProtocolError('copy writer omitted distinct UTF-8 key order')
        previous = encoded
        if int(row['index']) > int(head['index']):
            raise copy_stream.CopyProtocolError('copy row index exceeds snapshot')
        if set(row) == {'key', 'items', 'index'}:
            if not isinstance(row['items'], dict) or any(not isinstance(v, str) for v in row['items'].values()):
                raise copy_stream.CopyProtocolError('copy items are not strings')
            try:
                for name, value in row['items'].items():
                    name.encode('utf-8')
                    value.encode('utf-8')
            except UnicodeError as exc:
                raise copy_stream.CopyProtocolError('copy items contain a lone surrogate') from exc
        elif set(row) == {'key', 'items', 'index', 'unreadable'}:
            if row['items'] is not None or row['unreadable'] is not True:
                raise copy_stream.CopyProtocolError('invalid unreadable copy row')
        else:
            raise copy_stream.CopyProtocolError('invalid closed copy row fields')
    return head, lines[1:]


def backup_rows(obs):
    active(obs, 'independent_fixture_activated')
    if need(obs, 'fixture_operation') != 'stand.spoil-row':
        raise MissingBinding('legitimate stand.spoil-row body/index carrier required; no private disk layout')
    errors = []
    known = need(obs, 'known_version')
    if integer(known, 'backup_exit') != 0:
        errors.append('backup of known-version damaged-body row failed')
    raw = wire.bytes_from(need(known, 'artifact_b64'))
    _, rows = copy_rows(raw)
    expected = need(known, 'expected_rows')
    damaged_key, damaged_version = need(known, 'damaged_key'), need(known, 'damaged_version')
    if (not isinstance(expected, list) or not expected or
            not any(isinstance(row, dict) and row.get('key') == damaged_key and
                    row.get('index') == damaged_version and row.get('unreadable') is True and
                    row.get('items') is None and isinstance(damaged_version, str) and damaged_version
                    for row in expected)):
        raise InstrumentationError('the independently corrupted known-version row was never exercised')
    if not same(rows, expected):
        errors.append('copy omitted/changed row, unreadable flag or exact version')
    if integer(known, 'artifact_mode') != 0o600 or not flag(known, 'atomic_publication_observed'):
        errors.append('CLI copy did not publish atomically with 0600 mode')
    lost = need(obs, 'index_lost')
    active(lost, 'log_observed')
    if integer(lost, 'backup_exit') == 0:
        errors.append('index_lost CLI backup falsely succeeded')
    errors += unchanged(lost, 'previous_artifact', 'artifact_after', 'failed backup replaced previous artifact')
    errors += unchanged(lost, 'before', 'after', 'failed copy changed data/id')
    exchange = need(lost, 'http')
    raw = wire.bytes_from(need(exchange, 'raw_b64'))
    # A read failure may be an honest 503 before any 200, or incomplete output
    # after 200. A completed (possibly omitted/fake-index) copy is never lawful.
    if raw.startswith(b'HTTP/1.1 503 ') or raw.startswith(b'HTTP/1.0 503 '):
        errors += wire.fault_errors(reply(lost, 'http'), 503, 'unavailable')
    else:
        if not flag(exchange, 'closed'):
            raise MissingBinding('post-200 copy failure needs actual termination/cancellation observation')
        exposed_body = bytearray()
        try:
            body = copy_stream.CopyBody([raw])
            for part in body.parts():
                exposed_body.extend(part)
        except copy_stream.CopyProtocolError as exc:
            if str(exc) not in ('incomplete HTTP line', 'incomplete framed copy body'):
                errors.append('post-200 failure also violated response framing/media: ' + str(exc))
        else:
            errors.append('index_lost returned a completed successful copy')
        if re.search(rb'(?:^|\r\n)HTTP/1\.[01] ', raw.partition(b'\r\n\r\n')[2]):
            errors.append('second HTTP response after exposed200')
        for line in bytes(exposed_body).split(b'\n')[:-1]:
            try:
                item = wire.strict_json(line)
            except (ValueError, UnicodeError):
                errors.append('malformed complete JSONL line before copy failure')
                continue
            if isinstance(item, dict) and 'kind' in item:
                errors.append('Fault object appended after exposed200')
        if not raw.startswith((b'HTTP/1.1 200 ', b'HTTP/1.0 200 ')):
            errors.append('copy failure was neither honest pre-200503 nor incomplete exposed200')
    # Import/restore of an unreadable row is a separate existing N4 refusal.
    for operation in ('import', 'restore'):
        row = need(obs, operation)
        if integer(row, 'exit') == 0:
            errors.append(operation + ' accepted unreadable input')
        errors += effects_absent(row)
    return errors


CHECKS = dict(zip(REGISTRY, (connections, input_drain, lock_wait, barrier_replay,
                           data_ownership, cost_id, framing, backup_rows)))


def judge(probe, observations):
    """Execute the named checker, retaining checking errors and missing inputs.

    Return is an OBSERVATION result. No dictionary field can turn this into a
    qualified native execution. That requires an actually supplied and approved
    isolated provider/context and an independent execution receipt.
    """
    if probe not in CHECKS:
        raise ValueError('unknown named probe')
    try:
        errors = CHECKS[probe](observations)
        return dict(status='OBSERVATION_RED' if errors else 'OBSERVATION_PASS',
                    errors=errors, missing=[])
    except MissingBinding as exc:
        return dict(status='NOT_EXECUTED', errors=[], missing=[str(exc)])
    except copy_stream.ObservationLimit as exc:
        return dict(status='NOT_EXECUTED', errors=[], missing=['observer capacity/decoder binding: ' + str(exc)])
    except (InstrumentationError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        return dict(status='INSTRUMENT_ERROR', errors=[str(exc)], missing=[])
    except (copy_stream.CopyProtocolError, ValueError, UnicodeError) as exc:
        return dict(status='OBSERVATION_RED', errors=[str(exc)], missing=[])


def report(capture=None, only=None):
    capture = capture or {}
    if not isinstance(capture, dict):
        raise InstrumentationError('capture must be an object')
    if capture and (capture.get('format') != 'cammeta-store-probes-v1' or capture.get('source_pin') != SOURCE):
        raise InstrumentationError('capture format/Source identity mismatch; no fallback/repin')
    observations = capture.get('observations', {})
    if not isinstance(observations, dict) or set(observations) - CHECKS.keys():
        raise InstrumentationError('unknown probe observations')
    if '05-data-ownership' in observations and capture.get('ownership_source_pin') != OWNERSHIP_SOURCE:
        raise InstrumentationError('probe5 requires its NEW published ownership Source identity, not old a08')
    selected = list(REGISTRY) if not only else only
    if any(key not in REGISTRY for key in selected) or len(set(selected)) != len(selected):
        raise InstrumentationError('unknown or duplicate named probe selection')
    rows = []
    for key in selected:
        info = REGISTRY[key]
        result = judge(key, observations[key]) if key in observations else dict(
            status='NOT_EXECUTED', errors=[], missing=['no actual observation capture for ' + key])
        rows.append(dict(id=key, **info, observation=result,
                         native_status='NOT_EXECUTED', native_missing=list(info['required']),
                         production_status='NOT_EXECUTED'))
    return dict(source_pin=SOURCE, source21_pin=SOURCE21, ownership_source_pin=OWNERSHIP_SOURCE, owner_literal_pin=OWNER,
                capture_scope=capture.get('scope', 'missing-native-bindings'), probes=rows,
                observation_checks=sum(r['observation']['status'].startswith('OBSERVATION_') for r in rows),
                native_executed=0, production_passed=0, production_budgets=None,
                qualification='No native/production activation from capture fields; explicit provider integration required')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', choices=REGISTRY, action='append')
    parser.add_argument('--capture', type=Path, help='internal independent raw observation capture; not acceptance.yaml')
    parser.add_argument('--list', action='store_true', help='full named registry and concrete prerequisites')
    args = parser.parse_args(argv)
    try:
        capture = None
        digest = None
        if args.capture is not None and not args.list:
            raw = args.capture.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            capture = wire.strict_json(raw)
        result = report(capture, args.probe)
        result['capture_sha256'] = digest
        result['runner_files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            Path(__file__), Path(wire.__file__), Path(fitness.__file__), Path(copy_stream.__file__))}
        print(json.dumps(result, ensure_ascii=True, indent=2))
        if args.list:
            return 0
        statuses = [r['observation']['status'] for r in result['probes']]
        return 2 if 'INSTRUMENT_ERROR' in statuses else 1 if 'OBSERVATION_RED' in statuses else 3 if 'NOT_EXECUTED' in statuses else 0
    except (OSError, ValueError, InstrumentationError) as exc:
        print(json.dumps(dict(status='INSTRUMENT_ERROR', error=str(exc), native_executed=0)))
        return 2


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
