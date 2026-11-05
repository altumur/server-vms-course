"""Markdown links of the course: find, resolve, judge targets and anchors (ADR-0124; ADR-0124 addendum (1) item 7).

    python tools/layout/links.py <каталог> [--only <префикс>] [--base <файл прежнего итога>]

Two readers on purpose:
- `targets()` — the rewriter's reader: the destinations of inline links `[text](dest "title")`, `[text](<dest>)` and of
  link definitions `[label]: dest "title"`, with their positions, outside code blocks and code spans;
- `judged()` — the judge's reader, independent: markdown-it (CommonMark) tokens, reference links resolved.
`missed()` names a local destination the judge sees and the rewriter does not: a syntax the migration cannot rewrite —
the migration stops on it. The check of a tree judges every local link of every `*.md`: the target exists, an anchor
`#…` names a heading of the target Markdown file (anchors as GitHub builds them). A link of history (`decisions/**`,
root `РЕВЬЮ-*.md`, `ХОД-*.md`, `windows/**`) to a canonical path with a Russian anchor — a heading of the mirror `ru/…`,
not of the English source — is broken «history: Russian anchor, into ru/…» (ADR-0124 addendum (2)). With `--base` it prints only broken
links that are not in the former result (a file of «file<TAB>target<TAB>why» lines, as `--tsv` prints). Exit 1 if any.
"""
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[ \t]*$", re.M | re.S)
SPAN = re.compile(r"(?<!`)(`+)(?!`)((?:(?!\n[ \t]*\n).)+?)(?<!`)\1(?!`)", re.S)   # within a paragraph
TEXT = r"((?:[^\[\]\n]|\n(?![ \t]*\n)|\[[^\[\]\n]*\])*)"            # link text; it may wrap a line
DEST = r"(<[^<>\n]*>|[^()\s<>]+)"
TITLE = r"""(?:[ \t\n]+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?"""
INLINE = re.compile(r"(!?)\[" + TEXT + r"\]\([ \t]*" + DEST + TITLE + r"[ \t]*\)")
DEFINITION = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*" + DEST + TITLE + r"[ \t]*$", re.M)
SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")
HISTORY = re.compile(r"^(?:decisions/|windows/|РЕВЬЮ-[^/]*\.md$|ХОД-[^/]*\.md$)")
MODULES = ("Platform", "VMS")


def home_of(path):
    """The home of a file: a lesson (or `common`) `Platform/<x>`, `VMS/<x>`; a module `Platform`, `VMS` for the files of
    the module directory itself and of its `en/`, `ru/`; the root `.` for the files of the root and of its `en/`, `ru/`;
    otherwise None."""
    parts = Path(os.path.normpath(path)).parts
    if not parts or parts == (".",):
        return None
    if parts[0] in MODULES:
        if len(parts) >= 3 and parts[1] not in ("en", "ru"):
            return "/".join(parts[:2])
        return parts[0] if len(parts) >= 2 else None
    return "." if len(parts) == 1 or parts[0] in ("en", "ru") else None


def mirror(path):
    """The Russian mirror `<home>/ru/<rest>` of a canonical path (from the root of the course), or None for a path that
    is already under `ru/` or has no home."""
    home = home_of(path)
    if home is None:
        return None
    rest = path if home == "." else path[len(home) + 1:]
    if rest.startswith(("ru/", "en/")):
        return None
    return f"ru/{rest}" if home == "." else f"{home}/ru/{rest}"


def history_ru(root, target, anchor):
    """ADR-0124 addendum (2): a link of history to the canonical path `target` (from the root) with a Russian anchor
    meant the Russian text, now in the mirror → the mirror path, or None (no anchor, an anchor of the source, no
    mirror, or the mirror has no such heading either)."""
    if not anchor or not target.endswith(".md"):
        return None
    ru = mirror(target)
    root = Path(root)
    if ru is None or not (root / target).is_file() or not (root / ru).is_file():
        return None
    if anchor in anchors(root / target) or anchor not in anchors(root / ru):
        return None
    return ru


class Target:
    """A destination in a text: `start`, `end` — of the destination only (without `<>`); `whole` — the inline link
    (start, end) or None for a definition; `text` — the link text of an inline link."""

    def __init__(self, m, kind):
        g = 3 if kind == "inline" else 2
        raw, self.kind = m.group(g), kind
        angle = raw.startswith("<")
        self.start, self.end = m.start(g) + angle, m.end(g) - angle
        self.dest = raw[1:-1] if angle else raw
        self.whole = (m.start(), m.end()) if kind == "inline" else None
        self.text = m.group(2) if kind == "inline" else None
        self.image = kind == "inline" and m.group(1) == "!"

    @property
    def local(self):
        return bool(self.dest) and not SCHEME.match(self.dest) and not self.dest.startswith("//")


def code_ranges(text):
    """[(start, end)] of fenced blocks and of code spans outside them."""
    out = [(m.start(), m.end()) for m in FENCE.finditer(text)]
    at = 0
    for a, b in sorted(out) + [(len(text), len(text))]:
        out += [(at + m.start(), at + m.end()) for m in SPAN.finditer(text[at:a])]
        at = b
    return sorted(out)


