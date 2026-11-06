"""Reproduce the source-only P04 forward composition, identities and byte proofs."""
from collections import Counter
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import copy,json,subprocess,sys

PUBLISHED='c9a6eb86d4ed4bebb0c720bb4385396c3e485fe6'
AUTHOR='3e8825d94b2c5456089b864090f700964d7ad24d'
SOURCE='4723d25cb1c01b2a658696c758bfde8e9157cf60'
BASES={'5a355d41ba49239726e89997609b135db5268d73','8f2873279bfc264911a1f296ec96fec89139b7b0'}
ROOT=Path.cwd()
MAP=Path('decisions/inbox/2026-11-06-p04-forward-basis.tsv')
REPORT=Path('decisions/inbox/2026-11-06-p04-forward-proof.json')
sys.path.insert(0,str(ROOT/'skills/lesson-spec/scripts'))
import en_mirror,source_cells
from v7 import spec

def git(*args):return subprocess.check_output(['git',*args])
def digest(b):return sha256(b).hexdigest()
@lru_cache(maxsize=None)
def get(ref,p):return git('show',ref+':'+p)
def tree(ref):
 out={}
 for entry in git('ls-tree','-rz','--full-tree',ref).split(b'\0'):
  if entry:
   meta,p=entry.split(b'\t',1);mode,kind,oid=meta.decode().split();assert kind=='blob';out[p.decode()]=(mode,oid)
 return out
def data(raw):
 rows=[(n,l.split('\t')) for n,l in enumerate(raw.decode().split('\n'),1) if l and not l.startswith('#')]
 return rows
def table(raw):
 rows=data(raw);h=rows.pop(0)[1];return [dict(zip(h,c)) for n,c in rows]

pub,author,source=(tree(ref) for ref in (PUBLISHED,AUTHOR,SOURCE))
assert git('show','-s','--format=%P',SOURCE).decode().strip().split()==[PUBLISHED,AUTHOR]
assert set(git('merge-base','--all',PUBLISHED,AUTHOR).decode().split())==BASES
ancestors=set(git('rev-list',SOURCE).decode().split())
assert '12af604f8def0da36b5f60af0232ca03e342a5b1' not in ancestors
paths=sorted(set(pub)|set(author)|set(source))
delta=[p for p in paths if pub.get(p)!=source.get(p)]
assert len(delta)==78,len(delta)
completion='skills/lesson-spec/scripts/en_mirror.py';ledger='decisions/adr-norms.tsv'
assert all(source.get(p)==author.get(p) or p in (ledger,completion) for p in delta)
assert all((ROOT/p).read_bytes()==get(SOURCE,p) for p in delta)
assert all(p.startswith(('Platform/02-installer/','Platform/04-controller/','decisions/inbox/2026-11-06-adr0121-p04','decisions/inbox/2026-11-06-p04')) or p in (
 completion,ledger,'Platform/common/data/README.md','Platform/common/ru/data/README.md','Platform/common/data/catalog.tsv','Platform/common/vectors/family-read/04.tsv') for p in delta),delta

identity={}
# Every other Platform lesson, Source, VMS and tools retains the published tree.
for prefix in sorted({p.split('/')[1] for p in source if p.startswith('Platform/') and len(p.split('/'))>2 and p.split('/')[1][:2].isdigit()}):
 if prefix.startswith(('02-','04-')):continue
 selected={p:v for p,v in source.items() if p.startswith('Platform/'+prefix+'/')}
 expected={p:v for p,v in pub.items() if p.startswith('Platform/'+prefix+'/')}
 assert selected==expected,prefix
 identity['Platform/'+prefix+'/']=dict(basis=PUBLISHED,files=len(selected),git_entries_sha256=digest(json.dumps(selected,sort_keys=True).encode()))
for prefix,expected,basis in [('Platform/04-controller/',author,AUTHOR),('Source/',pub,PUBLISHED),('VMS/',pub,PUBLISHED),('tools/',pub,PUBLISHED)]:
 selected={p:v for p,v in source.items() if p.startswith(prefix)}
 assert selected=={p:v for p,v in expected.items() if p.startswith(prefix)},prefix
 identity[prefix]=dict(basis=basis,files=len(selected),git_entries_sha256=digest(json.dumps(selected,sort_keys=True).encode()))

