import json,sys,os,glob,datetime as dt
now=dt.datetime.now(dt.timezone.utc); start=now-dt.timedelta(minutes=60)
def ts(e):
    t=e.get('timestamp');
    return dt.datetime.fromisoformat(t.replace('Z','+00:00')) if t else None
def kind(e):
    t=e.get('type'); m=e.get('message') or {}
    c=m.get('content')
    if t=='assistant':
        if isinstance(c,list) and any(x.get('type')=='tool_use' for x in c if isinstance(x,dict)): return 'a_tool'
        return 'a_final'
    if t=='user':
        if isinstance(c,list) and any(isinstance(x,dict) and x.get('type')=='tool_result' for x in c): return 'u_tool'
        return 'u_msg'
    return None
for f in sys.argv[1:]:
    ev=[]
    name=''
    for line in open(f,errors='ignore'):
        try: e=json.loads(line)
        except: continue
        if e.get('isSidechain'): continue
        k=kind(e); t=ts(e)
        if not name and k=='u_msg':
            c=(e.get('message') or {}).get('content'); s=c if isinstance(c,str) else ' '.join(x.get('text','') for x in c if isinstance(x,dict))
            name=s[:60].replace('\n',' ')
        if k and t: ev.append((t,k))
    ev=[x for x in ev if x[0]>=start-dt.timedelta(minutes=30)]
    idle=tool=0.0; prev=None; last=None
    for t,k in ev:
        if prev:
            a=max(prev[0],start); b=t
            if b>a:
                d=(b-a).total_seconds()
                if prev[1]=='a_final' and k=='u_msg': idle+=d
                elif prev[1]=='a_tool' and k=='u_tool' and d>60: tool+=d
        prev=(t,k); last=t
    if prev and prev[1]=='a_final':
        idle+=(now-max(prev[0],start)).total_seconds()
    n=sum(1 for t,k in ev if t>=start and k=='u_msg')
    print(f"{os.path.basename(os.path.dirname(f))[19:]:28.28} {os.path.basename(f)[:8]} idle={idle/60:5.1f}m longtool={tool/60:5.1f}m msgs_in={n:3d} last={(now-last).total_seconds()/60 if last else -1:5.1f}m ago | {name}")
