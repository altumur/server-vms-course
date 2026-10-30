"""ADR-0099 properties, not an implementation test. Run only through CT103."""
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])
COURSE = '27e65d25bd5c5c003fd8d3ffe17ee58ca58797ef'
CONSOLE = '9849d2889fa565c8696caa1fab10639422dac104'
RANK = dict(none=0, view=1, edit=2, admin=3)

def extract(archive, target, commit, listing):
    target.mkdir()
    with tarfile.open(archive) as stream:
        assert stream.pax_headers['comment'] == commit
        stream.extractall(target, filter='data')
    result = {}
    for entry in filter(None, listing.read_bytes().split(b'\0')):
        meta, name = entry.split(b'\t', 1)
        mode, kind, wanted = meta.split()
        assert kind == b'blob' and mode != b'120000'
        raw = (target / name.decode()).read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == wanted.decode()
        result[name.decode()] = hashlib.sha256(raw).hexdigest()
    return result

def row(cap, scope, until=0):
    return dict(subject='role:R', cap=cap, scope=scope, until=until)

def role_level(rows, unit, *, unknown_membership=False, unknown_unit=False, now=1):
    """ADR tiers, with unchanged covers' unreadable-unit behavior from the gate."""
    rows = [r for r in rows if not r['until'] or now < r['until']]
    def maximum(items):
        return max((RANK[r['cap']] for r in items), default=None)
    level = maximum(r for r in rows if r['scope'] == 'unit:' + unit['id'])
    if level is not None:
        return level
    if not unknown_unit and unit.get('about'):
        level = maximum(r for r in rows if r['scope'] == 'unit:' + unit['about'])
        if level is not None:
            return level
    folders = [r for r in rows if r['scope'].startswith('folder:')]
    if folders and unknown_membership:
        return 0
    nearest = []
    for chain in unit.get('chains', []):
        for folder in chain:
            matches = [r for r in folders if r['scope'] == 'folder:' + folder]
            if matches:
                nearest.extend(matches)
                break
    level = maximum(nearest)
    if level is not None:
        return level
    labels = [] if unknown_unit else unit.get('labels', [])
    level = maximum(r for r in rows if r['scope'].startswith('labels:')
                    and set(r['scope'][7:].split(',')) <= set(labels))
    if level is not None:
        return level
    return maximum(r for r in rows if r['scope'] == '*') or 0

