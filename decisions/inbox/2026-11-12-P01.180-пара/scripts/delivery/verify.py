"""P01.180 (from P02.26): delivered M and J-input equal the sources: every path, mode and blob; fsck --strict; one ref."""
import subprocess, hashlib, os, json
R = '/srv/b11-isolation'; P = '/home/pilot/run-p01180-pair-20261112'
def g(d, *a): return subprocess.check_output(['git', '-c', 'safe.directory=*', '--git-dir', d, *a])
def tree(d, c):
    o = {}
    for e in g(d, 'ls-tree', '-r', '-z', c).split(b'\0'):
        if e: h, p = e.split(b'\t', 1); m, _, b = h.split(); o[p.decode()] = (m.decode(), b.decode())
    return o
res = {}
for n, src, c, dst in (('M', P + '/pair-41a9493fb08c/M.git', 'be48405e645b49985d35efc42b6d61c2f304c4d8', R + '/model-specs/be48405e645b49985d35efc42b6d61c2f304c4d8'),
                       ('JI', P + '/ji-41a9493fb0/JI.git', '9daca227dbc08ce3d4a14c6d47c6ea3f94e55034', R + '/judge-input/9daca227dbc08ce3d4a14c6d47c6ea3f94e55034')):
    s = tree(src, c); d = tree(dst + '/' + os.path.basename(src), c)
    bad = []
    for p, (m, b) in s.items():
        f = os.path.join(dst, 'tree', p); raw = open(f, 'rb').read()
        if hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest() != b or bool(os.stat(f).st_mode & 0o111) != (m == '100755'): bad.append(p)
    extra = [os.path.relpath(os.path.join(a, x), dst + '/tree') for a, _, fs in os.walk(dst + '/tree') for x in fs if os.path.relpath(os.path.join(a, x), dst + '/tree') not in s]
    res[n] = {'files': len(s), 'git_tree_equal': s == d, 'tree_files_equal': len(s) - len(bad), 'bad': bad[:5], 'extra': extra[:5],
              'fsck': subprocess.run(['git', '-c', 'safe.directory=*', '--git-dir', dst + '/' + os.path.basename(src), 'fsck', '--strict'], capture_output=True).returncode == 0,
              'refs': g(dst + '/' + os.path.basename(src), 'for-each-ref', '--format=%(refname)').decode().split()}
print(json.dumps(res, indent=1))
