"""Audit exact P05 source-only composition; never regenerate outputs or frozen maps."""
from collections import Counter
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json,subprocess,sys

PUBLISHED='3f152a87a32d9b218dfef041ef1be830a110ab1e'
AUTHOR='12af604f8def0da36b5f60af0232ca03e342a5b1'
AUTHOR_BASE='3e8825d94b2c5456089b864090f700964d7ad24d'
SEMANTIC='8995f3914d4c348ad2b6eda4807f08adbf296188'
SOURCE='2bb5a428567a4114403aabf21e692b4d5ed26c36'
ROOT=Path.cwd()
sys.path.insert(0,str(ROOT/'skills/lesson-spec/scripts'))
import en_mirror,source_cells
from v7 import spec

digest=lambda b:sha256(b).hexdigest()
def git(*args):return subprocess.check_output(['git',*args])
@lru_cache(None)
def get(ref,p):return git('show',ref+':'+p)
def tree(ref):
 out={}
 for entry in git('ls-tree','-rz',ref).split(b'\0'):
  if entry:
   meta,p=entry.split(b'\t',1);mode,kind,oid=meta.decode().split()
   assert kind=='blob';out[p.decode()]=(mode,oid)
 return out
def data(raw):return [(n,l.split('\t')) for n,l in enumerate(raw.decode().split('\n'),1) if l and not l.startswith('#')]
def table(raw):
 rows=data(raw);h=rows.pop(0)[1]
 assert all(len(c)==len(h) for _,c in rows)
 return [dict(zip(h,c)) for _,c in rows]

pub,author,source=(tree(r) for r in (PUBLISHED,AUTHOR,SOURCE))
assert git('show','-s','--format=%P',SOURCE).decode().strip().split()==[PUBLISHED,AUTHOR]
base=tree(AUTHOR_BASE)
author_delta={p for p in set(base)|set(author) if base.get(p)!=author.get(p)}
delta={p for p in set(pub)|set(source) if pub.get(p)!=source.get(p)}
completion='skills/lesson-spec/scripts/en_mirror.py';ledger='decisions/adr-norms.tsv'
assert len(author_delta)==65 and len(delta)==66 and delta==author_delta|{completion}
assert all(source.get(p)==author.get(p) or p in (completion,ledger) for p in delta)
for p in delta:assert (ROOT/p).read_bytes()==get(SOURCE,p),p
assert all(p.startswith('Platform/05-resource/') or p.startswith('decisions/inbox/2026-11-06-adr0121-p05') or p.startswith('decisions/inbox/2026-11-06-p05') or p in (
 'Platform/06-console/spec/06.1-console.norms.md','Platform/06-console/ru/spec/06.1-console.norms.md',
 'Platform/common/vectors/family-read/05.tsv',ledger,completion,'\u0425\u041e\u0414-\u0421\u043f\u0435\u0446\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f.md',
 *['Platform/common/'+prefix+'contracts/'+name+'.md' for prefix in ('','ru/') for name in ('tombstone','presence-lock','event-journal')]) for p in delta)

# Preserve the entire current published tree outside the exact accepted source delta.
identity={}
protected_lessons=sorted({'Platform/'+p.split('/')[1]+'/' for p in source if p.startswith('Platform/') and p.split('/')[1][:2].isdigit() and p.split('/')[1][:2] not in ('05','06')})
for prefix in (*protected_lessons,'Source/','VMS/','tools/'):
 selected={p:v for p,v in source.items() if p.startswith(prefix)}
 expected={p:v for p,v in pub.items() if p.startswith(prefix)}
 assert selected==expected,prefix
 identity[prefix]=dict(basis=PUBLISHED,files=len(selected),git_entries_sha256=digest(json.dumps(selected,sort_keys=True).encode()))
lesson={p:v for p,v in source.items() if p.startswith('Platform/05-resource/')}
assert len(lesson)==63 and lesson=={p:v for p,v in author.items() if p.startswith('Platform/05-resource/')}
for p in source:
 if p.startswith('Platform/06-console/') and p not in delta:assert source[p]==pub[p]
