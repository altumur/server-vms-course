"""Direct foreign entry points and the real clean-before-export lifecycle."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(sys.argv[1])/'runner'))
import diagnostic_secrets as ds
import prepare
out=Path(os.environ['CHECK_OUT']);result={}
for field in ('scenarios','cases','variants','probes'):
    secret='own-direct-'+field+'-credential-042'
    body={field:{'token':secret}}
    learned={}
    for entry in ('learn_received','body'):
        secrets=ds.Secrets()
        if entry=='learn_received':secrets.learn_received(dict(got=body))
        else:secrets.body(body)
        learned[entry]=secret in secrets.values
    with tempfile.TemporaryDirectory(prefix='rv-clean-export-') as directory:
        root=Path(directory);path=root/'result.json';log=root/'native.log'
        secrets=ds.Secrets();secrets.register_log(log)
        log.write_text('native exact echo '+secret+'\n')
        raw=dict(scenarios={'safe-case':[dict(step='4',line=6,ok=True,why=[],got=body)]})
        # This ordering is used by vms_engine and by m11stand/tls_stage exporters.
        prepare.write(path,secrets.clean(raw))
        before=secret in secrets.values
        secrets.finalize([root]);secrets.finalize([root])
        result[field]=dict(safety_pass=all(learned.values()) and before and secret not in log.read_text(),
                           learned_at_entry=learned,learned_before_write=before,
                           learned_after_finalize=secret in secrets.values,log=log.read_text(),
                           raw_body_exported=secret in path.read_text())
(out/'extra-controls.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v['safety_pass'] for k,v in result.items()}))
