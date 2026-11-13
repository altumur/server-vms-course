"""Copy release proofs and record selected evidence/report bytes; no export mutation."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

B,D=(Path(p).resolve() for p in sys.argv[1:3])
I=json.loads((B/'IDENTITIES.json').read_text())
assert json.loads((B/'VERIFY-ALL.json').read_text())['OK']
assert json.loads((B/'CHANGED-NORMS-AUDIT.json').read_text())['OK']
for name in ('IDENTITIES.json','NARROW-M.json','OPERATOR-UNCHANGED.json','SOURCE-COMPOSITION.json','CHECK-SPEC-C.run.json','FILTER-DELTA.json','FILTER-REVIEWS.json','VERIFY-PAIR.json','VERIFY-JI.json','VERIFY-ALL.json','CHANGED-NORMS-AUDIT.json'):
    shutil.copyfile(B/name,D/name)
for source,target in [(Path(I['M_passport']),'PASSPORT-M.json'),(Path(I['JI_directory'])/'PASSPORT-JI.json','PASSPORT-JI.json'),(Path(I['pair_directory'])/'PASSPORT-TRUSTED-ONLY.json','PASSPORT-RAW-PAIR.json'),(B/'passport/CONTROLS.json','PASSPORT-CONTROLS.json')]:
    shutil.copyfile(source,D/target)
for p in (D/'scripts').glob('*.py'):
    shutil.copyfile(p,B/'scripts'/p.name)

def row(p):
    raw=p.read_bytes()
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

proofs=[p for p in B.iterdir() if p.is_file() and p.name not in ('PAIR-EVIDENCE-MANIFEST.json','FINAL-ARTIFACT-MANIFEST.json') and not p.name.startswith(('CHECK-SPEC-SUBMISSION','FINAL-RECEIPT'))]
for sub in ('operator','scripts','reviews'):
    proofs.extend(p for p in (B/sub).iterdir() if p.is_file())
proofs.extend(Path(p) for p in (I['M_passport'],str(Path(I['JI_directory'])/'PASSPORT-JI.json'),str(Path(I['pair_directory'])/'PASSPORT-TRUSTED-ONLY.json')))
proofs.extend(p for p in (B/'passport/controls-final').iterdir() if p.is_file())
proofs.append(B/'passport/CONTROLS.json')
manifest={k:I[k] for k in ('C','M','J','JI')}
manifest.update({'evidence':str(B),'note':'Selected release proofs and wrappers; Git artifacts bound by exact commits and VERIFY-PAIR. Submission check and final receipt are separate.','files':[row(p) for p in sorted(set(proofs))]})
for target in (B/'PAIR-EVIDENCE-MANIFEST.json',D/'PAIR-EVIDENCE-MANIFEST.json'):
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=1)+'\n')
report=[p for p in D.rglob('*') if p.is_file() and p.name!='FINAL-ARTIFACT-MANIFEST.json' and '__pycache__' not in p.parts]
out={k:I[k] for k in ('C','M','J','JI')};out.update({'report_files':[row(p) for p in sorted(report)],'OK':True})
for target in (B/'FINAL-ARTIFACT-MANIFEST.json',D/'FINAL-ARTIFACT-MANIFEST.json'):
    target.write_text(json.dumps(out,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'report_files':len(report),'evidence_files':len(set(proofs)),'OK':True},indent=1))