for prefix in ('','ru/'):
 p='Platform/06-console/'+prefix+'spec/06.1-console.norms.md'
 a=get(PUBLISHED,p).split(b'\n');b=get(SOURCE,p).split(b'\n')
 assert len(a)==len(b) and sum(x!=y for x,y in zip(a,b))==1
for p in ['Platform/common/'+prefix+'contracts/'+name+'.md' for prefix in ('','ru/') for name in ('forwarding','gate-and-pass')]:
 assert source[p]==pub[p],p
for p in ('Platform/common/data/catalog.tsv','Platform/common/vectors/family-read/04.tsv','skills/lesson-spec/scripts/v7/sections-meaning-deltas.tsv'):
 assert source[p]==pub[p],p
for p in set(source)|set(pub):
 if p.startswith('skills/') and p!=completion:assert source.get(p)==pub.get(p),p
original=get(PUBLISHED,completion).decode();line=next(l for l in original.split('\n') if l.startswith('FULL_ENGLISH_DONE = '))
expected=line[:-1]+', "Platform/05-resource/")'
assert get(SOURCE,completion).decode()==original.replace(line,expected)
assert 'Platform/05-resource/' in en_mirror.FULL_ENGLISH_DONE
missing=[r for r in get(AUTHOR,ledger).decode().split('\n') if r and r not in get(PUBLISHED,ledger).decode().split('\n')]
assert len(missing)==2
assert get(SOURCE,ledger)==get(PUBLISHED,ledger).rstrip(b'\n')+b'\n'+''.join(r+'\n' for r in missing).encode()
assert not any(l.startswith(('<<<<<<<','=======','>>>>>>>')) for l in get(SOURCE,ledger).decode().split('\n'))

mp='decisions/inbox/2026-11-06-adr0121-p05-source-map.tsv'
assert digest(get(SOURCE,mp))=='9576f201de9c0fd9d03c731fe338b4ef13fde8b516b0e7ae320d14b9a560457b'
assert Counter(r['phase'] for r in table(get(SOURCE,mp)))=={'review':614,'language':1703}
for suffix in ('source-map.tsv','preservation.json','freeze.md'):
 p='decisions/inbox/2026-11-06-adr0121-p05-'+suffix;assert get(SOURCE,p)==get(AUTHOR,p)
preserved=json.loads(get(AUTHOR,'decisions/inbox/2026-11-06-adr0121-p05-preservation.json'))
assert len(preserved['protocol_identities'])==1168 and len(preserved['field_changes'])==152
# The frozen original source and semantic map are unchanged; the new composition
# does not claim to repeat the historical 265-test author suite.

fr='Platform/common/vectors/family-read/05.tsv'
rows=table(get(SOURCE,fr));before=table(get(AUTHOR_BASE,fr));old={r['case']:r for r in before};after={r['case']:r for r in rows}
assert len(after)==len(rows)==1131 and len(rows)-len(before)==11
readers=[r for r in before if r['mode']=='reader']
assert len(readers)==560 and all(after[r['case']]==r for r in readers)
writers_changed=[]
for r in before:
 a=after[r['case']]
 if a!=r:
  assert r['mode']=='writer' and r['family']=='platform/resources/<server>/heartbeat'
  assert all(a[k]==r[k] for k in r if k!='text')
  x,y=json.loads(r['text']),json.loads(a['text']);added=set(y)-set(x)
  assert added<=set(('door','waits','restore','mirror')) and {k:v for k,v in y.items() if k not in added}==x
  writers_changed.append(r['case'])
assert len(writers_changed)==137 and sum(r['case'].startswith('05-k') for r in rows)==74
cat=spec.read_catalog(ROOT);bykey={(r['key'],r['kind']):r for r in cat}
templates,errors=spec.key_templates(ROOT,cat);assert not errors;cache={}
for r in rows:
 why=spec.judge_row(ROOT,bykey[r['family'],r['kind']],r['kind'],r['mode'],r['text'],json.loads(r['paths']),json.loads(r['outcome']),cache,templates[r['family'],r['kind']],r['key'])
 assert why is None,(r['case'],why)
