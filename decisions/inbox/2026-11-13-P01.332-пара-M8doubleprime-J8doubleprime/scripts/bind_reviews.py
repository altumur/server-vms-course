"""Bind classification deltas to existing different-provider review evidence."""
from pathlib import Path
import csv,hashlib,json,shutil,subprocess,sys
B=Path(sys.argv[1]).resolve();C=(B/'C.txt').read_text().strip()
T=Path('/home/pilot/cammeta-sessions/tasks')
delta=json.loads((B/'FILTER-DELTA.json').read_text())
assert delta['to']==C and not delta['changed'] and not delta['removed']
prior_root=Path('/home/pilot/P01.329-evidence')
prior=json.loads((prior_root/'FILTER-REVIEWS.json').read_text())
rows=[]
for row in prior['deltas']:
    item=dict(row)
    for key in ('accepted_receipt','review'):
        old=prior_root/row[key];new=B/row[key];new.parent.mkdir(exist_ok=True)
        shutil.copyfile(old,new)
    assert hashlib.sha256((B/row['review']).read_bytes()).hexdigest()==row['review_sha256']
    accepted=json.loads((B/row['accepted_receipt']).read_text())
    assert accepted['status']=='accepted'
    subprocess.run(['git','--git-dir',str(B/'source.git'),'merge-base','--is-ancestor',accepted['commit'],C],check=True)
    item['inherited_from']='accepted P01.329 FILTER-REVIEWS.json; unchanged classification'
    rows.append(item)
raw=(T/'accepted/P01.341.json').read_bytes();accepted=json.loads(raw)
assert accepted['status']=='accepted'
assert 'provider: codex' in (T/'P01.341.yaml').read_text().splitlines()
with Path('/home/pilot/cammeta-sessions/sessions.tsv').open() as f:
    identities=[dict(zip(('name','handle','model'),r[:3])) for r in csv.reader(f,delimiter='\t') if r and r[0]=='architect']
assert len(identities)==1 and identities[0]['model']=='Claude' and identities[0]['handle']==accepted['window']
(B/'reviews/P01.341-reviewer.json').write_text(json.dumps({'source':'sessions.tsv name/handle/model only','identity':identities[0],'accepted_window':accepted['window'],'provider':'Anthropic'},indent=1)+'\n')
(B/'reviews/P01.341-accepted.json').write_bytes(raw)
rows.append({'task':'P01.341','records':['Platform/01-store/forms/production/soak.json','Platform/01-store/forms/production/soak.schema.json'],'author_provider':'OpenAI','reviewer_provider':'Anthropic','provider_evidence':'task provider codex; accepted.window equals architect Claude handle','accepted_receipt':'reviews/P01.341-accepted.json','review':'reviews/P01.341-accepted.json','review_sha256':hashlib.sha256(raw).hexdigest()})
expected={r['path'] for r in delta['added']}
assert {p for r in rows for p in r['records']}==expected
result={'C':C,'baseline':'P01.299 accepted pair; unchanged classifications inherited','delta_sha256':hashlib.sha256((B/'FILTER-DELTA.json').read_bytes()).hexdigest(),'deltas':rows,'filter_author_provider':'per-record actual provider in deltas','filter_reviewer_provider':'different actual provider per record in deltas','all_delta_records_covered':True}
(B/'FILTER-REVIEWS.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'C':C,'reviewed_added_records':len(expected),'OK':True},indent=1))
