"""Readers bind a signed shared document to its current pointer and location."""
import hashlib
import json
from types import SimpleNamespace

from tests.conftest import Box
from w2cplatform.domain.shared import SharedSettings, SharedView, OBJECT, POINTER
from w2cplatform.trust.documents import sign
from w2cplatform.trust.memberkey import MemberKey
from w2cplatform.trust.tokens import TokenIssuer


def site():
    box = Box()
    issuer = TokenIssuer('shared-test')
    issuer.book_seal = MemberKey.new().seal_pub
    box.vars.put('domain/keys', issuer.keyset().to_items())
    box.vars.put('domain/member', {'cluster':'reader'})
    box.vars.put('domain/holder', {'doc':json.dumps({'holder':'holder','term':1})})
    doc = sign({'term':1,'rev':2,'settings':{'shared':{}}},issuer)
    raw = json.dumps(doc).encode()
    pointer = {'term':1,'rev':2,'sha256':hashlib.sha256(raw).hexdigest()}
    box.vars.put(POINTER,pointer)
    box.objects.put(OBJECT,raw)
    view = SharedView(box.vars,box.objects,box.wall)
    return SimpleNamespace(**locals())


def test_member_reads_only_the_generation_bound_to_its_pointer():
    e=site()
    assert e.view.document()==e.doc
    for changes in ({'rev':3},{'term':2},{'sha256':'wrong'}):
        e.box.vars.put(POINTER,{**e.pointer,**changes})
        assert e.view.document() is None


def test_absent_or_malformed_pointer_and_holder_cannot_reuse_a_signed_copy():
    for key,value in ((POINTER,{}),(POINTER,{'rev':'wrong'}),
                      ('domain/holder',{'doc':'wrong'})):
        e=site();e.box.vars.put(key,value)
        assert e.view.document() is None


def test_holder_reads_published_object_and_never_its_leftover_carried_copy():
    e=site()
    e.box.vars.put('domain/holder',{'doc':json.dumps({'holder':'reader','term':2})})
    assert e.view.document() is None  # signed old copy is not the holder's object
    e.box.vars.put(POINTER,{**e.pointer,'object':'shared/rev-2'})
    assert e.view.document() is None
    e.box.objects.put('shared/rev-2',e.raw)
    assert e.view.document()==e.doc
    e.box.objects.delete('shared/rev-2')
    assert e.view.document() is None


def test_shared_settings_published_by_holder_are_read_without_an_agent_copy():
    e=site()
    e.box.vars.put('domain/holder',{'doc':json.dumps({'holder':'reader','term':1})})
    e.box.vars.put(POINTER,{})
    publisher=SharedSettings(e.box.vars,e.box.objects,e.issuer,wall=e.box.wall)
    publisher.edit(lambda settings:None,base_rev=0)
    assert e.view.document()['rev']==1


def test_unsigned_replaced_or_invalid_order_document_is_never_settings():
    for change in ({'sig':'wrong'},{'rev':True},{'term':0}):
        e=site()
        doc={**e.doc,**change}
        if 'sig' not in change:
            doc.pop('sig',None)
            doc=sign(doc,e.issuer)
        raw=json.dumps(doc).encode()
        e.box.objects.put(OBJECT,raw)
        e.box.vars.put(POINTER,{**e.pointer,'sha256':hashlib.sha256(raw).hexdigest()})
        assert e.view.document() is None and e.view.settings()=={}
