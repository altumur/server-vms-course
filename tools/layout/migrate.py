"""Move a lesson to the layout of ADR-0124 (and its addendum (1)): the English source on the canonical path, the Russian
text as a mirror in `ru/`, forms in `forms/`, logs in `journal/`.

    python tools/layout/migrate.py <урок> --phase plan     # print the table, change nothing
    python tools/layout/migrate.py <урок> --phase ru       # 1st commit: Russian X → ru/X, the lecture → ru/; moves.tsv
    python tools/layout/migrate.py <урок> --phase en       # 2nd commit: en/<имя>.en.md → X; forms/, journal/
    python tools/layout/migrate.py <урок> --phase links    # 3rd commit: links over the course, heads of pairs (once)
    python tools/layout/migrate.py --phase relink          # any time: links into moved lessons by meaning (idempotent)

`<урок>` — `Platform/NN-<имя>`, `VMS/NN-<имя>`, `Platform/common` or `VMS/common`; or a shallow home: `.` — the root of
the course (`НОРМАТИВНЫЕ-СЛОВА.md`, `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md`; ADR-0124 доп. (1) п. 4), `Platform` or `VMS` — the
README of a module. A shallow home holds its own files only (not its subdirectories but `en/` and `ru/`); only its pairs
`en/X.en.md` ↔ `X` move, its other Russian files (notes of the course) stay and are not sources. Run from the root of
the course. Each
phase stages its own paths only (`git mv`, `git add <путь>`), the commit is the operator's. The table of moves is kept for
good in `tools/layout/moves.tsv`: a reader of an old ADR finds the new place by it. Machine Markdown (`harness/**` — the
bytes of a product prompt, ADR-0124 доп. (1) п. 4) is not moved, not translated and not rewritten.

`links` = the table step and the meaning step; it runs once per lesson right after `en` (moves.tsv keeps the mark
`linked`): the table step resolves the links of a moved file from its former place. `relink` is the meaning step alone,
over every moved lesson; run it after merging texts written by the former habit. `--keep <префикс>` (repeated) leaves
the files under the prefix as they are — a parallel branch moves them (`VMS/common`); what the phase would change there
is printed «KEPT», and `relink` after the merge does it. Every problem — a syntax the rewriter
cannot read (`links.missed`), a Russian anchor without its English pair, a link that must become text but is a
definition — is found before anything is written, and the phase exits 1.

The meaning step (ADR-0124 addendum (1) item 3), by the class of the linking file:
- source (English: a file of a moved lesson outside `ru/` and `journal/`, or `en/*.en.md` of a lesson in the former
  layout) — into the source `Y` with the English anchor; a link into `ru/` without a source (the lecture) or into
  `journal/` becomes text: a code span of the path from the root of the lesson, «(for people, not in the export)»;
- translation (Russian under `ru/` of a moved lesson, or a derived Russian text of a lesson in the former layout) — into
  translations `ru/Y` (the Russian anchor), into the source for machine files and for its own source; a link to a
  lecture or a journal becomes text wherever its source has text (the pair stays one to one);
- lecture (`ru/NN-<имя>.md`: Russian, for people, without a pair) — into translations; links stay links;
- history (`decisions/**`, root `РЕВЬЮ-*.md`, `ХОД-*.md`, `windows/**`) — only links to paths that are no more, by the
  table, and (addendum (2)) links to a canonical path with a Russian anchor: they meant the Russian text, now in the
  mirror — into `ru/…` with the same Russian anchor; a link without an anchor or with an anchor of the source stays;
- any other text (lectures and Russian sources of other lessons, notes, rules) — as a source, but links stay links.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import links as L  # noqa: E402

MOVES = HERE / "moves.tsv"
HEADER = "# lesson\told\tnew\tkind"
OLD_MARK = "производный от en, руками не правится"
FORM = re.compile(r"data/([^/]+-checks(?:\.probes)?\.tsv|[^/]+\.machine\.yaml|[^/]+\.traces\.tsv)")
MACHINE_MD = re.compile(r"(?:^|/)harness/")
HISTORY = L.HISTORY
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
    rel = [inside(home, f) for f in own(home)]
    if any(r.startswith("ru/") for r in rel):
        raise SystemExit(f"{home}: already has ru/ — moved")
    name = Path(home).name
    shallow = home in SHALLOW
    sources = {}
    for r in rel:
        m = re.fullmatch(r"(?:(.*)/)?en/([^/]+)\.en\.md", r)
        if m:
            sources[(m.group(1) + "/" if m.group(1) else "") + m.group(2) + ".md"] = r
    rows, missing = [], []
    for r in sorted(rel):
        if re.search(r"(?:^|/)en/[^/]+\.en\.md$", r) or MACHINE_MD.search(r):
            continue
        if shallow:                                    # only the pairs move; the notes of the course stay
            if r in sources:
                rows.append((r, f"ru/{r}", "translation"))
        elif r.endswith(".md"):
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
    return [(under(home, o), under(home, n), k) for o, n, k in rows]


def read_moves():
    rows = []
    if MOVES.is_file():
        for line in MOVES.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                rows.append(tuple(line.split("\t")))
    return rows


def lesson_moves(home):
    return [(o, n, k) for lesson, o, n, k in read_moves() if lesson == home and k != "linked"]


def write_moves(rows):
    lines = [HEADER] + ["\t".join(r) for r in rows]
    head = ("# Таблица переноса уроков в раскладку ADR-0124 (доп. (1) п. 5): старый путь → новый. Постоянная: читатель "
            "старого ADR находит по ней новое место.\n# kind: translation — русский производный X → ru/X; source — "
            "английский en/<имя>.en.md → X; lecture — лекция → ru/; form — формы ADR-0120 → forms/; journal — "
            "corrections.tsv → journal/; linked — фаза ссылок урока сделана (пути «-»).\n")
    MOVES.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def git_mv(old, new):
    Path(new).parent.mkdir(parents=True, exist_ok=True)
    git("mv", old, new)


def prune_empty(home):
    for d in sorted(Path(home).rglob("*"), key=lambda p: -len(p.parts)):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


# ---- classes of files ---------------------------------------------------------------------------------------------

MODULES = L.MODULES
SHALLOW = (".", *MODULES)                               # homes of their own files only: the root, a module directory
home_of = L.home_of


def under(home, rest):
    """A path of a home → from the root of the course."""
    return rest if home == "." else f"{home}/{rest}"


def inside(home, path):
    """A path from the root of the course → from its home."""
    return path if home == "." else path[len(home) + 1:]


def own(home):
    """The tracked files of a home (a shallow home: its own files, `en/` and `ru/`)."""
    if home in SHALLOW:
        return [p for p in tracked(None if home == "." else home) if home_of(p) == home]
    return tracked(home)


def moved_homes():
    return {lesson for lesson, *_ in read_moves()}


def file_class(path, text, homes, sources=frozenset()):
    """source, translation, history, machine or other — of the linking file by its path now. `sources` — the sources of
    the moved shallow homes (the root, a module): there only they are sources, the notes beside them are «other»."""
    if HISTORY.search(path):
        return "history"
    if MACHINE_MD.search(path):
        return "machine"
    home = home_of(path)
    if home in homes and home in SHALLOW:
        if inside(home, path).startswith("ru/"):
            return "translation"
        return "source" if path in sources else "other"
    if home in homes:
        rest = inside(home, path)
        if rest == f"ru/{Path(home).name}.md":
            return "lecture"                             # Russian for people, no pair: links into ru/ stay links
        if rest.startswith("ru/"):
            return "translation"
        return "other" if rest.startswith("journal/") else "source"
    if re.search(r"(?:^|/)en/[^/]+\.en\.md$", path):
        return "source"
    if OLD_MARK in "\n".join(text.splitlines()[:12]):
        return "translation"
    return "other"


def heading_map(a, b):
    """Anchors of `a` → anchors of `b` by the headings in order, one to one; None if the levels differ."""
    try:
        ha, hb = L.headings(Path(a).read_text(encoding="utf-8")), L.headings(Path(b).read_text(encoding="utf-8"))
    except OSError:
        return None
    if [lv for lv, _ in ha] != [lv for lv, _ in hb]:
        return None
    return {x: y for (_, x), (_, y) in zip(ha, hb)}


class Rewriter:
    """`moves` — of the lesson being moved (the table step); `homes` — every moved lesson (the meaning step)."""

    def __init__(self, root, homes, moves=(), keep=()):
        self.root = Path(root)
        self.homes = homes
        self.keep = tuple(keep)
        self.sources = {n for lesson, o, n, k in read_moves() if k == "source" and lesson in SHALLOW}
        self.new_of = {o: n for o, n, _ in moves}
        self.old_of = {n: o for o, n, _ in moves}
        self.kind = {o: k for o, n, k in moves}
        self.gone = {o: n for lesson, o, n, k in read_moves() if k in ("source", "lecture", "form", "journal")}
        self.maps = {}
        self.stats = {"files": 0, "links": 0, "texted": 0, "anchors": 0, "by_class": {}}
        self.problems, self.warnings = [], []

    def exists(self, rel):
        return (self.root / rel).exists()

    def anchor(self, frm, to, anchor, where):
        """An anchor of `frm` → the anchor of its pair `to` (both paths from the root)."""
        if anchor is None or anchor == "":
            return anchor
        if anchor in L.anchors(self.root / to):
            return anchor
        if (frm, to) not in self.maps:
            self.maps[(frm, to)] = heading_map(self.root / frm, self.root / to)
        mapping = self.maps[(frm, to)]
        if anchor in L.anchors(self.root / frm):
            if mapping and anchor in mapping:
                return mapping[anchor]
            self.problems.append(f"{where}: anchor #{anchor} of {frm} has no pair in {to} (headings not one to one)")
            return anchor
        self.warnings.append(f"{where}: anchor #{anchor} is in neither {frm} nor {to} (broken before)")
        return anchor

    def table_step(self, path, old_path, p):
        """The target of a link as written for the former place of the file → its target by the table (from root)."""
        old_abs = os.path.normpath(os.path.join(os.path.dirname(old_path), p))
        if self.kind.get(old_abs) in ("source", "lecture", "form", "journal"):
            return self.new_of[old_abs]
        here = os.path.normpath(os.path.join(os.path.dirname(path), p))
        if old_path != path and old_abs not in self.kind and not self.exists(old_abs) and self.exists(here):
            return here                                  # written for the new place (a built block copied from ru)
        return old_abs

    def meaning_step(self, cls, path, target, anchor, where):
        """→ (target, anchor, how): how — 'link' or 'text'."""
        if target in self.gone:                         # a path that is no more
            target = self.gone[target]
        if cls == "history":                            # addendum (2): a Russian anchor meant the Russian text
            return L.history_ru(self.root, target, anchor) or target, anchor, "link"
        home = home_of(target)
        if home not in self.homes:
            return target, anchor, "link"
        rest = inside(home, target)
        mirror = cls in ("source", "translation")       # a translation mirrors its source: text where the source has text
        if rest.startswith("ru/"):
            source = under(home, rest[3:])
            if self.exists(source) and target.endswith(".md"):
                if cls in ("translation", "lecture"):
                    return target, self.anchor(source, target, anchor, where), "link"
                return source, self.anchor(target, source, anchor, where), "link"
            return target, anchor, ("text" if mirror else "link")    # the lecture: for people only
        if rest.startswith("journal/"):
            return target, anchor, ("text" if mirror else "link")
        translation = under(home, f"ru/{rest}")
        if target.endswith(".md") and self.exists(translation):
            mine = path == translation                    # a translation names its own source
            if cls in ("translation", "lecture") and not mine:
                return translation, self.anchor(target, translation, anchor, where), "link"
            return target, self.anchor(translation, target, anchor, where), "link"
        return target, anchor, "link"

    def rewrite(self, path, table=True):
        """→ the new text of a file or None (unchanged); problems are collected, nothing is written."""
        text = (self.root / path).read_text(encoding="utf-8")
        cls = file_class(path, text, self.homes, self.sources)
        if cls == "machine":
            return None
        for href in L.missed(text):
            self.problems.append(f"{path}: a link the rewriter cannot read: {href}")
        old_path = self.old_of.get(path, path) if table else path
        lang = "en" if cls == "source" else "ru"         # (lecture: Russian, links stay)
        out, at, changed = [], 0, 0
        for t in L.targets(text):
            p, _, a = t.dest.partition("#")
            anchor = a if "#" in t.dest else None
            if not p:
                continue                                # an anchor of the same file
            where = f"{path}: {t.dest}"
            p = unquote(p)
            target = self.table_step(path, old_path, p) if table else os.path.normpath(os.path.join(os.path.dirname(path), p))
            if cls == "history" and target == os.path.normpath(os.path.join(os.path.dirname(path), p)) \
                    and target not in self.gone and not L.history_ru(self.root, target, anchor):
                continue
            target, new_anchor, how = self.meaning_step(cls, path, target, anchor, where)
            if how == "text":
                if t.whole is None:
                    self.problems.append(f"{where}: a link definition must become text — edit by hand")
                    continue
                home = home_of(target)
                name = inside(home, target) if home_of(path) == home else target
                note = (JOURNAL_NOTE if "/journal/" in target else NOTE)[lang]
                inner = t.text
                rep = f"`{name}` ({note})" if re.fullmatch(r"`[^`]+`", inner) else f"{inner} (`{name}`, {note})"
                start, end = t.whole
                self.stats["texted"] += 1
            else:
                rel = os.path.relpath(target, os.path.dirname(path))
                if p.endswith("/") and not rel.endswith("/"):
                    rel += "/"
                if p.startswith("./") and not rel.startswith("."):
                    rel = "./" + rel
                if unquote(t.dest.split("#")[0]) == rel and new_anchor == anchor:
                    continue
                if new_anchor != anchor:
                    self.stats["anchors"] += 1
                rep = rel.replace(" ", "%20") + ("#" + new_anchor if new_anchor is not None else "")
                start, end = t.start, t.end
            out += [text[at:start], rep]
            at = end
            changed += 1
        if not changed:
            return None
        out.append(text[at:])
        self.stats["files"] += 1
        self.stats["links"] += changed
        self.stats["by_class"][cls] = self.stats["by_class"].get(cls, 0) + changed
        return "".join(out)


def kept(path, keep):
    return any(path == k or path.startswith(k.rstrip("/") + "/") for k in keep)


def rewrite_course(rw, table):
    """Plan every rewrite, stop before writing if anything is wrong; → the changed paths."""
    plans = {}
    for path in tracked():
        if path.endswith(".md"):
            new = rw.rewrite(path, table=table)
            if new is not None:
                plans[path] = new
    for path in [p for p in plans if kept(p, rw.keep)]:
        print("KEPT", path, "(a parallel branch moves it: relink after the merge)")
        del plans[path]
    for w in sorted(set(rw.warnings)):
        print("WARNING", w)
    if rw.problems:
        for p in sorted(set(rw.problems)):
            print("PROBLEM", p)
        raise SystemExit(f"{len(set(rw.problems))} problems: nothing written")
    for path, text in plans.items():
        Path(path).write_text(text, encoding="utf-8")
    return sorted(plans)


# ---- heads of pairs and text mentions of paths that are no more --------------------------------------------------

EN_HEAD = re.compile(r"the Russian(?: text)?\s+\[`[^`]*`\]\([^)]*\)(\s+is derived from it)")
RU_HEAD = re.compile(r"Текст производный от en, руками не правится: источник( P/[0-9.]+| V/[0-9.]+)? — английский \[`[^`]*`\]\([^)]*\)")


def heads(home, moves):
    done = []
    for old, new, kind in moves:
        if kind == "source":                           # old en/…en.md → X: its translation is ru/X
            rel = inside(home, new)
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


def mentions(moves, keep=()):
    """Full paths of files that are no more, in text of live files (not history), by the table → [(file, count)]."""
    gone = {o: n for o, n, k in moves if k in ("source", "lecture", "form", "journal")}
    if not gone:
        return []
    pattern = re.compile("|".join(re.escape(o) for o in sorted(gone, key=len, reverse=True)) + r"(?![\w.-])")
    out = []
    for path in tracked():
        if (HISTORY.search(path) and path not in LIVE_TABLES) or Path(path).resolve() == MOVES or MACHINE_MD.search(path):
            continue
        if not path.endswith((".md", ".tsv", ".yaml", ".json", ".txt")):
            continue
        if kept(path, keep):
            if pattern.search(Path(path).read_text(encoding="utf-8", errors="replace")):
                print("KEPT", path, "(text mentions of gone paths: relink after the merge does not fix them — by hand)")
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


def report(rw):
    s = rw.stats
    print(f"links: {s['links']} in {s['files']} files {s['by_class']}; to text {s['texted']}; anchors {s['anchors']}")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("lesson", nargs="?")
    ap.add_argument("--phase", required=True, choices=["plan", "ru", "en", "links", "relink"])
    ap.add_argument("--keep", action="append", default=[], help="leave files under this prefix as they are")
    args = ap.parse_args(argv)
    if args.phase == "relink":
        rw = Rewriter(Path.cwd(), moved_homes(), keep=args.keep)
        touched = rewrite_course(rw, table=False)
        for p in touched:
            git("add", p)
        report(rw)
        return 0
    home = (args.lesson or "").rstrip("/") or "."
    if not Path(home).is_dir() or home_of(f"{home}/x") != home:
        raise SystemExit(f"{home}: not a lesson directory (Platform/NN-<имя>, VMS/NN-<имя>, */common) nor a shallow home "
                         "(., Platform, VMS)")
    if args.phase == "plan":
        for row in (lesson_moves(home) or plan(home)):
            print("\t".join(row))
        return 0
    if args.phase == "ru":
        rows = plan(home)
        for old, new, kind in rows:
            if kind in ("translation", "lecture"):
                git_mv(old, new)
        write_moves([r for r in read_moves() if r[0] != home] + [(home, o, n, k) for o, n, k in rows])
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
        if home in SHALLOW:                            # its en/ only: the rest of a shallow home is not moved
            en = Path(under(home, "en"))
            if en.is_dir():
                prune_empty(en)
                if not any(en.iterdir()):
                    en.rmdir()
        else:
            prune_empty(home)
        print(f"{home}: {n} files → canonical paths, forms/, journal/")
        return 0
    if any(r[0] == home and r[3] == "linked" for r in read_moves()):
        raise SystemExit(f"{home}: links already done — use --phase relink")
    rw = Rewriter(Path.cwd(), moved_homes(), rows, keep=args.keep)
    touched = rewrite_course(rw, table=True)
    head = heads(home, rows)
    ment = mentions(rows, keep=args.keep)
    rw2 = Rewriter(Path.cwd(), moved_homes(), keep=args.keep)         # the meaning step once more: idempotent, after heads
    touched2 = rewrite_course(rw2, table=False)
    write_moves(read_moves() + [(home, "-", "-", "linked")])
    for p in sorted(set(touched) | set(touched2) | set(head) | {p for p, _ in ment}) + ["tools/layout/moves.tsv"]:
        git("add", p)
    report(rw)
    print(f"heads of pairs: {len(head)}; text mentions of gone paths: {sum(n for _, n in ment)} in {len(ment)} files; "
          f"after heads: {rw2.stats['links']} links")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
