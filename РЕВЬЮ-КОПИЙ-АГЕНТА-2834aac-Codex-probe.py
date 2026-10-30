from pathlib import Path
import sys,os,json,hashlib,unittest
r=Path.cwd();out=Path(os.environ['CHECK_OUT'])
m=r/'MANIFEST.json';assert hashlib.sha256(m.read_bytes()).hexdigest()=='88c269f3175ee2d1b36fd0a365359a0a0cfde7b5fa42ba20f1ec602d671e0235'
files=json.loads(m.read_text());bad=[n for n,h in files.items() if hashlib.sha256((r/n).read_bytes()).hexdigest()!=h];assert not bad,bad
base=r/'check-input'
os.environ['CAMMETA_SPECS']=str(base/'specs');os.environ['VMS_JSDOM_TEST_SPECS']=str(base/'vms-jsdom-specs')
sys.path[:0]=[str(base/'runner/runner'),str(base/'runner/tests')]
res=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(['test_domain_agent_copies','test_agent_tokens','test_process_exits']))
from test_domain_agent_copies import Copies
case=Copies()
case.setUp()
try:
 case.directive('@start agent m1')
 case.directive('@start agent m1 second')
 case.directive('@clock m1 +10')
 copies=case.b.copies('m1');found=case.b.clusters['m1'].find('agent#3')
 before=len(case.signals);ret=case.run.directive('@on m1 @sigkill agent#3','ok')
 probe=dict(configured_numbers=[v['number'] for v in copies],current_pids=[v['process'].pid for v in copies],lookup_pid=None if found is None else found.pid,signals=case.signals[before:],directive_result=ret)
finally:case.doCleanups()
audit=dict(manifest_files=len(files),manifest_ok=not bad,author_tests=res.testsRun,author_green=res.wasSuccessful(),invalid_copy_after_restart=probe,SUT=0)
(out/'review-audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit),flush=True)
assert res.wasSuccessful()
assert probe['lookup_pid'] is None,'RED: nonexistent agent#3 resolves to an existing restarted copy'
