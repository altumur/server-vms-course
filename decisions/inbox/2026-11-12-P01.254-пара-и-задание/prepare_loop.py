"""Isolated preparation snapshot of accepted 248/253/260/261/263 and ADR-0133(78).
Usage: python3 -I prepare_loop.py <new evidence dir> <loop bare repository>
Only root Python modules and rules are materialized; no deployment or probe.
"""
from pathlib import Path
import hashlib, json, re, subprocess, sys
out, source = map(Path, sys.argv[1:3]); out.mkdir(); repo = out/'combined.git'
heads = {'P01.263':'62a45a4396dc54bd0eb54fcbeabe6f6460113fdd',
         'P01.260_ADR78':'1d39c4447c43f003d7dbab1944b5fc4920e14a38',
         'en_generic_with_P01.253':'7e6c535ccca13090dd572729433eee1ebb506f4f'}
def git(*args, data=None, check=True):
    return subprocess.run(['git','--git-dir',str(repo),*args],input=data,capture_output=True,check=check)
subprocess.run(['git','init','--bare',str(repo)],capture_output=True,check=True)
git('fetch','--no-tags',str(source),*heads.values())
first=git('merge-tree','--write-tree',heads['P01.263'],heads['P01.260_ADR78'])
(out/'merge263-260.out').write_bytes(first.stdout); first_tree=first.stdout.decode().splitlines()[0]
commit=git('-c','user.name=P01.254 preparation','-c','user.email=prep@invalid','commit-tree',first_tree,
           '-p',heads['P01.263'],'-p',heads['P01.260_ADR78'],data=b'P01.254 isolated preparation snapshot\n').stdout.decode().strip()
last=git('merge-tree','--write-tree',commit,heads['en_generic_with_P01.253'],check=False)
(out/'merge-with-253.out').write_bytes(last.stdout); (out/'merge-with-253.err').write_bytes(last.stderr)
assert last.returncode==1
lines=last.stdout.decode().splitlines(); tree=lines[0]
conflicts={s.split('\t',1)[1] for s in lines if '\t' in s}
assert conflicts=={'profile_probe.py','tests/test_profile_probe.py'}
raw=git('show',tree+':profile_probe.py').stdout.decode()
rx=re.compile(r'^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n',re.M|re.S)
blocks=list(rx.finditer(raw)); assert len(blocks)==9
# Keep ADR(78)'s single exact-byte start and P253's prose/form/env readers.
choices=[1,2,2,2,1,2,1,1,1]; parts=[]; end=0
for m,side in zip(blocks,choices): parts.extend([raw[end:m.start()],m[side]]); end=m.end()
profile=''.join(parts)+raw[end:]
def once(a,b):
    global profile
    assert profile.count(a)==1,a
    profile=profile.replace(a,b)
once('(the store socket in its run directory)','(a socket of the process in its run directory)')
once('before the first start of a store','before the first start of a process')
once('a production default such as\n        # /run/configstore','a production default under\n        # /run/<name>')
once('"""{name: {"value": object, "file": rel, "place": label}}','"""{name: {"value": object, "text": exact code span, "file": rel, "place": label}}')
once('names a JSON file the README gives as an exact example','names a JSON file the prose of M gives as an exact example')
once('("key", "name", "ok", "judged", "why", "start")','("key", "name", "ok", "judged", "why", "start", "env_given", "env_left", "env_runner")')
once('            env = req.get("stand_env") or {}\n','            env, rn = req.get("stand_env") or {}, req.get("stand_env_runner") or []\n')
once('j["text"], w, base, dirs, s.get("values"), env)','j["text"], w, base, dirs, s.get("values"), env, rn)')
once('"start": {k: x[k] for k in ("alive", "exit", "sockets")}}','"start": {k: x[k] for k in ("alive", "exit", "sockets")},\n                 "env_given": x["env_given"], "env_left": x["env_left"], "env_runner": x["env_runner"]}')
once('s.get("sources") or {}, dirs))','s.get("sources") or {}, dirs, env, req.get("stand_env_file"), x["env_left"], x["env_runner"]))')
assert '<<<<<<<' not in profile
compile(profile,'profile_probe.py','exec')
blob=git('hash-object','-w','--stdin',data=profile.encode()).stdout.decode().strip()
(out/'profile-resolution.diff').write_bytes(git('diff','--no-ext-diff',heads['en_generic_with_P01.253']+':profile_probe.py',blob).stdout)
modules=out/'modules'; modules.mkdir(); hashes={}
for entry in git('ls-tree','-rz',tree).stdout.split(b'\0'):
    if not entry: continue
    _,name=entry.split(b'\t',1); p=name.decode()
    if not (('/' not in p and p.endswith('.py')) or p.startswith('rules/')): continue
    body=profile.encode() if p=='profile_probe.py' else git('show',tree+':'+p).stdout
    dest=modules/p; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(body)
    hashes[p]=hashlib.sha256(body).hexdigest()
    if p.endswith('.py'): compile(body,p,'exec')
manifest={'heads':heads,'first_merge_tree':first_tree,'automatic_merge_tree_with_conflicts':tree,
          'resolved_profile_blob':blob,'profile_block_choices':choices,'conflicts':sorted(conflicts),
          'modules_sha256':hashes,'scope':'root Python modules and rules only; conflicted test file not materialized; preparation only, no deployment','OK':True}
(out/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'OK':True,'first_merge_tree':first_tree,'profile_blob':blob,'files':len(hashes)},indent=1))
