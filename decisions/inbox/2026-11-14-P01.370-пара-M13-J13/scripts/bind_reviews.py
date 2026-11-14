"""Bind unchanged classifications to the accepted different-provider P02.72 proofs."""
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
for key in ('added','removed','changed','M_sources_to','JI_sources_to'):
    assert delta[key]==old[key],('different reviewed filter delta/source',key)
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
assert expected=={p for r in inherited['deltas'] for p in r['records']}
shutil.copyfile(prior/'FILTER-REVIEWS.json',B/'reviews/P02.72-filter-reviews.json')
shutil.copyfile(prior/'FILTER-DELTA.json',B/'reviews/P02.72-filter-delta.json')
result={**inherited,'C':C,'delta_sha256':sha(B/'FILTER-DELTA.json'),
    'baseline':'accepted P01.360 M12/J12; exact same classifications and filter source blobs as accepted P02.72',
    'inherited_review':'reviews/P02.72-filter-reviews.json',
    'inherited_review_sha256':sha(B/'reviews/P02.72-filter-reviews.json'),
    'inherited_acceptance':'reviews/P02.72-accepted.json',
    'inherited_acceptance_sha256':sha(B/'reviews/P02.72-accepted.json'),
    'inherited_delta':'reviews/P02.72-filter-delta.json',
    'inherited_delta_sha256':sha(B/'reviews/P02.72-filter-delta.json'),
    'exact_delta_and_filter_source_blobs_equal':True}
(B/'FILTER-REVIEWS.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'C':C,'delta_records_reviewed':len(expected),'inherited_from':'accepted P02.72'},indent=1))