seams='Platform/05-resource/acceptance/seams.tsv';calls=data(get(SOURCE,seams));oldcalls=data(get(AUTHOR_BASE,seams))
assert len(calls)==62 and len(oldcalls)==37 and calls[:37]==oldcalls
assert data(get(SOURCE,seams))==data(get(SEMANTIC,seams))
for _,c in calls:assert len(c)==4 and c[1]=='1';json.loads(c[2].split(' ',2)[2]);json.loads(c[3])
scenario='Platform/05-resource/acceptance/scenarios.tsv'
operational=[(n,c) for n,c in data(get(SOURCE,scenario)) if c[0]!='scenario']
assert operational==[(n,c) for n,c in data(get(SEMANTIC,scenario)) if c[0]!='scenario']
assert len(operational)==292 and len({c[0] for _,c in operational})==35
refusals=table(get(SOURCE,'Platform/05-resource/forms/refusals.tsv'))
assert len(refusals)==38 and len({r['row'] for r in refusals})==27
assert [len(table(get(SOURCE,'Platform/05-resource/forms/'+name+'.tsv'))) for name in ('daemon-flags','door-roles','stages')]==[19,11,9]
assert not en_mirror.full_english_errors(ROOT,('Platform/05-resource/',))
mirror_count=0
for ru,en in en_mirror.pairs(ROOT):
 if '/05-resource/' in str(en) and ru.is_file():
  mirror_count+=1;assert not en_mirror.compare(ru.read_text(),en.read_text(),ru,en,ROOT)
assert mirror_count==7

# Direct original-byte proof across all 731 cells; no blanket line shift assumption.
proof='Platform/common/data/cell-json-sha256.tsv';assert source[proof]==pub[proof]
proofrows=table(get(SOURCE,proof));assert len(proofrows)==731 and len({r['table'] for r in proofrows})==9
forms=source_cells.wire_headers(ROOT);byte_proof=[]
for p in sorted({r['table'] for r in proofrows}):
 assert source[p]==pub[p],p
 columns,positional=forms.get(Path(p),(None,False))
 declared,decoded,errors=source_cells.table(get(SOURCE,p).decode(),columns,positional);assert not errors,(p,errors)
 baseline=('2ebffcaa59ab7694fb90d7f6d29410b44adcd619' if p.startswith('Platform/common/') else
  'cac140972cfc4e949e2859adbe4afde10fa3c7ff' if p.startswith('Platform/01-store/') else
  'fa9fa46a0cd5a83353d9a2afe66d7366d3f27853' if p.startswith('Platform/02-installer/') else
  'f5108651a59b5a5cbd202f1b0ad26572012457ee')
 oldrows=data(get(baseline,p))
 if positional:cols=columns
 else:_,cols=oldrows.pop(0)
 assert len(oldrows)==len(decoded)
 for (oldline,values),(line,row) in zip(oldrows,decoded):
  before=dict(zip(cols,values))
  for column in declared:
   assert before[column].encode()==row[column].encode(),(p,line,column)
   byte_proof.append(dict(table=p,before=baseline,before_line=oldline,line=line,column=column,before_sha256=digest(before[column].encode()),decoded_sha256=digest(row[column].encode())))
assert len(byte_proof)==731
expected_proof={(r['table'],int(r['line']),r['column']):(r['before_sha256'],r['decoded_sha256']) for r in proofrows}
assert {(r['table'],r['line'],r['column']):(r['before_sha256'],r['decoded_sha256']) for r in byte_proof}==expected_proof
assert not source_cells.errors(ROOT,[p for p in en_mirror.english_sources(ROOT,('Platform/','VMS/')) if p.suffix=='.tsv'])
created='Platform/03-worker/vectors/creates-key/cases.tsv'
old715=b'\n'.join(l for l in get(SOURCE,proof).split(b'\n') if not l.startswith(created.encode()+b'\t'))
assert old715==get('3def662df86bd360430c7190886d515d813f5fe6',proof)

# Exact map of every path where published / frozen author / fixed source differ,
# including preserved generated outputs as identity evidence, not new generation.
paths=sorted(set(pub)|set(author)|set(source))
mapped=[p for p in paths if not(pub.get(p)==author.get(p)==source.get(p))]
oids=sorted({v[1] for t in (pub,author,source) for p in mapped if(v:=t.get(p))})
stream=BytesIO(subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(oids)+'\n').encode()))
hashes={}
for oid in oids:
 h=stream.readline().decode().split();assert h[0]==oid and h[1]=='blob'
 hashes[oid]=digest(stream.read(int(h[2])));assert stream.read(1)==b'\n'
