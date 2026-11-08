"""Internal Z21 observation checks; no candidate launch or public profile DSL.

These checks consume independently qualified observations. Passing an owned
fixture proves the checker control, not a production case or a fault provider.
"""
from dataclasses import dataclass
from decimal import Decimal
import re



def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is bool and type(b) is bool and a == b
    if isinstance(a, (int, Decimal)) and isinstance(b, (int, Decimal)):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


DECISION = 'c13201be303ca0807632493473b4d75ab344463d'
CASES = {
    'RUN-W01': ('storage', 'workload', 'cost'),
    'RUN-W02': ('storage', 'import', 'workload', 'cost'),
    'RUN-W03': ('clock', 'id-accounting', 'reopen'),
    'RUN-W04': ('memory', 'id-accounting', 'workload', 'cache-gc'),
    'RUN-T01': ('duplex', 'drain'),
    'RUN-T02': ('duplex', 'drain'),
    'RUN-T03': ('clock', 'duplex', 'phase'),
    'RUN-L01': ('copy-artifact', 'output-failure', 'reopen'),
    'RUN-L02': ('sink-latch', 'mutation-lock', 'progress', 'cancel'),
    'RUN-L03': ('sink-latch', 'admission', 'lifecycle', 'stop'),
    'RUN-F01': ('pre-effect-fault', 'medium-oracle', 'reopen'),
    'RUN-F02': ('uncertain-medium-fault', 'medium-oracle', 'reopen'),
    'RUN-F03': ('complete-record-fault', 'barrier', 'reopen'),
    'RUN-F04': ('pre-effect-fault', 'complete-record-fault', 'admission', 'reopen'),
    'RUN-H01': ('copy-artifact', 'import', 'reopen'),
    'RUN-H02': ('copy-http', 'copy-artifact', 'snapshot'),
    'RUN-H03': ('copy-http', 'copy-artifact', 'output-failure', 'cancel'),
}
BUDGETS = {
    'RUN-W01': ('workload', 'resources', 'measurement'),
    'RUN-W02': ('workload', 'resources', 'measurement'),
    'RUN-W03': ('measurement',),
    'RUN-W04': ('workload', 'resources', 'cache-gc', 'measurement'),
    'RUN-T01': ('drain', 'measurement'),
    'RUN-T02': ('drain', 'measurement'),
    'RUN-T03': ('phase', 'measurement'),
    'RUN-L02': ('lock-output-cancel', 'measurement'),
    'RUN-L03': ('stop-manager-margin', 'measurement'),
    'RUN-H02': ('copy-output-cancel', 'measurement'),
    'RUN-H03': ('copy-output-cancel', 'measurement'),
}
SOURCE_REFS = {
    'RUN-W01': ('P/01.1-R148',), 'RUN-W02': ('P/01.1-R148',),
    'RUN-W03': ('P/01.1-R141',), 'RUN-W04': ('P/01.1-R141',),
    'RUN-T01': ('P/01.1-R050', 'P/01.1-R147'),
    'RUN-T02': ('P/01.1-R050', 'P/01.1-R147'),
    'RUN-T03': ('P/01.1-R147', 'P/01.1-R054'),
    'RUN-L01': ('P/01.3-R018', 'P/01.3-R034'),
    'RUN-L02': ('P/01.3-R034',), 'RUN-L03': ('P/01.3-R034',),
    'RUN-F01': ('P/01.1-R144',), 'RUN-F02': ('P/01.1-R144',),
    'RUN-F03': ('P/01.1-R144',), 'RUN-F04': ('P/01.1-R144',),
    'RUN-H01': ('P/01.3-R018',), 'RUN-H02': ('P/01.3-R033',),
    'RUN-H03': ('P/01.3-R033', 'P/01.3-R034'),
}


class MissingBinding(ValueError):
    """The dependent observation is blocked/NotExecuted, never PASS."""


class InstrumentationError(ValueError):
    """Inactive/contradictory observation, not a business implementation refusal."""


