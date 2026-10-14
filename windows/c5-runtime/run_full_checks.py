"""Run every unit module exactly once in two parts, JS and the other full suites.

No tests or expected values are rewritten. Each child has its own log, exit and
command record; the source manifest is captured before starting the children.
"""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WINDOW = Path(os.environ.get('W2C_CHECK_OUTPUT', '/Users/murat/w2c/course-book-merge-evidence/c5-runtime-integrated'))
WINDOW.mkdir(parents=True, exist_ok=True)
PYTHON = '/Users/murat/w2c/vms-nightly/venv/bin/python'


def main():
    suffix = sys.argv[1] if len(sys.argv) > 1 else 'verified'
    assert suffix.replace('-', '').isalnum()
    checkpoint = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    modules = sorted(p.stem for p in (ROOT/'Source/tests').glob('test_*.py'))
    parts = [['test_keeps'], ['test_configstore', 'test_configstorevars', 'test_console_load']]
    seeded = {name for part in parts for name in part}
    for index, name in enumerate(name for name in modules if name not in seeded):
        parts[index % 2].append(name)
    assert set(parts[0]).isdisjoint(parts[1])
    assert sorted(parts[0] + parts[1]) == modules
    jobs = [(f'unit-{suffix}-part-{i+1}', ['tests/run.py', *sorted(part)]) for i, part in enumerate(parts)]
    jobs += [(f'js-{suffix}', ['tests/run.py', 'console']),
             (f'cluster-{suffix}', ['tests/cluster/run.py']),
             (f'domain-{suffix}', ['tests/domain/run.py']),
             (f'domainvms-{suffix}', ['tests/domainvms/run.py'])]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (ROOT/'Source').rglob('*') if p.is_file()
              and not {'node_modules', '__pycache__'}.intersection(p.parts) and p.suffix != '.pyc'}
    candidate_diff = subprocess.check_output(['git','diff','--binary','HEAD','--','Source'], cwd=ROOT)
    (WINDOW/f'source-{suffix}.json').write_text(json.dumps({'base_checkpoint': checkpoint,
        'candidate_diff_sha256': hashlib.sha256(candidate_diff).hexdigest(),
        'source_files_sha256': hashes}, ensure_ascii=False, indent=2)+'\n')
    plan = {'checkpoint': checkpoint, 'unit_modules': modules, 'unit_parts': [sorted(part) for part in parts],
            'unit_disjoint_complete': True, 'jobs': dict(jobs)}
    (WINDOW/f'checks-{suffix}.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n')
    env = dict(os.environ, OBSD_BIN='/Users/murat/w2c/vms-nightly/exe/obsd', PYTHONUNBUFFERED='1')
    env.pop('W2C_PRODUCT_REF', None)
    def run(job):
        name, arguments = job
        command = [PYTHON, *arguments]
        path = WINDOW/(name+'.log')
        assert not path.exists(), path
        with path.open('w') as output:
            process = subprocess.Popen(command, cwd=ROOT/'Source', env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            (WINDOW/(name+'.run.json')).write_text(json.dumps({'checkpoint':checkpoint, 'command':command, 'pid':process.pid,
                'cwd':str(ROOT/'Source'), 'started':time.time(), 'OBSD_BIN':env['OBSD_BIN'], 'W2C_PRODUCT_REF':None}, indent=2)+'\n')
            result = process.wait()
        (WINDOW/(name+'.exit')).write_text(str(result)+'\n')
        print(name, result, flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, jobs))
    return int(any(results))


if __name__ == '__main__':
    sys.exit(main())
