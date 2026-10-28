import json,sys,glob,os,datetime as dt
now=dt.datetime.now(dt.timezone.utc);start=now-dt.timedelta(minutes=60)
P=lambda t:dt.datetime.fromisoformat(t.replace('Z','+00:00'))
res={}
for f in glob.glob(os.path.expanduser('~/.codex/sessions/2026/10/28/*.jsonl')):
    if os.path.getmtime(f)<start.timestamp(): continue
    roots=[];ev=[]
    for l in open(f,errors='ignore'):
        try:e=json.loads(l)
        except:continue
        p=e.get('payload') or {}
        if e.get('type')=='session_meta': roots=p.get('runtime_workspace_roots') or [p.get('cwd')]
        k=p.get('type')
        if k in('task_started','task_complete'): ev.append((P(e['timestamp']),k))
    name=next((r for r in roots[1:2]), roots[0] if roots else '?')
    busy=0.0; cur=None
    for t,k in sorted(ev):
        if k=='task_started': cur=t
        elif cur: 
            a=max(cur,start); 
            if t>a: busy+=(t-a).total_seconds()
            cur=None
    if cur: busy+=(now-max(cur,start)).total_seconds()
    n=sum(1 for t,k in ev if k=='task_started' and t>=start)
    key=name.replace('/Users/murat/w2c/','')
    b,nn=res.get(key,(0,0)); res[key]=(b+busy,nn+n)
for k,(b,n) in sorted(res.items()):
    print(f"{k:45.45} busy={b/60:5.1f}m idle={60-min(60,b/60):5.1f}m tasks={n}")
