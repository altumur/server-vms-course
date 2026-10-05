import sys, time, tempfile, statistics, importlib.util as u
sys.path.insert(0, "/Users/murat/w2c/server-vms-course/vmsserver")
sp=u.spec_from_file_location("cse","/Users/murat/w2c/server-vms-course/vmsserver/tests/configstore_election.py")
m=u.module_from_spec(sp); sp.loader.exec_module(m)
from w2cplatform.variables import open_vars
root=tempfile.mkdtemp()
tuning = sys.argv[1] if len(sys.argv)>1 else "default"
nodes=[m.Node(k, root, tuning) for k in range(3)]
nodes[0].start()
for n in nodes[1:]: n.start(join=nodes[0].adv)
time.sleep(2)
try:
    st=[open_vars(n.url()).status() for n in nodes]
    lead=next(i for i,x in enumerate(st) if x.get("state")=="leader")
    for which, nd in (("leader", nodes[lead]), ("follower", nodes[(lead+1)%3])):
        v=open_vars(nd.url("timeout=10"))
        v.put("x/a", {"a":"1"})
        for op in ("get","put"):
            ts=[]
            for i in range(200):
                t=time.perf_counter()
                v.get("x/a") if op=="get" else v.put("x/a", {"a":str(i)})
                ts.append(time.perf_counter()-t)
            print(tuning, which, op, f"median {statistics.median(ts)*1000:.2f} ms, p90 {sorted(ts)[180]*1000:.2f} ms")
finally:
    for n in nodes: n.proc.kill()
