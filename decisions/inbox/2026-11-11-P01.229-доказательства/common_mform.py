"""Scratch check (not committed): m_form history_phrases (via M_FORM_COMMON) and judge_only_refs over the
model_and_judge files under the given prefixes of Platform/common (and moved lesson files given as extra prefixes).
usage: common_mform.py SKILL_SCRIPTS ROOT PREFIX..."""
import sys, collections
sys.path.insert(0, sys.argv[1])
from pathlib import Path
import m_form
root = Path(sys.argv[2]).resolve(); prefixes = sys.argv[3:]
class C:
    def __init__(s): s.root=root; s.errors=[]; s.stats=collections.Counter()
    def error(s,p,m): s.errors.append((str(p).replace(str(root)+'/',''),m))
c=C(); model=m_form.export_model(c)
m_form.M_FORM_COMMON = tuple(p for p in prefixes if p.startswith('Platform/common/'))
m_form.common_history(c, model)
# history_phrases for lesson prefixes (moved text) without ADR_LATER
for p in prefixes:
    if p.startswith('Platform/common/'): continue
    home = root / '/'.join(p.split('/')[:2])
    for path, d in sorted(model.items()):
        if d=='model_and_judge' and path.startswith(p) and path.endswith('.md'):
            src = root/path; m_form.scan_history(c, src)
            tr = home/'ru'/src.relative_to(home)
            if tr.is_file(): m_form.scan_history(c, tr)
# judge_only_refs: one pseudo-lesson per home
homes = sorted({'/'.join(p.split('/')[:2]) for p in prefixes})
for h in homes:
    L = m_form.Lesson(c, 'P/00', root/h)
    files = [f for f in L.m_files(model) if any(f.relative_to(root).as_posix().startswith(p) for p in prefixes)]
    m_form.judge_only_refs(c, L, files, model)
by = collections.Counter((p, m.split(':')[0] if m.startswith('line') else m[:40]) for p,m in c.errors)
kinds = collections.Counter('ADR' if 'ADR number' in m else 'phrase' if 'history in M' in m else 'judge-only' if 'judge-only' in m else 'other' for p,m in c.errors)
for p,m in c.errors: print(p, m[:200])
print('SUMMARY', dict(kinds), 'judge_only_refs seen', c.stats['judge_only_refs'])