with tempfile.TemporaryDirectory(prefix='rv-adr99-') as directory:
    work = Path(directory)
    sources = extract(ROOT / 'course.tar', work / 'course', COURSE, ROOT / 'course.ls-tree')
    console_sources = extract(ROOT / 'console.tar', work / 'console', CONSOLE, ROOT / 'console.ls-tree')
    html = (work / 'console/index.html').read_text()
    cam_levels = json.loads(re.search(r'^  cam:(\[\[.*\]\]),$', html, re.M)[1])
    order = [v[0] for v in cam_levels]
    real_role = html[html.index('function accRoleLevel('):html.index('function accRoleCam(')]
    real_eff = html[html.index('function accEffIn('):html.index('function accEff(')]
    # Execute the exact Console functions, supplying only their data lookups.
    js = 'const ACC_LV={cam:' + json.dumps(cam_levels, ensure_ascii=False) + '};\n' + '''
const ACC_GF_DEF={cam:'dCam'},ACC_NOFOLDER=new Set();
function accRank(f,v){return v?ACC_LV[f].findIndex(x=>x[0]===v):-1}
function accObj(){return {type:'camera'}}
function accObjGroups(id){return id==='cam/root'?['D']:['F','G']}
function accChain(g){return g==='D'?['D']:[g,'D']}
function accUserRoles(u){return u.roles}
function accRole(id,st){return st[id]}
''' + real_role + real_eff + '''
const role=(lv)=>({g:{dCam:lv},objs:{},groups:{}});
const folders=role('FORBID');folders.groups={F:{cam:'MON'},G:{cam:'ONLY_ARCHIVE'}};
const st={live:role('MON'),archive:role('ONLY_ARCHIVE')};
const root=role('FULL');root.groups={D:{cam:'FORBID'}};
console.log(JSON.stringify({folder:accRoleLevel(folders,'cam/7','cam','D').lv,
 oneRole:accEffIn(st,{roles:['archive']},'cam/7','D').lv,
 twoRoles:accEffIn(st,{roles:['archive','live']},'cam/7','D').lv,
 rootOverride:accRoleLevel(root,'cam/root','cam','D').lv}));
'''
    script = OUT / 'console-oracle.js'
    script.write_text(js)
    proc = subprocess.run(['node', str(script)], capture_output=True, text=True, check=True, timeout=20)
    oracle = json.loads(proc.stdout)
    assert oracle == dict(folder='MON', oneRole='ONLY_ARCHIVE', twoRoles='MON', rootOverride='FORBID')

    # ADR-0097 §7/ADR-0099 §5 translation, with explicit none components.
    translated = dict(FORBID=(0, 0, 0), ONLY_ARCHIVE=(1, 0, 1), MON=(1, 1, 0),
                      ARCHIVE=(1, 1, 1), ARCH_MANAGE=(1, 1, 2), FULL=(2, 1, 2))
    mismatches = []
    for a, b in itertools.product(translated, repeat=2):
        selected = max((a, b), key=order.index)
        combined = tuple(max(x, y) for x, y in zip(translated[a], translated[b]))
        if combined != translated[selected]:
            mismatches.append(dict(a=a, b=b, console_level=selected,
                                   console_caps=translated[selected], platform_caps=combined))
    assert len(mismatches) == 2
    unit = dict(id='cam/7', labels=[], chains=[['F', 'root'], ['G', 'root']])
    archive_via_folders = role_level([row('none', 'folder:F'), row('view', 'folder:G')], unit)
    assert archive_via_folders == 1 and translated[oracle['folder']][2] == 0
    root_rank = role_level([row('edit', '*'), row('none', '*')], dict(unit, chains=[]))
    assert root_rank == 2 and translated[oracle['rootOverride']][0] == 0

    precise = [row('admin', '*'), row('none', 'unit:cam/7')]
    broken = copy.deepcopy(precise)
    broken[1]['until'] = 'unreadable'
    # The existing public caller discards malformed /doc/lines before may.
    filtered = [r for r in broken if type(r['until']) in (int, float)]
    assert role_level(precise, unit) == 0 and role_level(filtered, unit) == 3

    labelled = dict(id='cam/7', labels=['private'], chains=[])
    label_rows = [row('edit', '*'), row('none', 'labels:private')]
    assert role_level(label_rows, labelled) == 0
    assert role_level(label_rows, labelled, unknown_unit=True) == 2
    about = dict(id='det/5', about='cam/7', labels=[], chains=[])
    about_rows = [row('edit', '*'), row('none', 'unit:cam/7')]
    assert role_level(about_rows, about) == 0
    assert role_level(about_rows, about, unknown_unit=True) == 2

    controls = {}
    def control(name, condition):
        assert condition, name
        controls[name] = True
    control('unit_exception_wins', role_level(precise, unit) == 0)
    control('about_exception_wins', role_level(about_rows, about) == 0)
    control('nearest_folder', role_level([row('none', 'folder:F'), row('edit', 'folder:root')],
                                        dict(unit, chains=[['F', 'root']])) == 0)
    control('max_of_memberships', role_level([row('none', 'folder:F'), row('edit', 'folder:G')], unit) == 2)
    control('same_tier_max', role_level([row('none', 'unit:cam/7'), row('view', 'unit:cam/7')], unit) == 1)
    control('folder_unknown_denies_role', role_level([row('admin', '*'), row('none', 'folder:F')],
                                                    unit, unknown_membership=True) == 0)
    control('empty_membership_is_not_failure', role_level([row('admin', '*'), row('none', 'folder:F')],
                                                        dict(unit, chains=[])) == 3)
    control('expired_exception_falls_back', role_level([row('admin', '*'), row('none', 'unit:cam/7', until=1)], unit) == 3)
    control('direct_admin_remains_independent', max(3, role_level(precise, unit)) == 3)
    control('second_role_can_override_none', max(role_level(precise, unit), 1) == 1)
    monotonic = 0
    for initial, added, requested in itertools.product(range(4), range(4), (1, 2, 3)):
        assert not (initial >= requested) or max(initial, added) >= requested
        monotonic += 1
    control('role_addition_platform_monotone', monotonic == 48)
    control('console_addition_drops_archive', translated[oracle['oneRole']][2] == 1
            and translated[oracle['twoRoles']][2] == 0)
    control('root_scope_collision_reproduced', root_rank == 2)
    witnesses = dict(
        non_homomorphic_translation=dict(oracle=oracle, ordered_pairs_checked=36, mismatches=mismatches,
                                         rec_rank_from_folders=archive_via_folders),
        malformed_exception=dict(valid_rank=0, skip_line_rank=3, bad_line=broken[1]),
        unreadable_target=dict(labels=dict(readable=0, unreadable=2), about=dict(readable=0, unreadable=2)),
        root_scope_collision=dict(console_level=oracle['rootOverride'], console_cam_rank=0,
                                  platform_cam_rank=root_rank))
    result = dict(green=True, SUT=0, course=COURSE, console=CONSOLE, source_sha256=sources,
                  console_source_sha256=console_sources, witnesses=witnesses, controls=controls,
                  model_sha256=hashlib.sha256((ROOT / 'RUN.py').read_bytes()).hexdigest())
    (OUT / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(green=True, SUT=0, sources=len(sources), controls=len(controls),
                         monotonic_cases=monotonic, witnesses=witnesses), ensure_ascii=False), flush=True)