def targets(text):
    """Every local destination of a text outside code, in order."""
    code = code_ranges(text)

    def in_code(pos):
        return any(a <= pos < b for a, b in code)

    out = []
    for m in INLINE.finditer(text):
        if not in_code(m.start()):
            out.append(Target(m, "inline"))
    for m in DEFINITION.finditer(text):
        if not in_code(m.start()):
            out.append(Target(m, "definition"))
    return sorted((t for t in out if t.local), key=lambda t: t.start)


def judged(text):
    """Local hrefs of a text by markdown-it (CommonMark), reference links resolved; raw HTML is not a link here."""
    from markdown_it import MarkdownIt
    hrefs = []

    def walk(tokens):
        for tok in tokens:
            if tok.type == "link_open":
                hrefs.append(tok.attrGet("href"))
            elif tok.type == "image":
                hrefs.append(tok.attrGet("src"))
            if tok.children:
                walk(tok.children)

    walk(MarkdownIt("commonmark").parse(text))
    return [unquote(h) for h in hrefs if h and not SCHEME.match(h) and not h.startswith("//")]


def missed(text):
    """Local destinations the judge sees and `targets()` does not."""
    mine = {unquote(t.dest) for t in targets(text)}
    return sorted({h for h in judged(text) if h not in mine})


def heading_text(raw):
    raw = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"(`+)(.+?)\1", r"\2", raw)
    raw = re.sub(r"(\*\*|__|\*)(.+?)\1", r"\2", raw)
    return raw.strip()


def slug(text):
    """GitHub's anchor of a heading text (github-slugger): lower case; letters, digits, marks, `-`, `_` kept; spaces →
    `-`."""
    return "".join("-" if ch == " " else ch for ch in text.lower()
                   if ch in "-_ " or unicodedata.category(ch)[0] in "LNM")


def headings(text):
    """[(level, anchor)] of the headings of a text by markdown-it, in order; a repeated anchor gets -1, -2…"""
    from markdown_it import MarkdownIt
    seen, out, level = {}, [], None
    for tok in MarkdownIt("commonmark").parse(text):
        if tok.type == "heading_open":
            level = int(tok.tag[1:])
        elif tok.type == "inline" and level is not None:
            words = "".join(c.content for c in (tok.children or []) if c.type in ("text", "code_inline"))
            base = slug(words.strip())
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.append((level, base if n == 0 else f"{base}-{n}"))
            level = None
    return out


_ANCHORS = {}


def anchors(path):
    path = Path(path)
    if path not in _ANCHORS:
        try:
            _ANCHORS[path] = {a for _, a in headings(path.read_text(encoding="utf-8"))}
        except (OSError, UnicodeError):
            _ANCHORS[path] = set()
    return _ANCHORS[path]


def forget():
    _ANCHORS.clear()


def broken(source, href, root=None):
    """Why a local href of the file `source` is broken, or None. With `root` (the root of the course) a link of history
    is judged by ADR-0124 addendum (2) too."""
    path, _, anchor = href.partition("#")
    if href.startswith("/"):
        return "absolute link"
    whole = Path(os.path.normpath(Path(source).parent / path)) if path else Path(source)
    if not whole.exists():
        return "no target"
    if root is not None and path and anchor:
        rel = Path(source).relative_to(root).as_posix()
        if HISTORY.search(rel):
            target = os.path.relpath(os.path.normpath(Path(source).parent / path), root)
            ru = history_ru(root, Path(target).as_posix(), anchor)
            if ru:
                return f"history: Russian anchor, into {ru}"
    if "#" in href and anchor and whole.suffix == ".md" and whole.is_file() and anchor not in anchors(whole):
        return "no anchor"
    return None


def check_tree(root, only=None):
    """→ ([(file, href, why)] broken, total) over every *.md under the root (or root/only), by the judge's reader."""
    root = Path(root)
    out, total = [], 0
    for md in sorted((root / only if only else root).rglob("*.md")):
        for href in judged(md.read_text(encoding="utf-8")):
            total += 1
            why = broken(md, href, root)
            if why:
                out.append((md.relative_to(root).as_posix(), href, why))
    return out, total


def main(argv):
    if not argv:
        sys.exit(__doc__)
    opts = {}
    for flag in ("--only", "--base"):
        if flag in argv:
            k = argv.index(flag)
            opts[flag], argv = argv[k + 1], argv[:k] + argv[k + 2:]
    tsv = "--tsv" in argv
    argv = [a for a in argv if a != "--tsv"]
    bad, total = check_tree(argv[0], opts.get("--only"))
    if "--base" in opts:
        base = set(Path(opts["--base"]).read_text(encoding="utf-8").splitlines())
        bad = [b for b in bad if "\t".join(b) not in base]
    for f, t, why in bad:
        print(f"{f}\t{t}\t{why}" if tsv else f"{f}: {why}: {t}")
    if not tsv:
        print(f"links {total}, broken {len(bad)}" + (" (not in the base)" if "--base" in opts else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
