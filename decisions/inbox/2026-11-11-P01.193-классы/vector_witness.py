#!/usr/bin/env python3
"""Reconstruct 19 native byte witnesses from saved J rows and static code findings.

No candidate, judge, tests, probes, build, or generated implementation is executed.
The only subprocess is git show of the pinned J table bytes. Candidate algorithms
are not reimplemented: each witness states the concrete output inferred by reading
that candidate's relevant branch, then checks saved length and SHA-256.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

J_GIT = '/home/pilot/run-p0226-pair-20261111/ji-4694190a17/JI.git'
J_PIN = '49e622795ca96b2e73904f1da5d203f2d103b2d5'
REPORTS = Path('/home/pilot/owner-receipts/P01.192-court-engine2-20261111/out-diag/attempt6')


def table_lines(package):
    raw = subprocess.check_output([
        'git', f'--git-dir={J_GIT}', 'show',
        f'{J_PIN}:Platform/common/vectors/{package}/cases.tsv',
    ], text=True)
    # splitlines() would also split the literal U+000B fixture and corrupt the
    # physical TSV line numbers. The table's physical line separator is LF.
    return raw.split('\n')


def go_json(value):
    # encoding/json.Marshal framing for these concrete JSON values. All values
    # here are valid Unicode; the two invalid UTF-8 cases use literal bytes below.
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            .replace('&', '\\u0026').replace('<', '\\u003c')
            .replace('>', '\\u003e').encode())


def witnesses():
    evidence = []
    for package in ('crl', 'revoked', 'log-mask'):
        lines = table_lines(package)
        report = REPORTS / f'P_01_vectors-{package}' / 'engine.json'
        for row in json.loads(report.read_text())['rows']:
            if row['result'] != 'red':
                continue
            cells = lines[row['line'] - 1].split('\t')
            if package == 'crl':
                value = json.loads(cells[2])
                # Candidate revoked.go:54 initializes CANext as an empty slice.
                value['ca_next'] = []
                native = go_json(value)
                reason = 'CRL-ca_next-null'
            elif package == 'revoked':
                # revoked.go:24 strips CR; vectors/main.go:255 parses @absent
                # as JSON first and returns native exit 2 with empty stdout.
                native = go_json(['ab', 'cd']) if row['line'] == 16 else b''
                reason = ('CR-accepted' if row['line'] == 16
                          else 'bare-absent-json-parse')
            else:
                expected = cells[1]
                native_by_line = {
                    # No nested src handling: original raw remains unchanged.
                    20: go_json(cells[0]),
                    # The port scan eats the backslash preceding closing quote.
                    26: go_json('a \\"rtsp://cam:***" b'),
                    # Login param entries are incorrectly treated as secrets.
                    29: go_json(expected.replace('user=admin', 'user=***')),
                    31: go_json('Authorization: Digest username=***, response="5ccc"'),
                    # Decoded delimiter is recognized but the encoded name stays.
                    43: go_json('?%26p%2577d=***'),
                    # ASCII-only header regexp eats NBSP and x.
                    53: go_json('Authorization: Bearer ***'),
                    # Byte-wise IsSpace splits UTF-8 NBSP; Go Marshal substitutes
                    # the remaining invalid byte by the literal JSON escape.
                    54: b'"?pwd=***\\ufffdchannel=1"',
                    56: b'"rtsp://h/x?pwd=***\\ufffdb"',
                    # U+3000 is not recognized by the byte-wise scanner.
                    57: go_json('rtsp://h/x?pwd=***'),
                }
                reason_by_line = {
                    20: 'nested-src', 26: 'address-end',
                    29: 'login-as-secret', 31: 'login-as-secret',
                    43: 'decoded-pair-name', 53: 'unicode-whitespace',
                    54: 'unicode-whitespace', 56: 'unicode-whitespace',
                    57: 'unicode-whitespace',
                }
                native = native_by_line[row['line']]
                reason = reason_by_line[row['line']]
            digest = hashlib.sha256(native).hexdigest()
            assert digest == row['body']['sha256'], (package, row['line'], 'sha256')
            assert len(native) == row['body']['length'], (package, row['line'], 'length')
            evidence.append({
                'package': package, 'line': row['line'], 'case': row['case'],
                'reason': reason, 'class': 'candidate',
                'inferred_native_utf8': native.decode(),
                'length': len(native), 'sha256': digest,
                'matches_saved_body': True,
            })
    assert len(evidence) == 19, len(evidence)
    return {
        'method': 'Static code reasoning and independent construction of native byte witnesses; no candidate or engine execution',
        'rows': evidence,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path,
                        default=Path(__file__).with_name('vector-witnesses.json'))
    args = parser.parse_args()
    args.out.write_text(json.dumps(witnesses(), ensure_ascii=False, indent=2) + '\n')
    print(f'19/19 inferred native byte witnesses match saved length and SHA256: {args.out}')
