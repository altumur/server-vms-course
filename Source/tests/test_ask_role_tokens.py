"""Ephemeral ask credentials belong to a target/trigger pair, never just a target."""
import base64
import json
import threading

from tests.conftest import Clock
from vms.role_tokens import RoleTokens
from vms.recording_books import Unconfirmed
from tests.test_book_names import raises


class Door:
    def __init__(self):
        self.calls=[]
    def request(self,kind,ref,by):
        self.calls.append((kind,ref,by))
        body=base64.urlsafe_b64encode(json.dumps({'iat':100,'ref':ref,'by':by,'n':len(self.calls)}).encode()).decode().rstrip('=')
        return {'request_id':str(len(self.calls)),'token':'test.'+body+'.test','exp':200}


def test_distinct_triggers_do_not_replace_or_share_cached_tokens():
    door,clock=Door(),Clock()
    tokens=RoleTokens('autoworker',door,clock=clock)
    a=tokens.get('ask','target',(1,),by='a')
    b=tokens.get('ask','target',(1,),by='b')
    assert a!=b and len(door.calls)==2
    assert tokens.get('ask','target',(1,),by='a')==a
    tokens.forget('ask','target',by='a')
    assert tokens.get('ask','target',(1,),by='b')==b and len(door.calls)==2
    assert tokens.get('ask','target',(2,),by='a')!=a
    assert tokens.get('ask','target',(1,),by='b')==b


def test_late_reply_cannot_revive_forgotten_pair_or_overwrite_another_pair():
    door=Door()
    real=door.request
    entered,release=threading.Event(),threading.Event()
    def held(kind,ref,by):
        result=real(kind,ref,by)
        if by=='a':
            entered.set();assert release.wait(2)
        return result
    door.request=held
    tokens=RoleTokens('recworker',door,clock=Clock())
    results=[]
    def request():
        results.append(raises(Unconfirmed,lambda:tokens.get('ask','target',(1,),by='a')))
    thread=threading.Thread(target=request);thread.start()
    assert entered.wait(2)
    tokens.forget('ask','target',by='a')
    b=tokens.get('ask','target',(1,),by='b')
    release.set();thread.join(2)
    assert not thread.is_alive() and len(results)==1
    assert ('ask','target','a') not in tokens.cached
    assert tokens.get('ask','target',(1,),by='b')==b
