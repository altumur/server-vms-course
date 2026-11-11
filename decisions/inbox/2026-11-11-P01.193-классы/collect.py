#!/usr/bin/env python3
"""Read saved court JSON and pinned Git objects; never invoke submitted code."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
COURT = Path('/home/pilot/owner-receipts/P01.192-court-engine2-20261111')
E2 = Path('/home/pilot/owner-receipts/P01.245-engine2-src-20261111')
J_REPO = Path('/home/pilot/run-p0226-pair-20261111/ji-4694190a17/JI.git')
J = '49e622795ca96b2e73904f1da5d203f2d103b2d5'
M_REPO = Path('/home/pilot/run-p0226-pair-20261111/pair-4694190a178f/M.git')
M = 'bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae'
MM_REPO = Path('/srv/minimax-loop/runs/p01-b-raft-bf8462085c08/work')
MM = '77b90bef744b97519fd73958cc2b6e308463b1fb'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '-c', f'safe.directory={repo}',
                                    '-C', str(repo), *args])


def tsv(name, rows, fields):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fields, delimiter='\t', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def classify(target, kind, x):
    line = x.get('line')
    if target == 'P/01.3/group':
        return 'E1', 'движок'
    if target == 'P/01.2/rights':
        return ('E3' if line in (21, 33) else 'E2'), 'движок'
    if target == 'P/01.1/inproc':
        return 'K1', 'кандидат'
    if target == 'P/01/vectors-crl':
        return 'K2', 'кандидат'
    if target == 'P/01/vectors-revoked':
        return ('K3' if line == 16 else 'K4'), 'кандидат'
    if target == 'P/01/vectors-log-mask':
        return 'K5', 'кандидат'
    if target == 'P/01.3/daemon':
        return ('N1', 'норма') if kind == 'rows' else ('K6', 'кандидат')
    if target == 'P/01.1/door':
        return ('K7', 'кандидат') if line in (9, 11) else ('E4', 'движок')
    raise ValueError((target, kind, x))


def main():
    files, totals, reds, others = {}, [], [], []
    for cand in ('claude', 'attempt6'):
        for mode in ('out', 'out-diag'):
            reports = sorted((COURT / mode / cand).glob('*/engine.json'))
            assert len(reports) == 12, (cand, mode, len(reports))
            for p in reports:
                raw = p.read_bytes()
                files[str(p)] = sha(raw)
                d = json.loads(raw)
                rec = dict(candidate=cand, mode=mode, target=d['target'],
                           result=d.get('result', 'NO_RESULT'), error=d.get('error', ''))
                for kind in ('steps', 'rows', 'entries'):
                    counts = Counter(x['result'] for x in d.get(kind, []))
                    for word in ('GREEN', 'red', 'not_executed', 'blocked', 'not_applicable'):
                        rec[f'{kind}_{word}'] = counts[word]
                    if mode != 'out-diag':
                        continue
                    for x in d.get(kind, []):
                        row = dict(candidate=cand, target=d['target'], kind=kind,
                                   table=x.get('table', ''), line=x.get('line', ''),
                                   scenario=x.get('scenario', x.get('case', x.get('name', x.get('id', '')))),
                                   step=x.get('step', ''), variant=x.get('variant', ''),
                                   original_class=x.get('class', ''),
                                   detail=x.get('detail', ''), reason=x.get('reason', ''))
                        if x['result'] == 'red':
                            row['package'], row['classification'] = classify(d['target'], kind, x)
                            row['report'] = str(p.relative_to(COURT))
                            reds.append(row)
                        elif x['result'] != 'GREEN':
                            row['result'] = x['result']
                            others.append(row)
                totals.append(rec)
    counts = Counter((r['candidate'], r['classification']) for r in reds)
    assert len(reds) == 62 and Counter(r['candidate'] for r in reds) == {'claude': 21, 'attempt6': 41}
    assert all(r['original_class'] == 'implementation' for r in reds)
    fields = ['candidate', 'target', 'kind', 'table', 'line', 'scenario', 'step',
              'variant', 'original_class', 'detail', 'reason']
    tsv('red-cases.tsv', reds, fields + ['package', 'classification', 'report'])
    tsv('unexecuted.tsv', others, fields + ['result'])
    tsv('counts.tsv', totals, list(totals[0]))

    checked = []
    for ln in (E2 / 'SHA256SUMS').read_text().splitlines():
        digest, rel = ln.split(maxsplit=1)
        rel = rel.lstrip('*')
        b = (E2 / rel).read_bytes()
        assert sha(b) == digest, rel
        checked.append(rel)
    assert len(checked) == 52

    pinned = {}
    for repo, pin, paths in (
        (J_REPO, J, ['Platform/common/acceptance/README.md',
                     'Platform/common/acceptance/PROFILE.md',
                     'Platform/common/acceptance/spec/acceptance.norms.md',
                     'Platform/common/acceptance/tls/README.md',
                     'Platform/common/acceptance/forms/targets.routing.tsv',
                     'Platform/01-store/acceptance/2/README.md',
                     'Platform/01-store/acceptance/2/scenarios.tsv',
                     'Platform/01-store/acceptance/3/README.md',
                     'Platform/01-store/acceptance/3/inputs/group.json',
                     'Platform/common/acceptance/forms/process-1.1.scenarios.tsv',
                     'Platform/common/acceptance/forms/process-1.3.scenarios.tsv',
                     'Platform/common/acceptance/forms/extra.tsv',
                     'Platform/common/acceptance/forms/extra.scenarios.tsv',
                     'Platform/01-store/spec/production-acceptance.md',
                     'Platform/common/vectors/wire.tsv',
                     'Platform/common/vectors/crl/README.md',
                     'Platform/common/vectors/crl/cases.tsv',
                     'Platform/common/vectors/revoked/README.md',
                     'Platform/common/vectors/revoked/cases.tsv',
                     'Platform/common/vectors/log-mask/README.md',
                     'Platform/common/vectors/log-mask/cases.tsv',
                     'Platform/common/vectors/secret-in/fields.yaml']),
        (M_REPO, M, ['Platform/01-store/spec/01.3-store.norms.md',
                     'Platform/01-store/spec/01.1-store.norms.md']),
        (MM_REPO, MM, ['01-store/acceptance.yaml', '01-store/group/tls.go',
                       '01-store/daemon/group_start.go', '01-store/door/authorization.go',
                       '01-store/cmd/door-adapter/main.go',
                       '01-store/internal/revocation/revoked.go',
                       '01-store/internal/logmask/mask.go',
                       '01-store/cmd/vectors/main.go',
                       '01-store/copy/timestamp.go', '01-store/copy/plan.go'])):
        for path in paths:
            b = git(repo, 'show', f'{pin}:{path}')
            pinned[f'{pin}:{path}'] = {'bytes': len(b), 'sha256': sha(b)}

    evidence = dict(
        course_base='385c25b353412d0c78d58b49555e16607704e815', J=J, M=M, candidate_MM=MM,
        engine2_archive_sha256='b244d533b36d08a7c0a7a2a64d75f1dfb8614c7efe33526e7a82d96a610c3bea',
        engine2_source_manifest_checked=checked,
        saved_reports_sha256=files, pinned_files=pinned,
        red_total=len(reds), red_by_candidate_and_class={f'{a}/{b}': n for (a, b), n in sorted(counts.items())},
        red_by_package=dict(sorted(Counter(r['package'] for r in reds).items())),
        non_green_non_red=len(others),
        prohibited_executions=0,
        method='Only saved JSON, SHA-256, and git show. Classification is a reading judgment; see INDEX.md.')
    (OUT / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: evidence[k] for k in ('red_total', 'red_by_candidate_and_class', 'red_by_package', 'non_green_non_red')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
