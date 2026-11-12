import subprocess,json,sys,os,hashlib
B,C,M_,J_=sys.argv[1:5]; P=B+'/pair-'+C[:12]; S='/home/pilot/server-vms-course/.git'
def g(d,*a,inp=None): return subprocess.run(['git','--git-dir='+d,*a],input=inp,capture_output=True,check=True).stdout
def tree(d,c):
    o={}
    for e in g(d,'ls-tree','-r','-z',c).split(b'\0'):
        if e:
            h,p=e.split(b'\t',1); m,t,b=h.split(); o[p.decode()]=(m.decode(),t.decode(),b.decode())
    return o
r={}
Cm=tree(S,C); Cp={p:v for p,v in Cm.items() if p.startswith('Platform/')}
Mg,Jg=P+'/M.git',P+'/J.git'
J=tree(Jg,J_); M=tree(Mg,M_)
# P01.180: the filter is assembled from the common filter and lesson forms/export.json (P02.52); the
# assembled bytes are FILTER-M.json beside the pair, and they are cross-checked with check_spec's own
# assembler (skills/lesson-spec/scripts/export_lists.py) on an archive of exact C.
FM=open(P+'/FILTER-M.json','rb').read()
f={x['path']:x['disposition'] for x in json.loads(FM)['files']}
sys.path.insert(0,B+'/archive-C/skills/lesson-spec/scripts'); sys.dont_write_bytecode=True
import export_lists
asm,errs,_st=export_lists.assemble(B+'/archive-C')
r['FILTER_M_eq_check_spec_assembly']=(not errs) and {x['path']:x['disposition'] for x in asm['model']}==f
r['FILTER_M_blob']=hashlib.sha1(b'blob %d\0'%len(FM)+FM).hexdigest()
mk='Platform/COURSE_COMMIT'; jm=dict(J); mark=jm.pop(mk,None)
r['J_minus_marker_eq_C_Platform']=jm==Cp; r['marker_text']=g(Jg,'show',J_+':'+mk).decode().strip()==C
r['every_J_path_in_filter_or_marker']=all(p in f for p in jm)
exp={p:v for p,v in J.items() if p!=mk and f.get(p)=='model_and_judge'}
mm=dict(M); mmk=mm.pop(mk,None)
r['filter_J_eq_M']=mm==exp; r['M_marker_present']=mmk is not None; r['M_marker_eq_J_marker']=mmk==mark
jo=[p for p in J if p not in M]; r['J_only_absent_M']=not any(p in M for p in jo)
r['crl_README_in_M']='Platform/common/vectors/crl/README.md' in M; r['crl_cases_not_M']='Platform/common/vectors/crl/cases.tsv' not in M
r['PAC_not_M']=not any('acceptance/spec/acceptance.' in p for p in M); r['PAC_in_J']=sum('acceptance/spec/acceptance.' in p for p in J)==4
r['ru_not_in_M']=not any(p.startswith('Platform/common/ru/') or '/ru/' in p for p in M)
for n,d,c in (('M',Mg,M_),('J',Jg,J_)):
    refs=g(d,'for-each-ref','--format=%(refname) %(objectname)').decode().split('\n'); refs=[x for x in refs if x]
    r[n+'_refs']=refs
    r[n+'_parentless']=g(d,'rev-list','--parents',c).decode().split()==[c]
    r[n+'_all_commits']=g(d,'rev-list','--all').decode().split()==[c]
    phys={l.split()[0] for l in g(d,'cat-file','--batch-all-objects','--batch-check').decode().splitlines()}
    reach={l.split()[0] for l in g(d,'rev-list','--objects','--all').decode().splitlines()}
    r[n+'_physical_eq_reachable']=phys==reach; r[n+'_objects']=len(phys)
    if n=='M': Mo=phys
    else: Jo=phys
    q=subprocess.run(['git','--git-dir='+d,'fsck','--full','--strict'],capture_output=True,text=True); r[n+'_fsck']=(q.returncode,(q.stdout+q.stderr).strip()[:200])
    r[n+'_commit']=g(d,'log','-1','--format=%an|%ae|%at|%s|%b',c).decode().strip()[:220]
    r[n+'_extra_files']=sorted(x for x in os.listdir(d) if x not in('objects','refs','HEAD','config','packed-refs'))
    r[n+'_hooks_info']=[x for x in ('hooks','info','logs') if os.path.exists(d+'/'+x)]
jb={v[2] for p,v in J.items() if p not in M}; mb={v[2] for v in M.values()}
r['J_only_blobs_absent_M_objects']=not ((jb-mb)&Mo); r['J_only_distinct']=len(jb-mb); r['shared_blobs_with_J_only_paths']=len(jb&mb)
r['counts']={'M':len(M),'J':len(J),'J_only':len(jo),'C_Platform':len(Cp),'filter_mj':sum(v=='model_and_judge' for v in f.values())}
r['private_outside_M']=[x for x in os.listdir(P)]

# P01.88: wire.tsv in M, wire.cases.tsv and the case tables of both wire files not in M
def wire_tables(path):
    rows=[l.split('\t') for l in g(S,'show',C+':'+path).decode().split('\n') if l and not l.startswith('#')]
    return {f"Platform/{x[0].split('/')[0]}/vectors/{x[0].split('/',1)[1]}/{x[1]}" for x in rows[1:]}
wt=wire_tables('Platform/common/vectors/wire.tsv'); wc=wire_tables('Platform/common/vectors/wire.cases.tsv')
r['wire_tsv_in_M']='Platform/common/vectors/wire.tsv' in M
r['wire_cases_not_M']='Platform/common/vectors/wire.cases.tsv' not in M and 'Platform/common/vectors/wire.cases.tsv' in J
r['case_tables_of_wire_not_M']=sorted(p for p in wt if p in M); r['case_tables_of_wire_cases_not_M']=sorted(p for p in wc if p in M)
r['case_tables_counts']={'wire':len(wt),'wire_cases':len(wc)}
r['scenarios_seams_not_M']=sorted(p for p in M if '/acceptance/' in p and p.endswith(('/scenarios.tsv','/seams.tsv')))
print(json.dumps(r,ensure_ascii=False,indent=1))
json.dump(r,open(B+'/VERIFY.json','w'),ensure_ascii=False,indent=1)
