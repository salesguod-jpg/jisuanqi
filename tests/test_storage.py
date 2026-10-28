import pytest
from smartpad.storage import save,load,fingerprint,ConflictError

def test_roundtrip_and_conflict(tmp_path):
    p=tmp_path/'note.scn';doc={'version':1,'text':'中文\n100','overrides':{'1':{'include':False}},'settings':{}}
    stamp=save(p,doc);assert load(p)==doc
    assert save(p,doc,stamp)==stamp
    p.write_text('external',encoding='utf8')
    with pytest.raises(ConflictError):save(p,doc,stamp)
    assert p.read_text()=='external'
    recovery=tmp_path/'recovery.scn';save(recovery,doc);assert load(recovery)==doc
    assert not list(tmp_path.glob('.recovery*'))

def test_invalid(tmp_path):
    p=tmp_path/'bad.scn';p.write_text('{"version":1,"text":"x","overrides":{"0":{"include":"yes"}}}')
    with pytest.raises(ValueError):load(p)

@pytest.mark.parametrize('mode',['calculator','standard'])
def test_legacy_percent_mode_is_removed(tmp_path,mode):
    p=tmp_path/'legacy.scn'
    save(p,{'version':1,'text':'500+15%','settings':{'mode':mode}})
    data=load(p)
    assert 'mode' not in data['settings']
