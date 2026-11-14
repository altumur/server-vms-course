"""Bind P02.72 classifications plus the accepted OBSH.97 fixture review."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
B=Path(sys.argv[1]).resolve()
C=(B/'C.txt').read_text().strip()
prior=Path('/home/pilot/P02.72-evidence')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
delta=json.loads((B/'FILTER-DELTA.json').read_text())
old=json.loads((prior/'FILTER-DELTA.json').read_text())
assert delta['from']==old['from']=='a494be12d54c2e596467c1508973da3031af2088'
assert delta['to']==C
fixture='Platform/common/vectors/row-check/fixtures/testsub2.subsystem.yaml'
extra={'path':fixture,'M':'judge_only','JI':'include'}
assert delta['added']==sorted(old['added']+[extra],key=lambda r:r['path'])
for key in ('removed','changed'):
    assert delta[key]==old[key],('different reviewed filter delta',key)
accepted97=json.loads(Path('/home/pilot/cammeta-sessions/tasks/accepted/OBSH.97.json').read_text())
assert accepted97['status']=='accepted'
commit97=accepted97['commit']
for key,common in (('M_sources_to','Platform/common/export-model-filter.json'),
                   ('JI_sources_to','Platform/common/acceptance/judge-input-filter.json')):
    expected_sources=dict(old[key])
    expected_sources[common]=subprocess.check_output([
        'git','--git-dir',str(B/'source.git'),'rev-parse',commit97+':'+common]).decode().strip()
    assert delta[key]==expected_sources,('different reviewed filter sources',key)
inherited=json.loads((prior/'FILTER-REVIEWS.json').read_text())
assert inherited['C']==old['to'] and inherited['all_delta_records_covered']
assert inherited['delta_sha256']==sha(prior/'FILTER-DELTA.json')
T=Path('/home/pilot/cammeta-sessions/tasks')
accepted=(T/'accepted/P02.72.json').read_bytes()
a=json.loads(accepted)
assert a['status']=='accepted'
subprocess.run(['git','--git-dir',str(B/'source.git'),'merge-base','--is-ancestor',a['commit'],C],check=True)
(B/'reviews/P02.72-accepted.json').write_bytes(accepted)
for path in (prior/'reviews').iterdir():
    if path.is_file():
        target=B/'reviews'/path.name
        assert not target.exists() or target.read_bytes()==path.read_bytes()
        if not target.exists():shutil.copyfile(path,target)
for row in inherited['deltas']:
    r=json.loads((B/row['accepted_receipt']).read_text())
    assert r['status']=='accepted' and r['commit']==row['accepted_commit']
    assert row['author_provider']!=row['reviewer_provider']
    assert sha(B/row['review'])==row['review_sha256']
    subprocess.run(['git','--git-dir',str(B/'source.git'),'merge-base','--is-ancestor',r['commit'],C],check=True)
expected={r['path'] for key in ('added','removed','changed') for r in delta[key]}
assert expected=={p for r in inherited['deltas'] for p in r['records']}|{fixture}
subprocess.run(['git','--git-dir',str(B/'source.git'),'merge-base','--is-ancestor',commit97,C],check=True)
(B/'reviews/OBSH.97-accepted.json').write_bytes((T/'accepted/OBSH.97.json').read_bytes())
review_path='decisions/inbox/ревью/2026-11-14-OBSH.97-ревью-фильтра.md'
review=subprocess.check_output(['git','--git-dir',str(B/'source.git'),'show',C+':'+review_path])
assert 'Claude Opus 5.5'.encode() in review and b'Codex' in review and fixture.encode() in review
(B/'reviews/OBSH.97-review.md').write_bytes(review)
extra_review={'task':'OBSH.97','source_commit':commit97,'accepted_commit':commit97,
    'records':[fixture],'author_provider':'OpenAI','reviewer_provider':'Anthropic',
    'accepted_receipt':'reviews/OBSH.97-accepted.json','review':'reviews/OBSH.97-review.md',
    'review_sha256':sha(B/'reviews/OBSH.97-review.md'),
    'review_kind':'explicit filter review in C; exact current common-filter blobs equal accepted OBSH.97'}
shutil.copyfile(prior/'FILTER-REVIEWS.json',B/'reviews/P02.72-filter-reviews.json')
shutil.copyfile(prior/'FILTER-DELTA.json',B/'reviews/P02.72-filter-delta.json')
result={**inherited,'C':C,'delta_sha256':sha(B/'FILTER-DELTA.json'),
    'baseline':'accepted P02.72 classifications plus one accepted OBSH.97 judge-only fixture',
    'deltas':inherited['deltas']+[extra_review],
    'inherited_review':'reviews/P02.72-filter-reviews.json',
    'inherited_review_sha256':sha(B/'reviews/P02.72-filter-reviews.json'),
    'inherited_acceptance':'reviews/P02.72-accepted.json',
    'inherited_acceptance_sha256':sha(B/'reviews/P02.72-accepted.json'),
    'inherited_delta':'reviews/P02.72-filter-delta.json',
    'inherited_delta_sha256':sha(B/'reviews/P02.72-filter-delta.json'),
    'inherited_delta_unchanged_except_reviewed_OBSH97_fixture':True,
    'common_filter_sources_equal_accepted_OBSH97':True}
(B/'FILTER-REVIEWS.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'C':C,'delta_records_reviewed':len(expected),'inherited_from':'accepted P02.72'},indent=1))
