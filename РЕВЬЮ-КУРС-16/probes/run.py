#!/usr/bin/env python3
"""Replay review 16 against git archives. Never copy probes into a checkout."""
import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--course-repo', type=Path, default=HERE.parents[1])
parser.add_argument('--product-repo', type=Path, default=HERE.parents[1].parent / 'vmssubsystem')
parser.add_argument('--before', default='0b9ecc39')
parser.add_argument('--after', default='045d198a')
parser.add_argument('--product', default='2e5e120c')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--go-only', action='store_true', help='nightly: check the product only')
parser.add_argument('--include-product', action='store_true', help='replay the earlier combined review with product access')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
results = {}


def snapshot(repo, ref, directory):
    directory.mkdir()
    archive = directory.parent / (directory.name + '.tar')
    with archive.open('wb') as out:
        subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', ref], stdout=out, check=True, timeout=60)
    with tarfile.open(archive) as tar:
        tar.extractall(directory, filter='data')
    archive.unlink()
    return subprocess.check_output(['git', '-C', str(repo), 'rev-parse', ref], text=True).strip()


def run(cmd, cwd, logfile, timeout):
    with logfile.open('w') as out:
        result = subprocess.run(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
    return result.returncode


def json_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')]


with tempfile.TemporaryDirectory(prefix='review16-snapshots-') as temp:
    root = Path(temp)
    if not args.go_only:
        for name, ref in [('before', args.before), ('after', args.after)]:
            directory = root / name
            sha = snapshot(args.course_repo, ref, directory)
            log = args.output / ('retention-' + name + '.log')
            code = run([sys.executable, str(HERE / 'retention_probe.py'), str(directory / 'Source')], directory, log, 30)
            facts = json_lines(log)
            missing = [row['scenario'] for row in facts if (row['alarms_left'] or row['events_left']) and not row['operator_record_left']]
            concurrent = args.output / ('concurrent-' + name + '.log')
            race_code = run([sys.executable, str(HERE / 'concurrent_unit_probe.py'), str(directory / 'Source')], directory, concurrent, 30)
            race = json_lines(concurrent)
            bad_race = bool(not race or race[0]['error'] or (not race[0]['old_bucket_still_exists'] and not race[0]['journal_records']))
            results[name] = {'sha': sha, 'retention_exit': code, 'lost_operator_records': missing,
                             'concurrent_exit': race_code, 'concurrent_failure': bad_race}
            contract = args.output / ('contract-' + name + '.log')
            contract_code = run([sys.executable, str(HERE / 'contract_probe.py'), str(directory / 'Source')], directory, contract, 30)
            results[name]['contract_exit'] = contract_code
    if args.go_only or args.include_product:
        directory = root / 'product'
        sha = snapshot(args.product_repo, args.product, directory)
        package = directory / 'vmsworker' / 'w2cplatform'
        shutil.copyfile(HERE / 'retention_go_test.go', package / 'review16_probe_test.go')
        code = run(['go', 'test', './w2cplatform', '-run', '^TestReview16', '-count=1', '-timeout=90s', '-v'],
                   directory / 'vmsworker', args.output / 'product.log', 120)
        results['product'] = {'sha': sha, 'exit': code}

failed = any(row.get('retention_exit') or row.get('concurrent_exit') or row.get('contract_exit') or row.get('lost_operator_records')
             or row.get('concurrent_failure') or row.get('exit') for row in results.values())
results['failed'] = failed
(args.output / 'summary.json').write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n')
print(json.dumps(results, indent=2, ensure_ascii=False))
sys.exit(1 if failed else 0)
