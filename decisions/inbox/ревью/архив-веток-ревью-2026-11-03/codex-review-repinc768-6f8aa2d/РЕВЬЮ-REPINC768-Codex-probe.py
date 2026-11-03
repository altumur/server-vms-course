"""Public label grammar and exact P01 plans/qualification evidence; CT103, own SUT0."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit

runtime,spec,packet=map(Path,sys.argv[1:4]);label=sys.argv[4]
sys.path.insert(0,str(runtime/'runner'))
import assembly
import c_execute
import c_targets
import console
import l03
import l08
import l09

bad=('kind=last','kind="last" junk','kind="last",junk',
     'kind="last"worker="w-1"','kind="last",,worker="w-1"')
valid=('', ' ', 'a="b"', ' a="b" , c="d", ',
       'c="d",a="b"', 'a="comma,b",c="escaped\\\"quote"', 'a="back\\\\slash",c="line\\n"')
st=SimpleNamespace(url='http://127.0.0.1:1',as_store=lambda req:(None,req))
controls=[]
def check(request,raw):
    with patch.object(l09,'http',return_value=(200,{'content-type':['text/plain']},raw)), \
         patch.object(l08,'request',return_value=(200,raw,{'content-type':'text/plain'})):
        return console.attempt(st,'own','1',request,'200 ~x',{})[0]
for labels in bad:
    raw=('x{'+labels+'} 1\n').encode()
    for request in ('GET /metrics','console GET /metrics'):
        why=check(request,raw)
        assert bool(why)==(label=='new'),(labels,request,why)
        controls.append(dict(labels=labels,request=request,rejected=bool(why)))
    why=[];series=l09.metrics(raw+b'x 2\n',why)
    if label=='new':
        assert series=={('x',''):2} and any('not a series line' in s for s in why)
        assert not any('twice' in s for s in why)
for labels in valid:
    raw=('x{'+labels+'} 1\n').encode()
    for request in ('GET /metrics','console GET /metrics'):assert not check(request,raw),(labels,request)
for raw in (b'x{} 1\nx 2\n',b'x{a="b",c="d"} -1\nx{c="d",a="b"} 0\n'):
    for request in ('GET /metrics','console GET /metrics'):assert check(request,raw)
result=dict(label_controls=controls,valid_forms=len(valid),duplicate_forms=2)

if label=='new':
    pin=(runtime/'SPEC_VERSION').read_text().strip()
    parts={owner:SimpleNamespace(doc=dict(keys={'role':'acc'},stand={},adapters={},vectors={})) for owner in assembly.MODULES}
    for target in c_targets.CONNECTED_TARGETS:
        for owner,group,key in (*target.requires,*target.requires_any):
            if group:parts[owner].doc[group][key]='PLAN-ONLY'
    store=parts['01-store'].doc
    store['keys'].update(store_build='raft',role='acc',role_header='X-Role',request_line_limit=8192)
    store['stand']['store']='own -rights {rights}'
    store['stand']['spoil-row']='own {data} {key} {what}'
    composition=SimpleNamespace(parts=parts,specs=spec,spec_version=pin)
    ids=['P/01.1/door','P/01.2/rights','P/01.3/daemon','P/01.3/group']
    vector_ids=[f'P/{n:02}/vectors-store-client' for n in range(1,7)]
    plans={p['id']:p for p in c_targets.plan(composition,ids+vector_ids)}
    assert len(plans)==10 and all(p['status']=='ready' for p in plans.values())
    counts={}
    for ident in ids:
        inp=next(i for i in plans[ident]['inputs'] if 'scenario_steps' in i)
        counts[ident]=[len(inp['scenario_steps']),sum(map(len,inp['scenario_steps'].values()))]
    assert list(counts.values())==[[32,220],[10,54],[14,111],[8,153]],counts
    g=next(i for i in plans[ids[3]]['inputs'] if 'scenario_steps' in i)
    d=next(i for i in plans[ids[2]]['inputs'] if 'scenario_steps' in i)
    source='Platform/01-store/acceptance/3/scenarios.tsv'
    data=c_targets.table(spec/source)[1:]
    grouped={cells[0] for _,cells in data if cells[2].startswith('@group-setup ')}
    assert set(g['scenario_steps'])==grouped and not grouped&set(d['scenario_steps'])
    assert grouped|set(d['scenario_steps'])=={cells[0] for _,cells in data}
    for line,cells in data:
        owners=[p for p in (g,d) if any(s['id']==cells[1] and s['line']==line for s in p['scenario_steps'].get(cells[0],[]))]
        assert len(owners)==1,(line,cells[:2])
    for row in plans.values():
        for inp in row['inputs']:
            path=spec/inp['path']
            if 'sha256' in inp:assert hashlib.sha256(path.read_bytes()).hexdigest()==inp['sha256']
    omitted=copy.deepcopy(composition)
    omitted.parts['01-store'].doc['stand']['store']='own --implicit-rights'
    omitted.parts['01-store'].doc['stand'].pop('spoil-row')
    skipped=c_targets.plan(omitted,['P/01.2/rights','P/01.3/daemon'])
    assert set(skipped[0]['not_executed_scenarios'])=={'13-rights-file','14-never-boundaries','15-rights-comment'}
    assert set(skipped[1]['not_executed_scenarios'])=={'20-spoil-row','22-spoil-row-guard'}
    build_status={}
    for build in ('raft','box',None):
        modified=copy.deepcopy(composition);modified.parts['01-store'].doc['keys']['store_build']=build
        build_status[str(build)]=c_targets.plan(modified,['P/01.3/group'])[0]['status']
    assert build_status=={'raft':'ready','box':'not_applicable','None':'not_executed'}
    # Real expansion of the corrected 1025-byte key and equivalence of the percent-coded GET target.
    rows=[cells for _,cells in c_targets.table(spec/'Platform/01-store/acceptance/1/scenarios.tsv')[1:] if cells[0]=='29-key-1025']
    expanded=[l03.BIG.sub(lambda m:'x'*int(m[1]),cells[2]) for cells in rows]
    keys=[]
    for i in range(3):
        _,method,path,body,_=l03.parse_request(expanded[i],'29-key-1025',str(i+1))
        if method=='GET':key=parse_qs(urlsplit(path).query)['key'][0]
        else:
            value=json.loads(body);key=value['key'] if i==0 else value['guard']['key']
        keys.append(key)
    assert [len(k.encode()) for k in keys]==[1025]*3 and keys[0]==keys[1]

    old_check='20261030T183121Z-repin340-Go';new_check='20261030T184857Z-repinc768-Go'
    summaries={c:json.loads((packet/'evidence'/c/'out/summary.json').read_text()) for c in (old_check,new_check)}
    assert not summaries[old_check]['green'] and summaries[new_check]['green']
    assert all(s['inputs_unchanged'] for s in summaries.values())
    def report(check,run):
        path=run['report'].split('/result/',1)[1]
        return json.loads((packet/'evidence'/check/path).read_text())
    qualified={};scenarios=steps=0
    for ident in ids:
        check=new_check if ident==ids[0] else old_check
        run=next(r for r in summaries[check]['runs'] if r['target']==ident)
        raw=report(check,run);coverage=c_execute.coverage(plans[ident],raw)
        assert run['green'] and raw['green'] and not coverage['errors'],(ident,coverage)
        records=raw['scenarios'];n=0
        for values in records.values():
            if isinstance(values,dict):values=values['steps']
            assert all(s['ok'] is True for s in values);n+=len(values)
        assert [len(records),n]==counts[ident]
        scenarios+=len(records);steps+=n
        qualified[ident]=dict(check=check,counts=counts[ident],coverage_errors=coverage['errors'])
        if ident==ids[0]:assert len(raw['raw_http'])==34 and all(s['ok'] is True for s in raw['raw_http'])
        if ident==ids[1]:assert len(raw['variants']['rights-evaluator'])==22 and all(s['ok'] is True for s in raw['variants']['rights-evaluator'])
    assert (scenarios,steps)==(64,538)
    vector_counts={}
    for ident in vector_ids:
        run=next(r for r in summaries[new_check]['runs'] if r['target']==ident)
        raw=report(new_check,run);coverage=c_execute.coverage(plans[ident],raw)
        assert run['green'] and raw['green'] and not coverage['errors']
        assert len(raw['vectors'])==20 and all(s['ok'] is True for s in raw['vectors'])
        old_run=next(r for r in summaries[old_check]['runs'] if r['target']==ident)
        old_raw=report(old_check,old_run)
        assert len(old_raw['vectors'])==20 and all(s['ok'] is True for s in old_raw['vectors'])
        assert c_execute.coverage(plans[ident],old_raw)['errors']==['package spec/table/consumer/variant coverage differs from inventory']
        repaired=copy.deepcopy(old_raw)
        for v in repaired['vectors']:v['spec_version']=pin
        assert not c_execute.coverage(plans[ident],repaired)['errors']
        vector_counts[ident]=20
    result.update(plan_counts=counts,group_scenarios=sorted(grouped),build_status=build_status,key_byte_lengths=[1025]*3,
                  qualified=qualified,qualified_total=[64,538],raw_http=34,rights_evaluator=22,
                  vector_counts=vector_counts,old_vector_failure_only_pin=True)
Path(os.environ['CHECK_OUT'],'controls.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='label_controls'},ensure_ascii=False))