# One approved completion line; no other skill or registry change.
original=get(PUBLISHED,completion).decode();line=next(l for l in original.split('\n') if l.startswith('FULL_ENGLISH_DONE = '))
new=line[:-1]+', "Platform/04-controller/")'
assert get(SOURCE,completion).decode()==original.replace(line,new)
for p in set(source)|set(pub):
 if p.startswith('skills/') and p!=completion:assert source.get(p)==pub.get(p),p
registry='skills/lesson-spec/scripts/v7/sections-meaning-deltas.tsv';assert source[registry]==pub[registry]
reserved=['Platform/common/'+prefix+'contracts/'+name+'.md' for prefix in ('','ru/') for name in ('forwarding','gate-and-pass')]
for p in reserved:assert source[p]==pub[p]
author_rows=[r for r in get(AUTHOR,ledger).decode().split('\n') if r]
missing=[r for r in author_rows if r not in get(PUBLISHED,ledger).decode().split('\n')]
assert len(missing)==3
assert get(SOURCE,ledger)==get(PUBLISHED,ledger).rstrip(b'\n')+b'\n'+''.join(r+'\n' for r in missing).encode()
assert not any(r.startswith(('<<<<<<<','=======','>>>>>>>')) for r in get(SOURCE,ledger).decode().split('\n'))

# Catalogue: add only the sibling pending family, preserving every existing cell.
catalog='Platform/common/data/catalog.tsv'
a=get(PUBLISHED,catalog).decode().split('\n');b=get(SOURCE,catalog).decode().split('\n')
added=[l for l in b if l not in a];assert len(added)==1 and added[0].startswith('<sub>/decommission-pending/<host>\t')
assert [l for l in b if l not in added]==a
for p in ['Platform/common/data/README.md','Platform/common/ru/data/README.md','Platform/common/vectors/family-read/04.tsv']:
 assert source[p]==author[p]
catalog_rows=table(get(SOURCE,catalog));old_catalog={(r['key'],r['kind']):r for r in table(get(PUBLISHED,catalog))}
for r in catalog_rows:
 if r['key']!='<sub>/decommission-pending/<host>':assert r==old_catalog[r['key'],r['kind']]
member_ops=[dict(key=r['key'],kind=r['kind'],ops=r['ops']) for r in old_catalog.values() if r['key'] in ('domain/member','domain/member-key')]

# Linked P02 schema reservations: exactly four enum insertions, no description rollback.
schema_insertions=[]
for p in ('Platform/02-installer/spec/02.1-installer.schema.json','Platform/02-installer/spec/02.2-installer.view.schema.json'):
 a=json.loads(get(PUBLISHED,p));b=json.loads(get(SOURCE,p));assert get(SOURCE,p)==get(AUTHOR,p)
 count=0
 def strip(v):
  global count
  if isinstance(v,dict):return {k:strip(x) for k,x in v.items()}
  if isinstance(v,list):
   out=[]
   for x in v:
    if x=='decommission-pending':count+=1
    else:out.append(strip(x))
   return out
  return v
 assert strip(b)==a and count==2,(p,count)
 schema_insertions.append(dict(path=p,insertions=count,all_other_schema_values_exact_published=True))
for prefix in ('','ru/'):
 for chapter in ('02.1-installer','02.2-installer'):
  p='Platform/02-installer/'+prefix+'spec/'+chapter+'.norms.md'
  assert get(SOURCE,p)==get(AUTHOR,p)
  assert get(SOURCE,p).replace(b', `decommission-pending`',b'')==get(PUBLISHED,p),p
 p='Platform/02-installer/'+prefix+'spec/02.5-installer.norms.md'
 assert get(SOURCE,p)==get(AUTHOR,p)
 assert get(SOURCE,p).replace(b', `<s>/decommission-pending/*`',b'')==get(PUBLISHED,p),p
linked=json.loads(get(AUTHOR,'decisions/inbox/2026-11-06-p04-review-preservation.json'))
rights=[]
for r in linked['rights_projection']:
 p=r['path'];assert get(SOURCE,p)==get(AUTHOR,p)
 a=json.loads(get(PUBLISHED,p));b=json.loads(get(SOURCE,p))
 for role,op,value in r['added']:
  assert value in b['roles'][role][op] and value not in a['roles'][role].get(op,[])
  b['roles'][role][op].remove(value)
 assert b==a,p
 rights.append(dict(path=p,insertions=r['added'],remaining_json_exact_published=True))
