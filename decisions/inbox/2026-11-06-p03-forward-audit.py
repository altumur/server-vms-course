"""Reproduce P03 source-only forward identities and exact byte proofs."""
from collections import Counter
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import subprocess
import sys

PUBLISHED='3def662df86bd360430c7190886d515d813f5fe6'
AUTHOR='8f2873279bfc264911a1f296ec96fec89139b7b0'
SOURCE='5fda5046a8b2899a93c12f1f53b8915475b99de8'
BASES={'828e2583fe90d8f959bdf7d4088132f5ecb96699','34ee07d34d431c1f78fb04f24e91c17f6e34f42b'}
ROOT=Path.cwd()
MAP=Path('decisions/inbox/2026-11-06-p03-forward-basis.tsv')
REPORT=Path('decisions/inbox/2026-11-06-p03-forward-proof.json')
sys.path.insert(0,str(ROOT/'skills/lesson-spec/scripts'))
import en_mirror,source_cells


def git(*args):return subprocess.check_output(['git',*args])
def digest(data):return sha256(data).hexdigest()
def get(ref,path):return git('show',ref+':'+path)
def tree(ref):
    result={}
    for entry in git('ls-tree','-rz','--full-tree',ref).split(b'\0'):
        if entry:
            meta,path=entry.split(b'\t',1);mode,kind,oid=meta.decode().split()
            assert kind=='blob';result[path.decode()]=(mode,oid)
    return result


published,author,source=(tree(ref) for ref in (PUBLISHED,AUTHOR,SOURCE))
assert git('show','-s','--format=%P',SOURCE).decode().strip().split()==[PUBLISHED,AUTHOR]
assert set(git('merge-base','--all',PUBLISHED,AUTHOR).decode().split())==BASES
ancestors=set(git('rev-list',SOURCE).decode().split())
assert '3e8825d94b2c5456089b864090f700964d7ad24d' not in ancestors
assert BASES <= ancestors
paths=sorted(set(published)|set(author)|set(source))
delta=[p for p in paths if published.get(p)!=source.get(p)]
assert len(delta)==55,len(delta)
assert all(p=='decisions/adr-norms.tsv' or source.get(p)==author.get(p) for p in delta)
assert all((ROOT/p).read_bytes()==get(SOURCE,p) for p in delta)

identity={}
for prefix,ref,expected in [
    ('Platform/03-worker/',AUTHOR,author),
    ('Platform/01-store/',PUBLISHED,published),('Platform/02-installer/',PUBLISHED,published),
    ('Platform/04-controller/',PUBLISHED,published),('Platform/05-resource/',PUBLISHED,published),
    ('Platform/06-console/',PUBLISHED,published),('Platform/08-domain/',PUBLISHED,published),
    ('Platform/09-agent/',PUBLISHED,published),('VMS/',PUBLISHED,published),
    ('Source/',PUBLISHED,published),('tools/',PUBLISHED,published),
]:
    selected={p:v for p,v in source.items() if p.startswith(prefix)}
    assert selected=={p:v for p,v in expected.items() if p.startswith(prefix)},prefix
    identity[prefix]=dict(basis=ref,files=len(selected),git_entries_sha256=digest(json.dumps(selected,sort_keys=True).encode()))

# The criss-cross Git merge has two actual bases. Their ADR append union is
# the logical base; temporary virtual-base conflict markers are never source.
ledger='decisions/adr-norms.tsv'
base_rows={r for ref in BASES for r in get(ref,ledger).decode().split('\n') if r}
author_rows=[r for r in get(AUTHOR,ledger).decode().split('\n') if r]
new=[r for r in author_rows if r not in base_rows]
missing=[r for r in author_rows if r not in get(PUBLISHED,ledger).decode().split('\n')]
assert len(new)==len(missing)==2 and set(new)==set(missing)
assert all(r.startswith('0121\t') and 'P/03' in r for r in new)
assert get(SOURCE,ledger)==get(PUBLISHED,ledger).rstrip(b'\n')+b'\n'+(''.join(r+'\n' for r in new)).encode()
assert not any(r.startswith(('<<<<<<<','=======','>>>>>>>')) for r in get(SOURCE,ledger).decode().split('\n'))
registry='skills/lesson-spec/scripts/v7/sections-meaning-deltas.tsv'
assert source[registry]==published[registry]
assert source['skills/lesson-spec/scripts/en_mirror.py']==author['skills/lesson-spec/scripts/en_mirror.py']
for p in source:
    if p.startswith('skills/') and p!='skills/lesson-spec/scripts/en_mirror.py':assert source[p]==published.get(p),p