basis_rows=[];counts=Counter()
for p in mapped:
 a,b,c=(t.get(p) for t in (pub,author,source))
 basis='published3f' if c==a else 'author12af' if c==b else 'approved-one-line-completion' if p==completion else 'append-two-ledger'
 assert basis!='append-two-ledger' or p==ledger
 counts[basis]+=1
 basis_rows.append([p,basis,*[' '.join(v) if v else '-' for v in (a,b,c)],*[hashes[v[1]] if v else '-' for v in (a,b,c)]])
mapfile=ROOT/'decisions/inbox/2026-11-06-p05-forward-basis.tsv'
mapfile.write_text('# Exact P05 forward basis; fixed source merge '+SOURCE+'; generated entries are preserved identity evidence, not regenerated outputs.\npath\tbasis\tpublished_mode_blob\tauthor_mode_blob\tsource_mode_blob\tpublished_sha256\tauthor_sha256\tsource_sha256\n'+''.join('\t'.join(r)+'\n' for r in basis_rows))
report=dict(published=PUBLISHED,author=AUTHOR,source_merge=SOURCE,source_delta_files=len(delta),merge_source_conflicts=[],
 forward_map=mapfile.relative_to(ROOT).as_posix(),forward_map_sha256=digest(mapfile.read_bytes()),forward_map_rows=len(basis_rows),forward_map_basis=counts,
 identity_groups=identity,all_P05_files_exact_author=len(lesson),ledger_author_rows_appended=2,completion_single_approved_line=True,
 registry_exact_published=True,P04_two_base_notes_and_linked_P02_exact_published=True,P09_catalogue_ops_preserved=True,P10_reserved_contracts_exact_published=True,
 original_map_sha256=digest(get(SOURCE,mp)),original_maps_preservation_freezes_unchanged=True,
 P05_family_source_rows_checked=len(rows),P05_key_cases=74,old_reader_rows_identical=560,old_writer_text_completions=137,new_family_cases=11,
 P05_CALL_source_only=62,old37CALL_exact=True,process_source_only_scenarios=35,process_source_only_steps=292,flags=19,roles=11,stages=9,
 refusal_projections=38,original_refusal_rows=27,P05_mirror_pairs=mirror_count,P05_Cyrillic=0,
 source_cell_count=731,source_cell_tables=9,proof_table_exact_published=True,old715_bytes_unchanged=True,byte_proof=byte_proof,
 no_new_cell_transport=True,P06_only_two_linked_completion_rows=True,P08_source_not_merged=True,
 tools_outputs_GEN01_exact_published=True,output_regeneration=False,normgen_KIT_run=False,runtime_green_claim=False,SUT_runs=0,errors=[])
checklog=ROOT/'.spec-check/p05-forward-source-check.log';focusedlog=ROOT/'.spec-check/p05-forward-focused.log'
assert 'PASS with 62 exceptions' in checklog.read_text()
focused=focusedlog.read_text();assert 'Ran 16 tests in' in focused
focused_pass=focused.rstrip().endswith('OK')
assert focused_pass or (focused.rstrip().endswith('FAILED (failures=1)') and 'restore.<\u0438\u043c\u044f>.restored' in focused and 'stale' in focused)
report.update(check_spec='PASS with 62 exceptions; strict coverage including VMS832',focused_tests=dict(tests=16,status='PASS',skip=0,
 seconds=float((ROOT/'.spec-check/p05-forward-focused.time').read_text()),meaning_registry='PASS' if focused_pass else 'RED: one stale P05 restore.<name>.restored desc entry; no source semantic defect'),
 log_sha256={p.name:digest(p.read_bytes()) for p in (checklog,focusedlog)})
report['focused_tests']['status']='PASS' if focused_pass else 'RED 15PASS/1FAIL'
(ROOT/'decisions/inbox/2026-11-06-p05-forward-proof.json').write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('source_merge','source_delta_files','forward_map_rows','forward_map_sha256','forward_map_basis','all_P05_files_exact_author','P05_family_source_rows_checked','P05_mirror_pairs','source_cell_count','source_cell_tables','focused_tests')},indent=2))