assert len(rights)==6 and sum(len(r['insertions']) for r in rights)==17
p02={p:v for p,v in source.items() if p.startswith('Platform/02-installer/')}
p02delta=[p for p in p02 if p02[p]!=pub.get(p)]
assert len(p02delta)==14 and all(source[p]==author[p] for p in p02delta)

# All frozen P04 source/data, including old reader/new writer distinctions.
mp='decisions/inbox/2026-11-06-adr0121-p04-source-map.tsv'
assert digest(get(SOURCE,mp))=='a2e7d2bdd5aad9518dcb3820b43cd4be1c2084dc426c5609c9058f543abad02a'
for suffix in ('preservation.json','freeze.md'):
 p='decisions/inbox/2026-11-06-adr0121-p04-'+suffix;assert get(SOURCE,p)==get(AUTHOR,p)
fr='Platform/common/vectors/family-read/04.tsv'
read_rows=table(get(SOURCE,fr));old_rows={r['case']:r for r in table(get(PUBLISHED,fr))}
assert len(read_rows)==1436 and len(read_rows)-len(old_rows)==81
cat=spec.read_catalog(ROOT);bykey={(r['key'],r['kind']):r for r in cat};templates,errors=spec.key_templates(ROOT,cat);assert not errors
cache={}
for r in read_rows:
 why=spec.judge_row(ROOT,bykey[r['family'],r['kind']],r['kind'],r['mode'],r['text'],json.loads(r['paths']),json.loads(r['outcome']),cache,templates[r['family'],r['kind']],r['key'])
 assert why is None,(r['case'],why)
 if r['case'] in old_rows:
  before=old_rows[r['case']]
  assert all(r[k]==before[k] for k in ('case','family','kind','mode','who')),r['case']
assert sum(r['case'].startswith('04-k') for r in read_rows)==36
seam='Platform/04-controller/acceptance/seams.tsv';seams=data(get(SOURCE,seam));assert len(seams)==50 and get(SOURCE,seam)==get(AUTHOR,seam)
for _,c in seams:assert c[1]=='1';json.loads(c[2].split(' ',2)[2]);json.loads(c[3])
# Every P04 machine/capture and process/vector input is already exactauthor via tree identity.
assert not en_mirror.full_english_errors(ROOT,('Platform/04-controller/',))
assert 'Platform/04-controller/' in en_mirror.FULL_ENGLISH_DONE
pair_count=0
for ru,en in en_mirror.pairs(ROOT):
 if '/04-controller/' in str(en) and ru.is_file():
  pair_count+=1;assert not en_mirror.compare(ru.read_text(),en.read_text(),ru,en,ROOT)

# Common/P01/P02/P03 cell transport stays exact published731/9, plus direct original byte proof.
proof='Platform/common/data/cell-json-sha256.tsv';assert source[proof]==pub[proof]
rows=table(get(SOURCE,proof));assert len(rows)==731 and len({r['table'] for r in rows})==9
forms=source_cells.wire_headers(ROOT);byte_proof=[]
for p in sorted({r['table'] for r in rows}):
 assert source[p]==pub[p],p
 columns,positional=forms.get(Path(p),(None,False))
 declared,decoded,errors=source_cells.table(get(SOURCE,p).decode(),columns,positional);assert not errors,(p,errors)
 baseline=('2ebffcaa59ab7694fb90d7f6d29410b44adcd619' if p.startswith('Platform/common/') else
  'cac140972cfc4e949e2859adbe4afde10fa3c7ff' if p.startswith('Platform/01-store/') else
  'fa9fa46a0cd5a83353d9a2afe66d7366d3f27853' if p.startswith('Platform/02-installer/') else
  'f5108651a59b5a5cbd202f1b0ad26572012457ee')
 old=data(get(baseline,p))
 if positional:cols=columns
 else:_,cols=old.pop(0)
 assert len(old)==len(decoded)
 for (oldline,values),(line,row) in zip(old,decoded):
  before=dict(zip(cols,values))
  for column in declared:
   assert before[column].encode()==row[column].encode(),(p,line,column)
   byte_proof.append(dict(table=p,before=baseline,before_line=oldline,line=line,column=column,before_sha256=digest(before[column].encode()),decoded_sha256=digest(row[column].encode())))
