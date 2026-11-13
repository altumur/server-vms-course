"""Inherit accepted P01.329 classifications only when semantic delta is empty."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
C = (B / 'C.txt').read_text().strip()
delta = json.loads((B / 'FILTER-DELTA.json').read_text())
assert delta['to'] == C and delta['from'] == 'dc0645fa329eaf7d52203dac5d4e69eb63cbd989'
assert not delta['added'] and not delta['removed'] and not delta['changed']
accepted = json.loads((B / 'reviews/P01.329-accepted.json').read_text())
assert accepted['status'] == 'accepted'
subprocess.run(['git', '--git-dir', str(B / 'source.git'), 'merge-base', '--is-ancestor',
                accepted['commit'], C], check=True)
inherited = Path('/home/pilot/P01.329-evidence/FILTER-REVIEWS.json')
shutil.copyfile(inherited, B / 'reviews/P01.329-inherited-filter-reviews.json')
review = json.loads(inherited.read_text())
assert review['C'] == delta['from'] and review['all_delta_records_covered']
out = {'C': C, 'baseline': 'accepted P01.329 pair; all semantic classifications unchanged',
       'delta_sha256': hashlib.sha256((B / 'FILTER-DELTA.json').read_bytes()).hexdigest(),
       'deltas': [], 'all_delta_records_covered': True,
       'filter_author_provider': 'inherited per-record actual providers from accepted P01.329',
       'filter_reviewer_provider': 'inherited different actual provider per record from accepted P01.329',
       'inherited_review': 'reviews/P01.329-inherited-filter-reviews.json',
       'inherited_review_sha256': hashlib.sha256(inherited.read_bytes()).hexdigest(),
       'accepted_receipt': 'reviews/P01.329-accepted.json',
       'no_new_classification': True}
(B / 'FILTER-REVIEWS.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
print(json.dumps({'C': C, 'inherited_classifications': delta['counts']['records_to'], 'new_records': 0}, indent=1))
