"""Prepare INACTIVE P06 review proposals from c81. No active source is written."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json,subprocess,yaml

BASE='c81dd35d5ff850c687c94d251cdc84269e28730d'
OUT=Path(__file__).resolve().parent
def git(p):return subprocess.check_output(['git','show',BASE+':'+p])
def dump(p,v):(OUT/p).write_text(json.dumps(v,ensure_ascii=True,indent=2)+'\n')
sha=lambda b:sha256(b).hexdigest()
def encode(value,lf=False,ascii=False):return json.dumps(value,ensure_ascii=ascii,separators=(',',':'),allow_nan=False).encode()+ (b'\n' if lf else b'')
def weight(items):return sum(len(k.encode())+len(v.encode()) for k,v in items.items())
def packet(note='',folder_members=1,quote_count=0):
 unit='testsub/units/u';folders=[f'{i:032x}' for i in range(8)]
 items={'id':'u','revision':'2','born':'b','deleted':'1','note':note,'quoted':'"'*quote_count,'utf8':'\u0436'}
 writes=[{'op':'put','key':unit,'items':items,'cas':'1'}]
 for ident in folders:
  refs=['testsub/units/'+f'{i:045d}' for i in range(folder_members)]
  writes.append({'op':'put','key':'platform/folders/'+ident,'items':{'name':'F','parent':'','members':','.join(refs)},'cas':'1'})
 writes.extend([{'op':'delete','key':'platform/memberof/'+unit,'cas':'1'},
                {'op':'put','key':'platform/memberof-gone/'+unit,'items':{},'cas':''}])
 # The claim is read/guarded here and saved by a separate existing write.
 # Never duplicate a writes key in guards: CAS of a writes key is its condition.
 guards=[{'key':'testsub/idem/attempt','index':'1'}, {'key':'platform/memberof/parent/units/p','index':'1'}]
 return {'op':'batch','writes':writes,'guards':guards,'id':'p06-c2-example'}
B=1048576
oversize=packet(folder_members=999,quote_count=450000)
def details(p,lf=False,ascii=False):
 raw=encode(p,lf=lf,ascii=ascii)
 headers=('POST /v1/write HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw))+'\r\n\r\n').encode()
 chunks=(format(len(raw),'x')+'\r\n').encode()+raw+b'\r\n0\r\n\r\n'
 return dict(entity_bytes=len(raw),sha256=sha(raw),trailing_LF=lf,ensure_ascii=ascii,
    put_weights=[weight(w['items']) for w in p['writes'] if w['op']=='put'],
    keys=[w['key'] for w in p['writes']],guards=p['guards'],writes=len(p['writes']),guard_count=len(p['guards']),
    within_body_limit=len(raw)<=B,HTTP_framing_bytes_counted_as_entity=False,
    content_length_wire_bytes=len(headers)+len(raw),chunked_data_and_delimiters_bytes=len(chunks),decoded_chunk_entity_bytes=len(raw))
witnesses={'escaping_counterexample':details(oversize)}
assert witnesses['escaping_counterexample']['entity_bytes']>B
assert max(witnesses['escaping_counterexample']['put_weights'])<=B
for delta in (-1,0,1):
 p=packet();empty=len(encode(p));p['writes'][0]['items']['note']='a'*(B+delta-empty)
 d=details(p);assert d['entity_bytes']==B+delta and max(d['put_weights'])<=B
 d['client_PUT_body_bytes']=len(encode({'note':p['writes'][0]['items']['note'],'quoted':'','utf8':'\u0436'}))
 assert d['client_PUT_body_bytes']<B
 witnesses['body_limit'+str(delta)]=d
 if delta==0:
  witnesses['same_JSON_plus_LF']=details(p,lf=True)
  witnesses['same_value_ASCII_escapes']=details(p,ascii=True)
dump('c2-byte-witnesses.json',dict(status='INACTIVE PROPOSAL; codec measurements only',base=BASE,limit=B,
 serializer='UTF-8; ensure_ascii=False; compact comma/colon; allow_nan=False; no BOM; no LF unless flagged',
 packet_shape=packet(),witnesses=witnesses,product_native_runs=0,SUT_runs=0))

rels=json.loads(git('Platform/02-installer/spec/02.1-installer.relations.json'))
assert max(r['no'] for r in rels['rows'])==159
paths=['Platform/02-installer/spec/02.1-installer.norms.md','Platform/02-installer/ru/spec/02.1-installer.norms.md',
 'Platform/02-installer/spec/02.1-installer.relations.json']
rules=[dict(no=160,path='placement.retire_when.delete_after',
  condition='unit.id == numeric AND NOT protected_manual',result='refused:relations',
  relation='when @unit.id = numeric & !protected_manual : absent placement.retire_when.delete_after'),
 dict(no=161,path='worker.deletes[]',condition='unit.id == numeric AND worker.deletes is nonempty',result='refused:relations',relation='@unit.id != numeric'),
 dict(no=162,path='placement.ends',condition='unit.id == numeric AND NOT protected_manual',result='refused:relations',
  relation='when @unit.id = numeric & !protected_manual : absent placement.ends')]
protected_cel='(("fields" in doc.unit && type(doc.unit.fields) == map && doc.unit.fields.exists(f, type(doc.unit.fields[f]) == map && "fixed" in doc.unit.fields[f] && doc.unit.fields[f].fixed == true)) || ("about" in doc && type(doc.about) == map && "field" in doc.about && doc.about.field != "id"))'
for r in rules:
 r['existing_class']='value'
 r['protected_manual_cel_on_form_valid_doc']=protected_cel
 r['numeric_cel_on_form_valid_doc']='doc.unit.id == "numeric"'
 r['refusal_pointer']=('/placement/retire_when/delete_after' if r['no']==160 else '/worker/deletes/<number>' if r['no']==161 else '/placement/ends')
accepted=[];affected=[]
verdicts=[l.split('\t') for l in git('Platform/02-installer/acceptance/1/verdicts.tsv').decode().split('\n') if l and not l.startswith('#')]
for cells in verdicts:
 if cells[0]=='case' or cells[1]!='ok':continue
 p='Platform/02-installer/acceptance/1/cases/'+cells[0]+'.subsystem.yaml'
 doc=yaml.safe_load(git(p));u=doc.get('unit',{});place=doc.get('placement') or {};worker=doc.get('worker') or {}
 if u.get('id')!='numeric':continue
 accepted.append(cells[0]);fields=u.get('fields') or {};about=doc.get('about')
 protected=(isinstance(fields,dict) and any(isinstance(v,dict) and v.get('fixed') is True for v in fields.values())) or (isinstance(about,dict) and about.get('field')!='id')
 if bool(worker.get('deletes')) or not protected and ('ends' in place or isinstance(place.get('retire_when'),dict) and 'delete_after' in place['retire_when']):affected.append(cells[0])
assert len(accepted)==21 and not affected
dump('c3-loader-proposal.json',dict(status='INACTIVE; proposed IDs160-162 not allocated/activated',base=BASE,
 active_paths_proposed=paths,protected_manual='A numeric unit has a declared fixed unit field, OR about with field != id. Numeric units cannot be targets of worker.creates (P02.3 catalogue rule); therefore admissible made rows cannot bypass this protection.',
 rules=rules,existing_rule49='unchanged: numeric+unplaced.delete_after stays refused',
 proposed_schema_view_delta=[],schema_view_reason='These are semantic cross-field relations, not new structure. Current schemas have no numeric condition. Add only the existing compiled relation records; canonical schema/view/property sets and values remain byte-identical.',
 schema_hashes={p:sha(git(p)) for p in ('Platform/02-installer/spec/02.1-installer.schema.json','Platform/02-installer/spec/02.2-installer.view.schema.json')},
 corpus_plan='Leave all947 current files/verdicts/classes and220 canonical files untouched. New witnesses stay in this inactive inbox until Architect assigns their executable scope. No new refusal class, role, rights, P03 or loader algorithm is activated here.',
 accepted_numeric_cases=accepted,newly_incompatible_accepted_cases=affected,
 proposed_witnesses=[dict(case='p06-c3-'+key,id='numeric' if numeric else 'name',fixed=protected,mechanism=mechanism,expect='refused:relations' if numeric and (mechanism=='worker.deletes' or not protected) else 'ok')
  for key,numeric,protected,mechanism in [('numeric-retire',True,False,'retire_when.delete_after'),('numeric-ends',True,False,'ends'),('numeric-delete',True,False,'worker.deletes'),('fixed-ends',True,True,'ends'),('fixed-retire',True,True,'retire_when.delete_after'),('fixed-delete',True,True,'worker.deletes'),('named-retire',False,False,'retire_when.delete_after'),('named-ends',False,False,'ends'),('named-delete',False,False,'worker.deletes')]],
 open_decision='Approve exact protection predicate and conditional IDs; compiled CEL/own-path output must be produced from the approved normative relation source, not guessed here. Existing159 and rule49 unchanged.'))
proposal=json.loads((OUT/'c3-loader-proposal.json').read_bytes())
case_docs=[]
for witness in proposal['proposed_witnesses']:
 numeric=witness['id']=='numeric'
 doc={'name':'probe','unit':{'rows':'units','id':'numeric' if numeric else 'name','fields':{'name':{'type':'string','required':True},'until':{'type':'float'},'retired':{'type':'bool'}}},'placement':{'capacity':{'default':1}},'worker':{'exec':'/usr/lib/probe/worker'}}
 if witness['fixed']:doc['unit']['fields']['pin']={'type':'string','fixed':True}
 if witness['mechanism']=='worker.deletes':doc['worker']['deletes']=['units']
 elif witness['mechanism']=='ends':doc['placement']['ends']={'field':'until','never':0}
 else:doc['placement']['retire_when']={'field':'retired','in':[True],'delete_after':1}
 case_docs.append(dict(case=witness['case'],doc=doc,proposed_expect=witness['expect'],status='INACTIVE independent witness, not part of947/220'))
dump('c3-cases.proposed.json',case_docs)

turn='Platform/common/vectors/turn/cases.tsv';rows=[l.split('\t') for l in git(turn).decode().split('\n') if l and not l.startswith('#')]
ids=['placement-take-empty','placement-take-released','placement-busy-live','placement-take-stale','placement-first-sight','placement-unreadable','placement-take-conflict','placement-renew','placement-guard','placement-guard-412','placement-release','placement-unknown-take-applied','placement-unknown-take-lost','placement-unknown-take-foreign','placement-unknown-renew']
out=['# INACTIVE proposed operations-turn rows; not read by current consumers or wire.','case\tinput\texpect\tnote']
for cells in rows[1:]:
 if cells[0] not in ids:continue
 v=json.loads(cells[1]);v['kind']='operations';v['turn']='testsub/operations-turn';v['me']={}
 for event in v['steps']:
  if isinstance(event.get('read'),dict):event['read'].pop('manifest_rev',None)
 expect=json.loads(cells[2])
 for event in expect:
  if isinstance(event,dict) and isinstance(event.get('write'),dict):event['write'].pop('manifest_rev',None)
  if isinstance(event,dict) and isinstance(event.get('guard'),dict):event['guard']['key']='testsub/operations-turn'
 out.append('\t'.join([cells[0].replace('placement-','operations-',1),json.dumps(v,separators=(',',':')),json.dumps(expect,separators=(',',':')),'Proposed C4 common turn obligation only; epoch barrier and real leader IO remain separate.']))
assert len(out)==17
(OUT/'c4-turn-cases.proposed.tsv').write_text('\n'.join(out)+'\n')
selector='(owner == "04-controller" && json(row["input"])["kind"] == "placement") || (owner in ["08-domain","09-agent"] && json(row["input"])["kind"] == "signer") || (owner == "06-console" && json(row["input"])["kind"] == "operations")'
wire=dict(package='common/turn',table='cases.tsv',surface='vectors',header='case,input,expect,note',inputs=json.dumps([dict(variant='',when=selector,cells={'input':{'column':'input'}})],separators=(',',':')),files='{}',expect='[{"variant":"","code":0,"value":{"column":"expect","decode":"json"}}]',compare='turn',markers='[]',native='{"type":"array","frame":"json"}',norm='common/vectors/turn/README.md#run')
(OUT/'c4-wire-row.proposed.tsv').write_text('# INACTIVE: compare=turn needs an approved wire form; current closed compare list rejects it.\n'+'\t'.join(wire)+'\n'+'\t'.join(wire.values())+'\n')
dump('c4-turn-proposal.json',dict(status='INACTIVE; no draft activation or runtime assignment',base=BASE,old_turn_sha256=sha(git(turn)),old_cases=33,
 proposed_cases=15,source_of_cases='Generic placement term/CAS/unknown/guard cases with no manifest gate; explicit new operations form, NOT signer relabeling. Placement-specific plan barrier cases deliberately excluded.',
 consumer_row=['common/turn','cases.tsv','06-console','common/vectors/turn/README.md: own operations turn; ADR-0127 P06 C4'],wire_row=wire,
 required_form_decision='Existing WIRE closed compares omit turn. Propose narrowly adding turn for common/turn only, with existing c_state_vectors.turn_errors mark freshness/current-attempt behavior and full structural equality for all other cells. Do not approximate with ignored holders, value or signer stable identity. No code/form activation until Architect approval.',
 semantics=['holder is a fresh unique attempt label, no manifest_rev and no stable process-instance holder','@new must not reuse any mark already emitted in this case; @same must equal current attempt','input read marks are placeholders substituted by the owned adapter before ordinary turn code; output must contain real labels, not literal placeholders','existing placement and signer rows/owners/expected bytes unchanged','held proves only turn capture; operations-epoch CAS barrier, step ticket/generation guards, two leaders and late writes remain separate P06.9 real-IO obligations'],
 active_paths_proposed=['Platform/common/vectors/turn/README.md','Platform/common/ru/vectors/turn/README.md',turn,'Platform/common/vectors/consumers.tsv','Platform/common/vectors/wire.tsv','Platform/common/vectors/WIRE.md','Platform/common/contracts/turn.md','Platform/common/ru/contracts/turn.md'],
 no_new_native_command=True,no_existing_roster_replacement=True))

request='CALL console-folder-create {"name":"\u0436"}'
def fixture(text,expected,decoded=None):return dict(source=text,expected=expected,decoded_request=decoded,decoded_sha256=sha(decoded.encode()) if decoded is not None else None)
outer=json.dumps(request,ensure_ascii=True);prefix='# cell-json: request\n# owned positional source fixture\n';row=lambda cell:'owned-first\t1\t'+cell+'\t{"ok":true}\n'
fixtures=[fixture(prefix+row(outer),'valid; first data physical3',request),
 fixture(prefix+row(json.dumps('CALL console-folder-create {invalid-inner')),'valid outer; invalid inner remains opaque','CALL console-folder-create {invalid-inner'),
 fixture(prefix+row('not-json'),'form error'),fixture(prefix+row('null'),'form error'),fixture(prefix+row('"\\ud800"'),'form error'),
 fixture(prefix.replace('request\n','request,request\n',1)+row(outer),'form error: duplicate declaration column'),
 fixture(prefix+row(outer).replace('\t1\t','\t',1),'form error: wrong width')]
dump('source-binding-proposal.json',dict(status='INACTIVE proposal; shared checker/reader unchanged',base=BASE,
 exact_path='Platform/06-console/acceptance/8/seams.tsv',columns=['scenario','step','request','expect'],positional=True,
 binding_before='No source_cells wire_headers binding for this seams path',marker_grammar='Existing common source-cells declaration unchanged',
 scope='Only this exact path. No glob over all seams, no implicit header/data guess, no new decoder or recursive decode.',
 binding_delta=dict(path='skills/lesson-spec/scripts/source_cells.py',entry={'Platform/06-console/acceptance/8/seams.tsv':[['scenario','step','request','expect'],True]}),
 reader_delta='Matching exact source_table.wire_forms binding via reader owners through coord103; same four original columns; no runtime aliases.',
 required_checks=['existing unmarked source and four rows unchanged','valid declared first row retained at original+1 physical line','outer1decode leaves internal JSON quotes/backslashes','valid outer invalid inner passes to existing CALL semantic parser','invalid outer errors before build/dispatch','same binding independent of unrelated cwd; undeclared/unrelated paths unchanged','all marked column cells covered by before/decoded SHA; raw table SHA separate'],fixtures=fixtures))