mp='decisions/inbox/2026-11-06-adr0121-p03-source-map.tsv'
assert digest(get(SOURCE,mp))=='850fe4203d906f6bd174f9b259b7d65ebecc3b4c979b69b45f4024816f31252d'
preservation='decisions/inbox/2026-11-06-adr0121-p03-preservation.json'
assert get(SOURCE,preservation)==get(AUTHOR,preservation)
frozen=json.loads(get(SOURCE,preservation))
machine_paths=['Platform/03-worker/forms/'+p for p in (
    'row-write-bindings.tsv','contender-writer.machine.yaml','contender-writer.traces.tsv',
    'token-cache.machine.yaml','token-cache.traces.tsv','slot-capture.tsv')]
seam_paths=sorted(p for p in source if p.startswith('Platform/03-worker/acceptance/') and p.endswith('/seams.tsv'))
assert len(seam_paths)==7
for p in machine_paths+seam_paths:
    assert get(SOURCE,p)==get(AUTHOR,p)==get('34ee07d34d431c1f78fb04f24e91c17f6e34f42b',p),p
assert len(machine_paths+seam_paths)==13
for r in frozen['identity_files']:assert digest(get(SOURCE,r['path']))==r['sha256'],r['path']
call_count=sum(1 for p in seam_paths for line in get(SOURCE,p).decode().split('\n') if '\tCALL ' in line)
assert call_count==55
s5=next(l for l in get(SOURCE,'Platform/03-worker/acceptance/6/seams.tsv').decode().split('\n') if l.startswith('s5-state-start-born\t')).split('\t')
request=json.loads(s5[2].split(' ',2)[2]);expect=json.loads(s5[3]);guard='9007199254740993'
assert request['start']['epoch_index']==expect['guard']['index']==guard
assert isinstance(request['start']['epoch_index'],str) and isinstance(expect['guard']['index'],str)
rollout='Platform/02-installer/forms/rollout-poll.machine.yaml'
assert source[rollout]==published[rollout]

proof_path='Platform/common/data/cell-json-sha256.tsv'
proof=get(SOURCE,proof_path)
assert proof==get(AUTHOR,proof_path)
created='Platform/03-worker/vectors/creates-key/cases.tsv'
prior=b'\n'.join(l for l in proof.split(b'\n') if not l.startswith(created.encode()+b'\t'))
assert prior==get(PUBLISHED,proof_path)
proof_rows=[l.split('\t') for l in proof.decode().split('\n') if l and not l.startswith('#')][1:]
assert len(proof_rows)==731 and len({r[0] for r in proof_rows})==9
forms=source_cells.wire_headers(ROOT);byte_proof=[]
for table in sorted({r[0] for r in proof_rows}):
    columns,positional=forms.get(Path(table),(None,False))
    declared,decoded,errors=source_cells.table(get(SOURCE,table).decode(),columns,positional)
    assert not errors,(table,errors)
    ref=('2ebffcaa59ab7694fb90d7f6d29410b44adcd619' if table.startswith('Platform/common/') else
         'cac140972cfc4e949e2859adbe4afde10fa3c7ff' if table.startswith('Platform/01-store/') else
         'fa9fa46a0cd5a83353d9a2afe66d7366d3f27853' if table.startswith('Platform/02-installer/') else
         'f5108651a59b5a5cbd202f1b0ad26572012457ee')
    old=[(n,l.split('\t')) for n,l in enumerate(get(ref,table).decode().split('\n'),1) if l and not l.startswith('#')]
    if not positional:_,cols=old.pop(0)
    else:cols=columns
    assert len(old)==len(decoded)
    for (old_line,values),(line,row) in zip(old,decoded):
        before=dict(zip(cols,values))
        for column in declared:
            assert before[column].encode()==row[column].encode(),(table,line,column)
            byte_proof.append(dict(table=table,before=ref,before_line=old_line,line=line,column=column,before_sha256=digest(before[column].encode()),decoded_sha256=digest(row[column].encode())))
