import json
import os
import tempfile
from pathlib import Path

class ConflictError(OSError): pass

def fingerprint(path):
    import hashlib
    path=Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

def save(path, document, expected=False):
    path=Path(path)
    if expected is not False and fingerprint(path)!=expected:
        raise ConflictError('文件已被其他程序修改，请另存为以保留两个版本')
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(document,stream,ensure_ascii=False,indent=2)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    return fingerprint(path)

def load(path):
    path=Path(path)
    if path.stat().st_size>20_000_000: raise ValueError('文件过大，最多支持 20 MB')
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('text'),str): raise ValueError('无效的记事本文档')
    if not isinstance(data.get('overrides',{}),dict) or not isinstance(data.get('settings',{}),dict): raise ValueError('文档设置格式错误')
    for key,value in data.get('overrides',{}).items():
        if not isinstance(key,str) or not key.isdigit() or not isinstance(value,dict): raise ValueError('行规则格式错误')
        if value.get('role','auto') not in ('auto','amount','number','percent','ignore'): raise ValueError('行规则类型错误')
        if not isinstance(value.get('expression',''),str) or not isinstance(value.get('include',True),bool): raise ValueError('行规则值错误')
    settings=data.get('settings',{})
    # 兼容旧文档：移除历史百分比模式，恢复后统一使用标准数学规则。
    settings.pop('mode',None)
    for key in ('thousands','autosave','dark','results','enter_result'):
        if key in settings and not isinstance(settings[key],bool): raise ValueError('设置值无效')
    if not isinstance(settings.get('font',''),str) or not isinstance(settings.get('size',12),int) or not 8<=settings.get('size',12)<=36: raise ValueError('字体设置无效')
    if data.get('path') is not None and not isinstance(data['path'],str): raise ValueError('恢复路径无效')
    return data
