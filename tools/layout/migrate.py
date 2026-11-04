"""Move a lesson to the layout of ADR-0124 (and its addendum (1)): the English source on the canonical path, the Russian
text as a mirror in `ru/`, forms in `forms/`, logs in `journal/`.

    python tools/layout/migrate.py <урок> --phase ru      # 1st commit: Russian X → ru/X, the lecture → ru/; moves.tsv
    python tools/layout/migrate.py <урок> --phase en      # 2nd commit: en/<имя>.en.md → X; forms/, journal/
    python tools/layout/migrate.py <урок> --phase links   # 3rd commit: links by meaning over the course, heads of pairs
    python tools/layout/migrate.py <урок> --phase plan    # print the table, change nothing

`<урок>` — `Platform/NN-<имя>`, `VMS/NN-<имя>`, `Platform/common` or `VMS/common`. Run from the root of the course. Each
phase stages its own paths only (`git mv`, `git add <путь>`), the commit is the operator's. The table of moves is kept for
good in `tools/layout/moves.tsv`: a reader of an old ADR finds the new place by it.

Links (ADR-0124 addendum (1) item 3), the class of the linking file decides:
- source (English: a file of a moved lesson outside `ru/` and `journal/`, or `en/*.en.md` of a lesson in the former
  layout) — into the source; a link into `ru/` (the lecture) or `journal/` becomes text: a code span of the path from the
  root of the lesson, «(for people, not in the export)»; a Russian anchor of a source target becomes the English one by
  the pairs of headings (one to one);
- translation (Russian under `ru/` of a moved lesson, or a derived Russian text of a lesson in the former layout) — into
  translations (`ru/X`, the Russian anchor stays), into the source for machine files; within the moved lesson a link to
  the lecture or the journal becomes text as in its source;
- history (`decisions/**`: ADR, notes, review archives) — only links to paths that are no more, mechanically by the table;
- any other text (lectures and Russian sources of other lessons, notes, rules) — into the source with the English anchor.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import links as L  # noqa: E402

MOVES = HERE / "moves.tsv"
HEADER = "# lesson\told\tnew\tkind"
OLD_MARK = "производный от en, руками не правится"
FORM = re.compile(r"data/([^/]+-checks(?:\.probes)?\.tsv|[^/]+\.machine\.yaml|[^/]+\.traces\.tsv)")
HISTORY = ("decisions/",)
LIVE_TABLES = ("decisions/adr-norms.tsv", "decisions/adr-pipeline.tsv")
NOTE = {"en": "for people, not in the export", "ru": "для человека, в выгрузку не входит"}
JOURNAL_NOTE = {"en": "a log, not in the export", "ru": "журнал, в выгрузку не входит"}


def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True).stdout


def tracked(prefix=None):
    out = git("ls-files", "-z", *([prefix] if prefix else []))
    return [p for p in out.split("\0") if p]


# ---- the table ---------------------------------------------------------------------------------------------------

def plan(home):
    """The moves of a lesson in the former layout → [(old, new, kind)], paths from the root of the course."""
    files = tracked(home)
    rel = [f[len(home) + 1:] for f in files]
    if any(r.startswith("ru/") for r in rel):
        raise SystemExit(f"{home}: already has ru/ — moved")
    name = Path(home).name
    sources = {}
    for r in rel:
        m = re.fullmatch(r"(?:(.*)/)?en/([^/]+)\.en\.md", r)
        if m:
            sources[(m.group(1) + "/" if m.group(1) else "") + m.group(2) + ".md"] = r
    rows, missing = [], []
    for r in sorted(rel):
        if re.search(r"(?:^|/)en/[^/]+\.en\.md$", r):
            continue
        if r.endswith(".md"):
            if r == f"{name}.md":
                rows.append((r, f"ru/{r}", "lecture"))
            elif r in sources:
                rows.append((r, f"ru/{r}", "translation"))
            else:
                missing.append(r)
        elif FORM.fullmatch(r):
            rows.append((r, "forms/" + r.split("/", 1)[1], "form"))
        elif m := re.fullmatch(r"acceptance/(?:([^/]+)/)?corrections\.tsv", r):
            rows.append((r, f"journal/corrections-{m.group(1)}.tsv" if m.group(1) else "journal/corrections.tsv", "journal"))
    for x, en in sorted(sources.items()):
        if x not in {o for o, _, k in rows if k == "translation"}:
            missing.append(f"{en} (no Russian {x})")
        rows.append((en, x, "source"))
    if missing:
        raise SystemExit(f"{home}: not translated whole — no English source for: " + ", ".join(missing))
    return [(f"{home}/{o}", f"{home}/{n}", k) for o, n, k in rows]


def read_moves():
    rows = []
    if MOVES.is_file():
        for line in MOVES.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                rows.append(tuple(line.split("\t")))
    return rows


def lesson_moves(home):
    return [(o, n, k) for lesson, o, n, k in read_moves() if lesson == home]


def write_moves(home, rows):
    kept = [r for r in read_moves() if r[0] != home]
    lines = [HEADER] + ["\t".join(r) for r in kept] + ["\t".join((home, o, n, k)) for o, n, k in rows]
    head = ("# Таблица переноса уроков в раскладку ADR-0124 (доп. (1) п. 5): старый путь → новый. Постоянная: читатель "
            "старого ADR находит по ней новое место.\n# kind: translation — русский производный X → ru/X; source — "
            "английский en/<имя>.en.md → X; lecture — лекция → ru/; form — формы ADR-0120 → forms/; journal — "
            "corrections.tsv → journal/.\n")
    MOVES.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def git_mv(old, new):
    Path(new).parent.mkdir(parents=True, exist_ok=True)
    git("mv", old, new)


def prune_empty(home):
    for d in sorted(Path(home).rglob("*"), key=lambda p: -len(p.parts)):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


# ---- classes of files and targets --------------------------------------------------------------------------------

def home_of(path):
    parts = Path(path).parts
    return "/".join(parts[:2]) if len(parts) >= 2 and parts[0] in ("Platform", "VMS") else None


def moved_homes():
    return {lesson for lesson, *_ in read_moves()}


def file_class(path, text, homes):
    """source, translation, history or other — of the linking file by its new path."""
    if path.startswith(HISTORY):
        return "history"
    home = home_of(path)
    if home in homes:
        rest = path[len(home) + 1:]
        if rest.startswith("ru/"):
            return "translation"
        return "other" if rest.startswith("journal/") else "source"
    if re.search(r"(?:^|/)en/[^/]+\.en\.md$", path):
        return "source"
    if OLD_MARK in "\n".join(text.splitlines()[:12]):
        return "translation"
    return "other"


def heading_pairs(source, translation):
    """Russian anchor → English anchor by the headings of a pair, one to one; {} if they are not one to one."""
    try:
        en = L.headings(Path(source).read_text(encoding="utf-8"))
        ru = L.headings(Path(translation).read_text(encoding="utf-8"))
    except OSError:
        return {}
    if [lv for lv, _ in en] != [lv for lv, _ in ru]:
        return {}
    return {r: e for (_, r), (_, e) in zip(ru, en)}


class Rewriter:
    def __init__(self, root, homes, moves):
        self.root = Path(root)
        self.homes = homes
        self.new_of = {o: n for o, n, _ in moves}
        self.old_of = {n: o for o, n, _ in moves}
        self.kind = {o: k for o, n, k in moves}
        self.source_of_translation = {}     # old Russian X (= source path now) → its translation ru/X
        for o, n, k in moves:
            if k == "translation":
                self.source_of_translation[o] = n
        self.pairs = {}
        self.stats = {"files": 0, "links": 0, "texted": 0, "anchors": 0, "by_class": {}}
        self.unmapped = []

    def anchor_en(self, x, anchor):
        if anchor is None:
            return None
        if x not in self.pairs:
            self.pairs[x] = heading_pairs(self.root / x, self.root / self.source_of_translation[x])
        if anchor in self.pairs[x]:
            return self.pairs[x][anchor]
        if anchor in L.anchors(self.root / x):
            return anchor
        self.unmapped.append((x, anchor))
        return anchor

    def target(self, cls, new_file, old_target_abs, anchor):
        """→ (new absolute target, anchor, how): how — 'link' or 'text' (a link that becomes text)."""
        a = old_target_abs
        kind = self.kind.get(a)
        if cls == "history":
            return (self.new_of[a] if kind in ("source", "lecture", "form", "journal") else a), anchor, "link"
        if kind == "translation":                       # the former Russian X: now the source X, the translation ru/X
            if cls == "translation":
                return self.new_of[a], anchor, "link"
            new_anchor = self.anchor_en(a, anchor)
            return a, new_anchor, "link"
        if kind == "source":
            return self.new_of[a], anchor, "link"
        if kind in ("lecture", "journal"):
            new = self.new_of[a]
            same_lesson = home_of(new_file) == home_of(new)
            if cls == "source" or (cls == "translation" and same_lesson):
                return new, anchor, "text"
            return new, anchor, "link"
        if kind == "form":
            return self.new_of[a], anchor, "link"
        return a, anchor, "link"

    def rewrite(self, path):
        text = (self.root / path).read_text(encoding="utf-8")
        cls = file_class(path, text, self.homes)
        old_path = self.old_of.get(path, path)
        lang = "en" if cls == "source" else "ru"
        out, at, changed = [], 0, 0
        for m in L.links(text):
            target = m.group(3)
            p, _, a = target.partition("#")
            anchor = a if "#" in target else None
            if not p:
                continue                                # an anchor of the same file
            old_abs = os.path.normpath(os.path.join(os.path.dirname(old_path), p))
            if cls == "history" and old_abs not in self.kind:
                continue
            here = os.path.normpath(os.path.join(os.path.dirname(path), p))
            if old_abs not in self.kind and not (self.root / old_abs).exists() and (self.root / here).exists():
                continue                                # written for the new place (a built block copied from ru)
            new_abs, new_anchor, how = self.target(cls, path, old_abs, anchor)
            if new_abs == old_abs and new_anchor == anchor and path == old_path:
                continue
            if how == "text":
                home = home_of(new_abs)
                name = new_abs[len(home) + 1:] if home_of(path) == home else new_abs
                note = (JOURNAL_NOTE if self.kind.get(old_abs) == "journal" else NOTE)[lang]
                inner = m.group(2)
                if re.fullmatch(r"`[^`]+`", inner):
                    rep = f"`{name}` ({note})"
                else:
                    rep = f"{inner} (`{name}`, {note})"
                self.stats["texted"] += 1
            else:
                rel = os.path.relpath(new_abs, os.path.dirname(path))
                if p.endswith("/") and not rel.endswith("/"):
                    rel += "/"
                if p.startswith("./") and not rel.startswith("."):
                    rel = "./" + rel
                rep = f"{m.group(1)}[{m.group(2)}]({rel}{'#' + new_anchor if new_anchor is not None else ''})"
                if new_anchor != anchor:
                    self.stats["anchors"] += 1
                if rep == m.group(0):
                    continue
            out.append(text[at:m.start()])
            out.append(rep)
            at = m.end()
            changed += 1
        if not changed:
            return 0
        out.append(text[at:])
        (self.root / path).write_text("".join(out), encoding="utf-8")
        self.stats["files"] += 1
        self.stats["links"] += changed
        self.stats["by_class"][cls] = self.stats["by_class"].get(cls, 0) + changed
        return changed


# ---- heads of pairs and text mentions of paths that are no more --------------------------------------------------

EN_HEAD = re.compile(r"the Russian(?: text)?\s+\[`[^`]*`\]\([^)]*\)(\s+is derived from it)")
RU_HEAD = re.compile(r"Текст производный от en, руками не правится: источник( P/[0-9.]+)? — английский \[`[^`]*`\]\([^)]*\)")


def heads(home, moves):
    done = []
    for old, new, kind in moves:
        if kind == "source":                           # old en/…en.md → X: its translation is ru/X
            rel = new[len(home) + 1:]
            src = Path(new)
            text = src.read_text(encoding="utf-8")
            fixed = EN_HEAD.sub(lambda m: f"the Russian translation `ru/{rel}` ({NOTE['en']}){m.group(1)}", text, count=1)
            if fixed != text:
                src.write_text(fixed, encoding="utf-8")
                done.append(new)
            tr = Path(home) / "ru" / rel
            text = tr.read_text(encoding="utf-8")
            link = os.path.relpath(new, tr.parent)
            fixed = RU_HEAD.sub(lambda m: f"Текст производный от `{rel}`, руками не правится: источник{m.group(1) or ''} — "
                                          f"английский [`{rel}`]({link})", text, count=1)
            if fixed != text:
                tr.write_text(fixed, encoding="utf-8")
                done.append(str(tr))
    return done


def mentions(moves):
    """Full paths of files that are no more, in text of live files (not history), by the table → [(file, count)]."""
    gone = {o: n for o, n, k in moves if k in ("source", "lecture", "form", "journal")}
    if not gone:
        return []
    pattern = re.compile("|".join(re.escape(o) for o in sorted(gone, key=len, reverse=True)) + r"(?![\w.-])")
    out = []
    for path in tracked():
        if path.startswith(HISTORY) and path not in LIVE_TABLES or Path(path).resolve() == MOVES:
            continue
        if not path.endswith((".md", ".tsv", ".yaml", ".json", ".txt")):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        fixed, n = pattern.subn(lambda m: gone[m.group(0)], text)
        if n:
            Path(path).write_text(fixed, encoding="utf-8")
            out.append((path, n))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("lesson")
    ap.add_argument("--phase", required=True, choices=["plan", "ru", "en", "links"])
    args = ap.parse_args(argv)
    home = args.lesson.rstrip("/")
    if not Path(home).is_dir() or home_of(home) != home:
        raise SystemExit(f"{home}: not a lesson directory (Platform/NN-<имя>, VMS/NN-<имя>, */common)")
    if args.phase == "plan":
        for row in (lesson_moves(home) or plan(home)):
            print("\t".join(row))
        return 0
    if args.phase == "ru":
        rows = plan(home)
        for old, new, kind in rows:
            if kind in ("translation", "lecture"):
                git_mv(old, new)
        write_moves(home, [(o, n, k) for o, n, k in rows])
        git("add", str(MOVES.relative_to(Path.cwd().resolve())))
        print(f"{home}: {sum(k in ('translation', 'lecture') for _, _, k in rows)} Russian files → ru/; table {MOVES.name}")
        return 0
    rows = lesson_moves(home)
    if not rows:
        raise SystemExit(f"{home}: no rows in {MOVES.name} — run --phase ru first")
    if args.phase == "en":
        n = 0
        for old, new, kind in rows:
            if kind in ("source", "form", "journal"):
                git_mv(old, new)
                n += 1
        prune_empty(home)
        print(f"{home}: {n} files → canonical paths, forms/, journal/")
        return 0
    homes = moved_homes()
    moves = [(o, n, k) for lesson, o, n, k in read_moves()]
    rw = Rewriter(Path.cwd(), homes, moves)
    touched = []
    for path in tracked():
        if path.endswith(".md") and rw.rewrite(path):
            touched.append(path)
    head = heads(home, rows)
    ment = mentions(rows)
    for p in sorted(set(touched) | set(head) | {p for p, _ in ment}):
        git("add", p)
    s = rw.stats
    print(f"links: {s['links']} in {s['files']} files {s['by_class']}; to text {s['texted']}; anchors {s['anchors']}")
    print(f"heads of pairs: {len(head)}; text mentions of gone paths: {sum(n for _, n in ment)} in {len(ment)} files")
    for x, a in sorted(set(rw.unmapped)):
        print(f"UNMAPPED anchor {x}#{a}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