assert len(byte_proof)==731
created_cells=[r for r in byte_proof if r['table']==created]
assert len(created_cells)==16 and all(r['line']==r['before_line']+1 for r in created_cells)
assert not source_cells.errors(ROOT,[p for p in en_mirror.english_sources(ROOT,('Platform/','VMS/')) if p.suffix=='.tsv'])
assert not en_mirror.full_english_errors(ROOT,('Platform/03-worker/',))
pair_count=0
for ru,en in en_mirror.pairs(ROOT):
    if '/03-worker/' in str(en) and ru.is_file():
        pair_count+=1;assert not en_mirror.compare(ru.read_text(),en.read_text(),ru,en,ROOT)

mapped=[p for p in paths if not(published.get(p)==author.get(p)==source.get(p))]
oids=sorted({v[1] for t in (published,author,source) for p in mapped if(v:=t.get(p))})
stream=BytesIO(subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(oids)+'\n').encode()))
hashes={}
for oid in oids:
    header=stream.readline().decode().split();assert header[0]==oid and header[1]=='blob'
    hashes[oid]=digest(stream.read(int(header[2])));assert stream.read(1)==b'\n'
rows=[];counts=Counter()
for p in mapped:
    a,b,c=(t.get(p) for t in (published,author,source))
    basis='published3def' if c==a else 'author8f' if c==b else 'append-both-ledger'
    assert basis!='append-both-ledger' or p==ledger
    counts[basis]+=1
    rows.append([p,basis,*[' '.join(v) if v else '-' for v in (a,b,c)],*[hashes[v[1]] if v else '-' for v in (a,b,c)]])
MAP.write_text('# Exact P03 forward basis; fixed source merge '+SOURCE+'; inherited tools/output rows are identity evidence only.\npath\tbasis\tpublished_mode_blob\tauthor_mode_blob\tsource_mode_blob\tpublished_sha256\tauthor_sha256\tsource_sha256\n'+''.join('\t'.join(r)+'\n' for r in rows))
report=dict(published=PUBLISHED,author=AUTHOR,source_merge=SOURCE,merge_bases=sorted(BASES),
            source_delta_files=len(delta),forward_map=str(MAP),forward_map_sha256=digest(MAP.read_bytes()),
            forward_map_rows=len(rows),forward_map_basis=counts,identity_groups=identity,
            ledger_author_rows_appended=2,p04_source_absent=True,registry_exact_published=True,
            machine_trace_capture_row_and_seam_files=13,all_frozen_identity_files=len(frozen['identity_files']),
            calls=55,guard_and_epoch_index_exact_string=guard,rollout_exact_published=True,
            prior_p02_proof_bytes_unchanged=True,source_cell_count=731,source_cell_tables=9,
            created_cells=created_cells,byte_proof=byte_proof,p03_mirror_pairs=pair_count,
            original_map_sha256=digest(get(SOURCE,mp)),original_preservation_unchanged=True,
            output_regeneration=False,runtime_green_claim=False,sut_runs=0,errors=[])
REPORT.write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['source_merge','source_delta_files','forward_map_rows','forward_map_sha256','forward_map_basis','source_cell_count','source_cell_tables','p03_mirror_pairs']},indent=2))