def number(value, *, positive=False):
    if type(value) not in (int, float, Decimal):
        raise InstrumentationError('a finite numeric observation is required')
    value = Decimal(str(value))
    if not value.is_finite():
        raise InstrumentationError('a finite numeric observation is required')
    if value < 0 or positive and value == 0:
        raise InstrumentationError('invalid observation/budget sign')
    return value


@dataclass(frozen=True)
class PhaseBudgets:
    idle: object
    header: object
    body: object
    drain: object
    drain_bytes: int

    def __post_init__(self):
        for name in ('idle', 'header', 'body', 'drain'):
            object.__setattr__(self, name, number(getattr(self, name), positive=True))
        if type(self.drain_bytes) is not int or self.drain_bytes <= 0:
            raise InstrumentationError('drain bytes must be a declared positive integer')


def event(value, name):
    if value is None:
        raise MissingBinding('missing independently observed ' + name)
    return number(value)


def phase_deadline(phase, budgets, *, accepted_at=None, previous_response_complete_at=None,
                   first_request_byte_at=None, headers_complete_at=None,
                   has_body=True, refusal_sent_complete_at=None):
    if not isinstance(budgets, PhaseBudgets):
        raise MissingBinding('actual finite phase budgets are required')
    if type(has_body) is not bool:
        raise InstrumentationError('has_body must be the observed boolean framing result')
    if phase == 'idle':
        start = (previous_response_complete_at if previous_response_complete_at is not None else accepted_at)
    elif phase == 'header':
        start = first_request_byte_at
    elif phase == 'body':
        if not has_body:
            return None
        # No first-body-byte argument: waiting for it must not defer this end.
        start = headers_complete_at
    elif phase == 'drain':
        start = refusal_sent_complete_at
    else:
        raise ValueError('unknown input phase')
    return event(start, phase + ' phase start') + getattr(budgets, phase)


def phase_close_errors(deadline, closed_at, *, measurement_allowance):
    if deadline is None:
        raise MissingBinding('this observation has no active phase deadline')
    close = event(closed_at, 'server close')
    allowance = number(measurement_allowance)
    return ['server close exceeds declared phase deadline'] if close > number(deadline) + allowance else []


def timeout_outcome(*, valid_request_line, response_started, eof=False):
    if any(type(v) is not bool for v in (valid_request_line, response_started, eof)):
        raise InstrumentationError('timeout observation flags must be boolean')
    # Existing R054 EOF/truncation does not acquire a new HTTP error or an id.
    reply = None if eof or response_started or not valid_request_line else dict(status=400, kind='badrequest')
    return dict(reply=reply, close=True, execute=False, occupy_id=False,
                connection_close_header=reply is not None)


def input_timeout_errors(*, valid_request_line, response_started, eof, actual_reply, request_method,
                         actual_closed, executed, occupied_id, connection_close_header):
    """actual_reply denotes a NEW reply emitted at this timeout/EOF event.

    The prior response, if already exposed, is not counted as a second reply.
    Header/line validity and effects must be independent actual observations.
    """
    flags = (actual_closed, executed, occupied_id, connection_close_header)
    if any(type(value) is not bool for value in flags):
        raise InstrumentationError('actual close/effect/header observations must be boolean')
    expected = timeout_outcome(valid_request_line=valid_request_line,
                               response_started=response_started, eof=eof)
    errors = []
    if expected['reply'] is None:
        if actual_reply is not None:
            errors.append('EOF/incomplete line/already started response must not emit a new Fault')
    else:
        if not isinstance(request_method, str) or not request_method:
            raise MissingBinding('a completed request line must supply its actual method')
        if request_method == 'HEAD':
            # HEAD exposes no JSON kind: judge status/headers/bodylessness,
            # never demand an unobservable Fault-body field.
            correct = (isinstance(actual_reply, tuple) and len(actual_reply) == 2 and
                       type(actual_reply[0]) is int and actual_reply == (400, b''))
        else:
            correct = reply_is(actual_reply, 400, 'badrequest')
        if not correct or not connection_close_header:
            errors.append('input timeout needs the existing400 BadRequestFault/HEAD form and Connection:close')
    if not actual_closed or executed or occupied_id:
        errors.append('timed out/incomplete input must close without execution/id occupation')
    return errors


