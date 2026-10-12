#!/usr/bin/env python3
"""A writer creates a genuine event directory between the resource's two inventory reads."""
import argparse,json,os,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('source');a=p.parse_args();sys.path.insert(0,str(Path(a.source).resolve()))
os.environ.setdefault('STORE_VOLATILE','1')
from w2cplatform.events import EventLog
from w2cplatform.variables import FileVariables
from w2cplatform.objects import FsObjectStore
from w2cplatform.resource import Resource
now=1757500000.0
with tempfile.TemporaryDirectory(prefix='review16-inventory-') as temp:
 root=Path(temp); tree=root/'events';vars=FileVariables(str(root/'vars'));objects=FsObjectStore(str(root/'objects'))
 vars.put('other/retention',{'days':'1'})
 old=Path(EventLog(str(tree),'other','7',1).append(now-5*86400,'observation','observation'))
 class ConcurrentWriter(Resource):
  calls=0
  def units(self):
   out=super().units(); self.calls+=1
   if self.calls==1:
    EventLog(str(tree),'other','8',1).append(now,'observation','observation')
   return out
 r=ConcurrentWriter(str(tree),'srv-a','http://srv-a',vars,objects,wall=lambda:now)
 error=None
 try:r.retain()
 except Exception as exc:error=type(exc).__name__+': '+str(exc)
 audit=list(tree.rglob('*.events.jsonl'))
 journal_rows=[]
 for path in audit:
  if '/audit/' in str(path):journal_rows += [json.loads(line) for line in path.read_text().splitlines()]
 print(json.dumps({'error':error,'old_bucket_still_exists':old.exists(),'journal_records':journal_rows,'remaining_units':r.units()},sort_keys=True))
