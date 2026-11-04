"""Markdown links of the course: parse, resolve, check targets and anchors (ADR-0124; ADR-0124 addendum (1) item 7).

    python tools/layout/links.py <каталог> [--only <префикс>]

Checks every local link `[text](target)` of every `*.md` under the directory (outside code blocks): the target file or
directory exists, and an anchor `#…` names a heading of the target Markdown file (anchors as GitHub builds them).
Exit code 1 if a link is broken. The migration (`migrate.py`) and the export probe use the same functions.
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

FENCE = re.compile(r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", re.M | re.S)
LINK = re.compile(r"(!?)\[((?:[^\[\]\n]|\n(?![ \t]*\n)|\[[^\[\]\n]*\])*)\]\(([^()\s]+)\)")   # text may wrap a line
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$", re.M)
SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:")


def outside_fences(text):
    """[(start, end)] of the parts of the text outside fenced code blocks."""
    out, at = [], 0
    for m in FENCE.finditer(text):
        out.append((at, m.start()))
        at = m.end()
    out.append((at, len(text)))
    return out


def links(text):
    """Local links of a Markdown text outside code blocks → [(match)] (group 2 — text, group 3 — target)."""
    out = []
    for a, b in outside_fences(text):
        for m in LINK.finditer(text, a, b):
            target = m.group(3)
            if SCHEME.match(target) or target.startswith("//"):
                continue
            out.append(m)
    return out


def heading_text(raw):
    """The text of a heading as rendered: code spans, links, emphasis and HTML stripped to their text."""
    raw = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"(`+)(.+?)\1", r"\2", raw)
    raw = re.sub(r"(\*\*|__|\*)(.+?)\1", r"\2", raw)
    return raw.strip()


def slug(text):
    """GitHub's anchor of a heading text (github-slugger): lower case, letters, digits, marks, `-`, `_` and spaces kept,
    spaces → `-`."""
    keep = []
    for ch in text.lower():
        cat = unicodedata.category(ch)
        if ch in "-_" or cat[0] in "LNM":
            keep.append(ch)
        elif ch == " ":
            keep.append("-")
    return "".join(keep)


def headings(text):
    """[(level, anchor)] of the ATX headings of a text outside code blocks, in order; repeated anchors get -1, -2…"""
    seen, out = {}, []
    for a, b in outside_fences(text):
        for m in HEADING.finditer(text, a, b):
            base = slug(heading_text(m.group(2)))
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.append((len(m.group(1)), base if n == 0 else f"{base}-{n}"))
    return out


def anchors(path, cache={}):  # noqa: B006 — a cache of anchors by file
    path = Path(path)
    if path not in cache:
        try:
            cache[path] = {a for _, a in headings(path.read_text(encoding="utf-8"))}
        except (OSError, UnicodeError):
            cache[path] = set()
    return cache[path]


def resolve(source, target):
    """A link target of the file `source` → (path, anchor or None); the path is normalized, not resolved by symlinks."""
    path, _, anchor = target.partition("#")
    from urllib.parse import unquote
    whole = Path(os.path.normpath(Path(source).parent / unquote(path))) if path else Path(source)
    return whole, (unquote(anchor) if "#" in target else None)


def broken(source, target):
    """Why the link is broken, or None."""
    path, anchor = resolve(source, target)
    if target.startswith("/"):
        return "absolute link"
    if not path.exists():
        return "no target"
    if anchor and path.suffix == ".md" and path.is_file() and anchor not in anchors(path):
        return "no anchor"
    return None


def check_tree(root, only=None):
    """→ [(file, target, why)] of broken links of every *.md under the root (or under root/only)."""
    root = Path(root)
    out, total = [], 0
    for md in sorted((root / only if only else root).rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        for m in links(text):
            total += 1
            why = broken(md, m.group(3))
            if why:
                out.append((md.relative_to(root).as_posix(), m.group(3), why))
    return out, total


def main(argv):
    if not argv:
        sys.exit(__doc__)
    only = None
    if "--only" in argv:
        k = argv.index("--only")
        only, argv = argv[k + 1], argv[:k] + argv[k + 2:]
    bad, total = check_tree(argv[0], only)
    for f, t, why in bad:
        print(f"{f}: {why}: {t}")
    print(f"links {total}, broken {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