assert len(byte_proof)==731
assert not source_cells.errors(ROOT,[p for p in en_mirror.english_sources(ROOT,('Platform/','VMS/')) if p.suffix=='.tsv'])
created='Platform/03-worker/vectors/creates-key/cases.tsv'
old715=b'\n'.join(l for l in get(SOURCE,proof).split(b'\n') if not l.startswith(created.encode()+b'\t'))
assert old715==get('3def662df86bd360430c7190886d515d813f5fe6',proof)

# Record exact provenance for all paths that distinguish published/author/source.
mapped=[p for p in paths if not(pub.get(p)==author.get(p)==source.get(p))]
oids=sorted({v[1] for t in (pub,author,source) for p in mapped if(v:=t.get(p))})
stream=BytesIO(subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(oids)+'\n').encode()))
hashes={}
for oid in oids:
 header=stream.readline().decode().split();assert header[0]==oid and header[1]=='blob';hashes[oid]=digest(stream.read(int(header[2])));assert stream.read(1)==b'\n'
basis_rows=[];counts=Counter()
for p in mapped:
 a,b,c=(t.get(p) for t in (pub,author,source))
 basis='publishedc9' if c==a else 'author3e' if c==b else 'one-line-completion' if p==completion else 'append-three-ledger'
 assert basis!='append-three-ledger' or p==ledger
 counts[basis]+=1
 basis_rows.append([p,basis,*[' '.join(v) if v else '-' for v in (a,b,c)],*[hashes[v[1]] if v else '-' for v in (a,b,c)]])
MAP.write_text('# Exact P04 forward basis; fixed source merge '+SOURCE+'; tools/output entries are preserved identity evidence, not regenerated outputs.\npath\tbasis\tpublished_mode_blob\tauthor_mode_blob\tsource_mode_blob\tpublished_sha256\tauthor_sha256\tsource_sha256\n'+''.join('\t'.join(r)+'\n' for r in basis_rows))
report=dict(published=PUBLISHED,author=AUTHOR,source_merge=SOURCE,merge_bases=sorted(BASES),source_delta_files=len(delta),forward_map=str(MAP),forward_map_sha256=digest(MAP.read_bytes()),forward_map_rows=len(basis_rows),forward_map_basis=counts,identity_groups=identity,
 ledger_author_rows_appended=3,completion_single_line=True,registry_exact_published=True,p10_reserved_contracts_exact_published=reserved,p09_existing_member_ops_preserved=member_ops,catalog_only_new_pending_family=True,
 linked_p02_changed_files=p02delta,linked_schema_reservations=schema_insertions,linked_rights=rights,
 all_P04_files_exact_author=True,original_map_sha256=digest(get(SOURCE,mp)),original_preservation_unchanged=True,P04_family_rows_checked=len(read_rows),P04_key_cases=36,new_family_cases=81,old_family_roles_and_modes_preserved=True,P04_CALL=50,P04_mirror_pairs=pair_count,P04_cyrillic=0,
 source_cell_count=731,source_cell_tables=9,proof_table_exact_published=True,old715_bytes_unchanged=True,byte_proof=byte_proof,
 P05_excluded=True,output_regeneration=False,normgen_kit_run=False,runtime_green_claim=False,SUT_runs=0,errors=[])
# Recorded author checks, not tests re-executed by this source-only helper.
report.update(json.loads('{"check_spec": "PASS with 62 exceptions; strict coverage including VMS832", "focused_tests": {"tests": 16, "status": "PASS", "seconds": 32.323, "skip": 0, "meaning_registry": "PASS"}, "log_sha256": {"p04-forward-source-check.log": "61e86a37a8b50a1f3817ef2053300ec362248e0179fe9f2eeb6f910ca571ee56", "p04-forward-focused.log": "3d877c44046a4ae890cb89836ce45d0223d3f9f51e3754ccffc262e13a456294", "p04-forward-audit.log": "d91187775444e2c3e3b1bcbf9b2b832a2d5944b6ec5e4c98ef77a37f8bd0190c"}}'))
REPORT.write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('source_merge','source_delta_files','forward_map_rows','forward_map_sha256','forward_map_basis','P04_family_rows_checked','P04_mirror_pairs','source_cell_count','source_cell_tables')},indent=2))