def early_refusal_errors(budgets, *, latch_activated, refusal_sent_complete_at,
                         refusal_received_complete_at, drain_started_at,
                         sender_released_at, closed_at, drained_bytes, measurement_allowance):
    if type(latch_activated) is not bool or not latch_activated:
        raise InstrumentationError('duplex sender latch was not independently activated')
    sent = event(refusal_sent_complete_at, 'complete refusal send')
    received = event(refusal_received_complete_at, 'complete refusal at client')
    drain = event(drain_started_at, 'raw drain start')
    release = event(sender_released_at, 'continued sender release')
    if type(drained_bytes) is not int or drained_bytes < 0:
        raise InstrumentationError('raw HTTP-stream drain count must be observed')
    errors = []
    if drain < sent:
        errors.append('raw drain precedes the complete refusal send')
    if release < received:
        errors.append('continued sender latch released before complete client refusal receipt')
    # No artificial client acknowledgement: server drain may already run while
    # the client is scheduling its read of the complete, already sent refusal.
    deadline = phase_deadline('drain', budgets, refusal_sent_complete_at=sent)
    errors += phase_close_errors(deadline, closed_at, measurement_allowance=measurement_allowance)
    if drained_bytes > budgets.drain_bytes:
        errors.append('raw drain exceeds declared byte bound')
    return errors


def reply_is(reply, status, kind):
    return (isinstance(reply, tuple) and len(reply) == 2 and type(reply[0]) is int and
            reply[0] == status and isinstance(reply[1], dict) and reply[1].get('kind') == kind)


def barrier_errors(stage, *, activated, before, published, after, reopened, reply,
                   repeated_failure=None, replay=None, first_answer=None, medium_allows=None,
                   repeated_after=None, repeated_reopened=None, retry_after=None, retry_reopened=None,
                   post_observation_order=None):
    """Compare qualified BUSINESS snapshots, including corresponding applied ids.

    Caller-provided snapshots exclude legitimate admission metadata and include
    the full batch plus its ids. The complete-record/medium premise must come
    from the independent provider, never from EIO/Barrier names or this helper.
    """
    if type(activated) is not bool or not activated:
        raise InstrumentationError('fault activation/stage is not independently proved')
    if any(x is None for x in (before, published, after, reopened)):
        raise MissingBinding('business/id/reopen observations are required')
    if stage not in ('pre-effect', 'uncertain-medium', 'complete-record'):
        raise InstrumentationError('unknown qualified fault stage')
    errors = []
    if stage == 'pre-effect':
        if not reply_is(reply, 503, 'unavailable'):
            errors.append('proven pre-effect refusal must be unavailable')
        if not same(before, after) or not same(before, reopened):
            errors.append('pre-effect refusal changed business state/version/applied-id')
    elif stage == 'uncertain-medium':
        if not reply_is(reply, 503, 'ambiguous'):
            errors.append('uncertain medium must not promise absence or success')
        if not callable(medium_allows):
            raise MissingBinding('a separately qualified medium recovery oracle is required')
        allowed = medium_allows(after, reopened)
        if type(allowed) is not bool:
            raise InstrumentationError('medium oracle must return a qualified boolean observation')
        if not allowed:
            errors.append('observed state violates the qualified whole-operation medium model')
    else:
        if not reply_is(reply, 503, 'ambiguous'):
            errors.append('complete-record barrier error must be ambiguous')
        if not same(published, after) or not same(published, reopened):
            errors.append('complete record must publish/recover whole business state and matching id')
        if repeated_failure is None or replay is None or first_answer is None:
            raise MissingBinding('repeated barrier failure and same-id retry observations are required')
        if any(value is None for value in (repeated_after, repeated_reopened, retry_after, retry_reopened,
                                           post_observation_order)):
            raise MissingBinding('distinct post-failed-barrier and post-retry business/id/reopen observations are required')
        # Independent judge event sequence, never business version arithmetic:
        # failure reply, live state, reopened state, successful retry reply,
        # live final state, reopened final state. Old initial snapshots cannot
        # silently stand in for these explicitly required post-phase receipts.
        order = post_observation_order
        if (not isinstance(order, tuple) or len(order) != 6 or
                any(type(value) is not int or value <= 0 for value in order) or
                any(a >= b for a, b in zip(order, order[1:]))):
            raise InstrumentationError('post-retry observations lack a distinct qualified event order')
        for label, state in (('repeated barrier failure', repeated_after),
                             ('repeated barrier reopen', repeated_reopened),
                             ('successful same-id retry', retry_after), ('successful retry reopen', retry_reopened)):
            if not same(published, state):
                errors.append(label + ' changed business state/version/applied-id')
        if not reply_is(repeated_failure, 503, 'ambiguous'):
            errors.append('repeated barrier error must remain ambiguous')
        if (not isinstance(replay, tuple) or len(replay) != 2 or type(replay[0]) is not int or
                replay[0] != 200 or not isinstance(replay[1], dict) or replay[1].get('again') is not True):
            errors.append('same-id retry must return original answer with again')
        else:
            answer = {k: v for k, v in replay[1].items() if k != 'again'}
            if not same(answer, first_answer):
                errors.append('same-id retry changed the original answer/version')
    return errors


