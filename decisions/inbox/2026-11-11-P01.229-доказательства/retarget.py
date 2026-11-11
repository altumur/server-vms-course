"""Retarget links to moved anchors of the common acceptance README (amap.json: 'Platform/…/README.md#a' -> 'Platform/…#a').
usage: retarget.py AMAP FILE... ; prints the count of replacements per file; writes in place."""
import sys, json, os, re
amap = json.load(open(sys.argv[1], encoding='utf-8'))
link = re.compile(r'(\]\()([^)\s#]*README\.md)(#[^)\s]+)(\))|(`)([^`\s#]*README\.md)(#[^`\s]+)(`)|(")([^"\s#]*README\.md)(#[^"\s]+)(")')
for f in sys.argv[2:]:
    try: t = open(f, encoding="utf-8").read()
    except (UnicodeError, OSError): continue
    n = 0; d = os.path.dirname(f)
    def sub(m):
        global n
        g = [x for x in m.groups() if x is not None]
        pre, path, frag, post = g
        for base in (os.path.normpath(os.path.join(d, path)), os.path.normpath(path)):
            key = base + frag
            if key in amap:
                new, nfrag = amap[key].split('#', 1)
                newp = os.path.relpath(new, d) if not path.startswith('Platform/') else new
                n += 1
                return f"{pre}{newp}#{nfrag}{post}"
        return m.group(0)
    t2 = link.sub(sub, t)
    if n: open(f, 'w', encoding='utf-8').write(t2)
    print(n, f)
