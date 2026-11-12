"""P01.251: bind the reviewed filter deltas and a green check on exact C, then invoke the unchanged pair operator once.
The authority is the P01.251 assignment (same release procedure as accepted P01.180); no delivery, pin choice or root call.
"""
from pathlib import Path
import json,hashlib,subprocess,datetime,time,sys
B=Path(__file__).resolve().parent.parent
C=(B/'C.txt').read_text().strip();OLD='41a9493fb08c293a570c006019995a64a599f68b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=1)+'\n')
assert (B/'CHECK-SPEC-C.exit').read_text().strip()=='0'
pf=json.loads((B/'PREFLIGHT.json').read_text());delta=json.loads((B/'FILTER-DELTA.json').read_text())
assert pf['C']==C and all(pf[k]=='pass' for k in ['classification','case_boundary','lexical_guard'])
expected={'Platform/05-resource/forms/decision-order.tsv':('model_and_judge','exclude'),'Platform/05-resource/forms/decision-order.tsv.schema.json':('judge_only','exclude'),'Platform/common/acceptance/forms/stand-environment.tsv':('model_and_judge','include'),'Platform/common/acceptance/forms/stand-environment.tsv.schema.json':('judge_only','exclude')}
assert {x['path']:(x['M'],x['JI']) for x in delta['added']}==expected and not delta['changed'] and not delta['removed']
reviews={'task':'P01.251','C':C,'previous_review_manifest':{'path':'reviews/P01.180-FILTER-REVIEWS.json','sha256':sha(B/'reviews/P01.180-FILTER-REVIEWS.json'),'original_evidence':'/home/pilot/run-p01180-pair-20261112','accepted_receipt':'reviews/P01.180-accepted.json'},'deltas':[{'task':'P01.250','author_provider':'Anthropic (Claude)','reviewer_provider':'OpenAI (Codex)','review':'reviews/P01.250-judge.txt','sha256':sha(B/'reviews/P01.250-judge.txt'),'accepted_receipt':'reviews/P01.250-accepted.json','records':['Platform/common/acceptance/forms/stand-environment.tsv','Platform/common/acceptance/forms/stand-environment.tsv.schema.json']},{'task':'P05.9','author_provider':'OpenAI (Codex)','reviewer_provider':'Anthropic (Claude)','review':'reviews/P05.9-Claude.md','sha256':sha(B/'reviews/P05.9-Claude.md'),'accepted_receipt':'reviews/P05.9-accepted.json','records':['Platform/05-resource/forms/decision-order.tsv','Platform/05-resource/forms/decision-order.tsv.schema.json']}],'delta':{'path':'FILTER-DELTA.json','sha256':sha(B/'FILTER-DELTA.json'),'counts':delta['counts']},'all_delta_records_covered':True,'operators':'Unchanged P02.52, reviewed by judge/Codex; inherited P01.180 operator digests verified separately','limitation_inherited':'P01.180: 9 P01.228 schemas had no different-provider review; all are withheld from M and J-input.'}
for r in reviews['deltas']:
 a=json.loads((B/r['accepted_receipt']).read_text());assert a['status']=='accepted'
assert set(p for r in reviews['deltas'] for p in r['records'])==set(expected)
dump(B/'FILTER-REVIEWS.json',reviews)
closure={'task':'P01.251','C':C,'previous_pair_C':OLD,'scope':'Local pair, M passport, J-input; no delivery, no pin selection, no generation/probe/model run','authority':'Task P01.251 requests the same release procedure as accepted P01.180. Its note/answered exclude the start probe pending P01.252. C includes 24182a5c4 and accepted P05.9.','preflight':'PREFLIGHT.json','preflight_sha256':sha(B/'PREFLIGHT.json'),'check':'CHECK-SPEC-C.out','check_sha256':sha(B/'CHECK-SPEC-C.out'),'check_exit':0,'filter_reviews':'FILTER-REVIEWS.json','filter_reviews_sha256':sha(B/'FILTER-REVIEWS.json'),'filter_sources':pf['filter_sources'],'assembled_filter_blob':pf['assembled_filter_blob'],'assembled_filter_sha256':pf['assembled_filter_sha256'],'operator_sha256':pf['operator_sha256'],'changes':'Full source/view content delta will be in DELTA-PAIR.json and DELTA-PAIR.md; it is not restricted to the four filter records.'}
dump(B/'SOURCE-CLOSURE-P01-251.json',closure)
a={'version':1,'authorization':'ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW','source_C':C,'filter_blob':pf['assembled_filter_blob'],'wire_blob':pf['wire_blob'],'derived_sha256':pf['derived_sha256'],'source_acceptance_sha256':sha(B/'SOURCE-CLOSURE-P01-251.json'),'green_check_sha256':sha(B/'CHECK-SPEC-C.out'),'different_provider_filter_review_sha256':sha(B/'FILTER-REVIEWS.json'),'filter_author_provider':'Anthropic + OpenAI (per-delta matrix in FILTER-REVIEWS.json)','filter_reviewer_provider':'OpenAI + Anthropic + Moonshot (per-delta FILTER-REVIEWS.json)'}
dump(B/'AUTHORIZATION.json',a)
op=B/'operator/b7_export_pair.py';argv=[sys.executable,'-B',str(op),'--source-git-dir','/home/pilot/server-vms-course/.git','--course-commit',C,'--output',str(B/('pair-'+C[:12])),'--authorization-json',str(B/'AUTHORIZATION.json')]
start=time.monotonic();utc=datetime.datetime.now(datetime.timezone.utc).isoformat();p=subprocess.run(argv,cwd=B,capture_output=True);(B/'stdout.log').write_bytes(p.stdout);(B/'stderr.log').write_bytes(p.stderr)
dump(B/'RUN.json',{'task':'P01.251','invocation_count':1,'argv':argv,'cwd':str(B),'start_utc':utc,'elapsed_seconds':time.monotonic()-start,'exit':p.returncode,'operator_sha256':sha(op),'stdout_sha256':sha(B/'stdout.log'),'stderr_sha256':sha(B/'stderr.log')})
print('pair exit',p.returncode);print(p.stdout.decode()[:2000]);print(p.stderr.decode()[:1000]);sys.exit(p.returncode)
