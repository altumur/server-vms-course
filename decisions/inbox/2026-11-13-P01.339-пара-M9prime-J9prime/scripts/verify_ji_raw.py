"""Independent check of the J-input (P01.73), P01.254 version. Uses git output and the course repository only; no operator code.
Changes against verify_ji.py of P01.121 (assembled filters P02.52, registry in lessons P02.51/P03.26):
- the filter is the assembled FILTER-JI.json beside the J-input (argv[8]); its blob must equal second_filter_blob of
  PASSPORT-JI.json and its records are compared with check_spec export_lists separately (JI-FILTER.json);
- routing directories are read from the common targets.routing.tsv and every lesson forms/targets.routing.tsv at C;
- named inputs add the lesson registries (targets.tsv, targets.routing.tsv of 01-store, 02-installer, 03-worker);
  lesson forms/export.json must not be in the J-input."""
import json,subprocess,sys,hashlib,re,csv,io
R,C,J_GIT,JC,JI_GIT,JIC,M_GIT,FJI=sys.argv[1:9]
def g(gd,*a): return subprocess.check_output(['git','--git-dir',gd,*a])
def tree(gd,c):
    o={}
    for r in g(gd,'ls-tree','-r','-z','--full-tree',c).split(b'\0'):
        if r:
            m,p=r.split(b'\t',1); mode,t,oid=m.decode().split(); o[p.decode()]=(mode,t,oid)
    return o
res={}
RG=subprocess.check_output(['git','-C',R,'rev-parse','--absolute-git-dir']).decode().strip()
ct={p:v for p,v in tree(RG,C).items() if p.startswith('Platform/')}
jt=tree(J_GIT,JC); ji=tree(JI_GIT,JIC); mt=tree(M_GIT,g(M_GIT,'rev-parse','refs/heads/model').decode().strip())
MK='Platform/COURSE_COMMIT'; FP='Platform/common/acceptance/judge-input-filter.json'
res['J_equals_C_Platform_plus_marker']={p:v for p,v in jt.items() if p!=MK}==ct and MK in jt
marker=g(J_GIT,'cat-file','blob',jt[MK][2]).decode().strip(); res['marker_is_C']=marker==C
FB=open(FJI,'rb').read(); flt=json.loads(FB)
res['assembled_filter_blob_eq_passport']=hashlib.sha1(b'blob %d\0'%len(FB)+FB).hexdigest()==json.load(open(FJI.rsplit('/',1)[0]+'/PASSPORT-JI.json'))['second_filter_blob']
inc={x['path'] for x in flt['files'] if x['disposition']=='include'}; exc={x['path'] for x in flt['files'] if x['disposition']=='exclude'}
res['filter_partition_covers_J']=(inc|exc)==set(jt) and not inc&exc and len(flt['files'])==len(jt)
res['JI_paths_equal_includes']=set(ji)==inc
res['JI_entries_equal_J']=all(ji[p]==jt[p] for p in ji)
res['all_regular_blobs']=all(v[1]=='blob' and v[0] in('100644','100755') for v in ji.values())
cy=re.compile('[Ѐ-ӿ]'); bad=re.compile(r'c_targets|c_store|harness\.py|bcb22c07|P01\.28')
code=('.py','.go','.sh','.c','.cc','.cpp','.h','.js','.ts','.rs')
hits={'code':[],'ru':[],'verdict_or_mutant_path':[],'cyrillic':[],'runner_token':[],'shebang_or_import':[]}
for p,(m,t,o) in ji.items():
    s=p.split('/')
    if p.endswith(code): hits['code'].append(p)
    if 'ru' in s: hits['ru'].append(p)
    if any('mutant' in x.lower() or 'verdict' in x.lower() for x in s): hits['verdict_or_mutant_path'].append(p)
    b=g(JI_GIT,'cat-file','blob',o)
    try:t2=b.decode('utf8')
    except UnicodeDecodeError: continue
    if cy.search(t2): hits['cyrillic'].append(p)
    if bad.search(t2): hits['runner_token'].append(p)
    if t2.startswith('#!') or re.search(r'^(import \w+|from \w+ import|package main|def \w+\()',t2,re.M): hits['shebang_or_import'].append(p)
res['forbidden_hits']=hits
res['filter_not_in_JI']=FP not in ji
res['filter_not_in_M']=FP not in mt
res['JI_J_only_routing_present']='Platform/common/acceptance/forms/targets.routing.tsv' in ji
RTS=['Platform/common/acceptance/forms/targets.routing.tsv']+sorted(p for p in ct if re.fullmatch(r'Platform/\d\d-[a-z0-9-]+/forms/targets\.routing\.tsv',p))
res['routing_tables']=RTS
rt=[l for f in RTS for l in g(RG,'show',C+':'+f).decode().splitlines()]
dirs=set()
for l in rt:
    if l.startswith('#') or not l.strip() or l.startswith('id\t'): continue
    dirs.update(json.loads(l.split('\t')[2]))
missing=sorted(p for p in jt for d in dirs if p.startswith(d+'/') and p not in ji and '/ru/' not in p)
res['routing_dirs']=len(dirs); res['routing_files_missing_in_JI']=missing
res['named_inputs_present']={p:p in ji for p in ['Platform/common/acceptance/spec/acceptance.norms.md','Platform/common/acceptance/spec/acceptance.README.md','Platform/common/acceptance/README.md','Platform/common/acceptance/PROFILE.md','Platform/common/vectors/wire.md','Platform/common/vectors/wire.tsv','Platform/common/vectors/consumers.tsv','Platform/common/acceptance/forms/targets.tsv','Platform/common/acceptance/forms/targets.README.md','Platform/01-store/spec/production-acceptance.md']+[f'Platform/{l}/forms/{f}' for l in ('01-store','02-installer','03-worker') for f in ('targets.tsv','targets.routing.tsv')]}
res['lesson_export_lists_not_in_JI']=not any(re.fullmatch(r'Platform/\d\d-[a-z0-9-]+/forms/export\.json',p) for p in ji)
res['JI_single_parentless_commit']=g(JI_GIT,'rev-list','--count','--all').strip()==b'1' and len(g(JI_GIT,'cat-file','-p',JIC).split(b'parent '))==1
res['JI_refs']=g(JI_GIT,'for-each-ref','--format=%(refname)').decode().split()
res['JI_fsck']=subprocess.run(['git','--git-dir',JI_GIT,'fsck','--full','--strict'],capture_output=True).returncode==0
counts=g(JI_GIT,'count-objects','-v').decode(); phys=sum(int(l.split(':')[1]) for l in counts.splitlines() if l.startswith(('count:','in-pack:')))
reach=len(g(JI_GIT,'rev-list','--objects','--all').splitlines()); res['objects_physical_eq_reachable']=(phys,reach,phys==reach)
res['counts']={'C_Platform':len(ct),'J':len(jt),'J_input':len(ji),'M':len(mt)}
ok=all(v is True for k,v in res.items() if isinstance(v,bool)) and not any(hits.values()) and not missing and all(res['named_inputs_present'].values()) and res['objects_physical_eq_reachable'][2] and res['JI_refs']==['refs/heads/judge-input']
res['OK']=ok
json.dump(res,sys.stdout,indent=1,sort_keys=True); print(); sys.exit(0 if ok else 1)