def copy_route_outcome(method, role, *, framing_valid=True, snapshot_available=True):
    """Expected route slice only; framing Fault detail remains its Source owner.

    This function cannot grant admin from a forwarded/header role and does not
    judge unrelated paths or wrap a second Fault after already exposed 200.
    """
    if type(framing_valid) is not bool or type(snapshot_available) is not bool:
        raise InstrumentationError('framing/snapshot observations must be boolean')
    if not framing_valid:
        raise MissingBinding('preceding framing outcome belongs to its exact parser/fault owner')
    if method != 'GET':
        return dict(status=405, kind='badrequest', allow='GET', bodyless=method == 'HEAD')
    if role != 'admin.sock':
        return dict(status=403, kind='forbidden')
    return dict(status=200, media='application/x-ndjson') if snapshot_available else dict(status=503, kind='unavailable')


def copy_route_errors(method, role, *, actual_status, actual_kind=None, allow=None,
                      body=None, framing_valid=True, snapshot_available=True):
    expected = copy_route_outcome(method, role, framing_valid=framing_valid,
                                  snapshot_available=snapshot_available)
    errors = []
    if type(actual_status) is not int or actual_status != expected['status']:
        errors.append('copy route status differs from the owned request/method/identity outcome')
    if expected.get('kind') is not None and not expected.get('bodyless') and actual_kind != expected['kind']:
        errors.append('copy refusal must use its existing owned Fault kind')
    if expected.get('allow') is not None and allow != 'GET':
        errors.append('unsupported copy method needs Allow:GET')
    if expected.get('bodyless'):
        if body is None:
            raise MissingBinding('HEAD needs an actual bodyless-response observation')
        if body != b'':
            errors.append('HEAD copy refusal must be bodyless')
    return errors


def qualification_plan(*, source_pin=None, tools_provider_receipt=None):
    """Honest complete current plan: no provider has been accepted by this API.

    A receipt name/counter is never enough to activate a production case. Actual
    integration must supply a reviewed provider, its environment and budgets;
    this component does not manufacture or auto-trust such a provider.
    """
    if source_pin is not None and not re.fullmatch('[0-9a-f]{40}', source_pin):
        raise ValueError('Source pin must be an exact full commit, distinct from the decision pin')
    rows = []
    for case, required in CASES.items():
        rows.append(dict(id=case, status='NOT_EXECUTED', applicable=True,
                         normative_refs=list(SOURCE_REFS[case]),
                         required_bindings=list(required), required_budget_inputs=list(BUDGETS.get(case, ())),
                         actual_budget=None, provider_qualified=False,
                         missing=['qualified actual provider/observations', *BUDGETS.get(case, ())],
                         reason='No independently accepted execution binding/environment supplied'))
    return dict(decision_pin=DECISION, normative_source_pin=source_pin,
                tools_provider_receipt=tools_provider_receipt, cases=rows,
                groups=len(rows), executed=0, passed=0, actual_budgets=None,
                candidate_launched=False, source_or_profile_fields_added=False,
                component_controls_are_not_production_results=True)
