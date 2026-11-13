"""Inherit accepted M11 filter classifications only after exact zero-delta proof."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
B=Path(sys.argv[1]).resolve()
C=(B/'C.txt').read_text().strip()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
delta=json.loads((B/'FILTER-DELTA.json').read_text())
assert delta['from']=='69e14d0cdd133f2736e1e8261a690ccb3ab2ed30' and delta['to']==C
assert not any(delta[k] for k in ('added','removed','changed')), 'unreviewed filter delta; stop release'
inherited=Path('/home/pilot/P01.355-evidence/r2/FILTER-REVIEWS.json')
shutil.copyfile(inherited,B/'reviews/P01.355-inherited-filter-reviews.json')
# Preserve all relative review references of the accepted inherited proof.
for old in (inherited.parent/'reviews').iterdir():
    if old.is_file():
        new=B/'reviews'/old.name
        assert not new.exists() or new.read_bytes()==old.read_bytes()
        if not new.exists(): shutil.copyfile(old,new)
accepted=json.loads((B/'reviews/P01.355-accepted.json').read_text())
assert accepted['status']=='accepted'
result={'C':C,'baseline':'accepted P01.355 M11/J11; exact zero semantic filter delta',
    'delta_sha256':sha(B/'FILTER-DELTA.json'),'deltas':[],
    'filter_author_provider':'inherited accepted classifications; no new delta',
    'filter_reviewer_provider':'inherited accepted different-provider review; no new delta',
    'all_delta_records_covered':True,
    'inherited_review':'reviews/P01.355-inherited-filter-reviews.json',
    'inherited_review_sha256':sha(inherited),
    'inherited_acceptance':'reviews/P01.355-accepted.json',
    'inherited_acceptance_sha256':sha(B/'reviews/P01.355-accepted.json')}
(B/'FILTER-REVIEWS.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'C':C,'delta_records_reviewed':0,'inherited_from':'P01.355'},indent=1))
