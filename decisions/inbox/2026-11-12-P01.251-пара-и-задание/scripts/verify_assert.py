"""P01.251: fail on a false/missing export invariant, rather than merely printing verification JSON.
This wraps the P01.180-derived checks with exact roster/ref/fsck assertions and an explicit M⊂J map comparison.
"""
from pathlib import Path
import json,subprocess,sys
B=Path(__file__).resolve().parent.parent;C=(B/'C.txt').read_text().strip();P=B/('pair-'+C[:12]);r=json.loads((B/'VERIFY.json').read_text())
for k,v in r.items():
 if isinstance(v,bool):assert v,(k,v)
for n,ref in [('M','model'),('J','judge')]:
 assert r[n+'_fsck'][0]==0,(n,r[n+'_fsck'])
 assert r[n+'_refs']==['refs/heads/'+ref+' '+subprocess.check_output(['git','--git-dir',str(P/(n+'.git')),'rev-parse',ref]).decode().strip()]
 assert not r[n+'_extra_files'] and not r[n+'_hooks_info'],n
for k in ['case_tables_of_wire_not_M','case_tables_of_wire_cases_not_M','scenarios_seams_not_M']:assert r[k]==[],k
assert r['counts']['M']==788 and r['counts']['J']==3562
ji=json.loads((B/'VERIFY-JI.json').read_text());assert ji['OK']
for k,v in ji.items():
 if isinstance(v,bool) and k!='orig_rules_output_OK':assert v,(k,v)
jif=json.loads((B/'JI-FILTER.json').read_text());assert jif['equal_check_spec_export_lists_judge']
assert json.loads((B/'passport/CONTROLS.json').read_text())['OK']
def tree(d,ref):
 out={}
 for x in subprocess.check_output(['git','--git-dir',str(d),'ls-tree','-rz',ref]).split(b'\0'):
  if x:h,p=x.split(b'\t',1);out[p.decode()]=h.decode()
 return out
m=tree(P/'M.git','model');j=tree(P/'J.git','judge');assert all(j.get(p)==v for p,v in m.items())
subset={'M_files':len(m),'J_files':len(j),'matched':sum(j.get(p)==v for p,v in m.items()),'OK':True};(B/'M-SUBSET-J.json').write_text(json.dumps(subset,indent=1)+'\n')
out={'C':C,'pair_invariants':True,'J_input_classified_checks':True,'assembled_filters_equal_check_spec':True,'passport_separate_controls':True,'M_subset_J':subset,'OK':True};(B/'VERIFY-ALL.json').write_text(json.dumps(out,indent=1)+'\n');print(json.dumps(out,indent=1))
