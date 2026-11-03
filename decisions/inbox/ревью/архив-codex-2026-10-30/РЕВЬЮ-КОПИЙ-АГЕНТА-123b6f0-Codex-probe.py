from pathlib import Path
import sys,json,signal
root=Path(sys.argv[1]);sys.path[:0]=[str(root/'runner'),str(root/'tests')]
from test_domain_agent_copies import Copies,Proxy
from unittest.mock import patch
import m11stand
result={}
case=Copies();case.setUp()
try:
 case.directive('@start agent m1');case.directive('@start agent m1 second');case.directive('@clock m1 +10')
 current=[v['process'] for v in case.b.copies('m1')];st=case.b.clusters['m1'];found=st.find('agent#3')
 before=len(case.signals);failure=None
 try:reply=case.run.directive('@on m1 @sigkill agent#3','ok')
 except SystemExit as e:failure=str(e);reply=None
 result['missing_after_clock']=dict(lookup=None if found is None else found.pid,signals=case.signals[before:],failure=failure,reply=reply,both_alive=all(p.poll() is None for p in current))
finally:case.doCleanups()
case=Copies();case.setUp()
try:
 case.directive('@start agent relay');case.directive('@start agent relay second')
 case.directive('@start agent m1 via relay');case.directive('@start agent m1 second')
 members=[v['process'] for v in case.b.copies('m1')];urls=[p.env['RELAY_URL'] for p in members]
 before=(len(case.processes),len(case.signals),Proxy.next_port);failure=None
 try:case.run.directive('@start agent relay second','ok')
 except SystemExit as e:failure=str(e)
 result['late_relay']=dict(failure=failure,processes_added=len(case.processes)-before[0],signals_added=len(case.signals)-before[1],proxies_added=Proxy.next_port-before[2],members_alive=all(p.poll() is None for p in members),urls_unchanged=[v['process'].env['RELAY_URL'] for v in case.b.copies('m1')]==urls,relay_copies=len(case.b.copies('relay')))
finally:case.doCleanups()
print(json.dumps(result))
