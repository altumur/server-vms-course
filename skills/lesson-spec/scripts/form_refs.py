"""ADR-0133 addendum (102): the references in the cells of the forms of the Platform lessons and of common — a path to a
file, a line of it, an anchor of it, a section of norms, an item of a readiness checklist — exist. A dangling reference
is an error, without a debt list (the owner, 2026-11-13: «add the check of the references to check_spec»).

The forms: `Platform/<lesson>/forms/**/*.tsv` and `Platform/common/**/forms/**/*.tsv`. The cells are read whole, by the
grammars below, never by guessing at prose:

- a Markdown link `[text](target)` — the target from the directory of the form, as Markdown resolves it;
- a path with a course prefix: `Platform/…`, `VMS/…` from the course root; `../…` from the directory of the form;
  `common/…` from `Platform/`; `forms/…`, `acceptance/…`, `spec/…`, `vectors/…`, `data/…`, `qualification/…`,
  `probes/…`, `lifecycle.md` from the home of the form (the directory that holds its `forms/`); in a column `norm` or
  `norms` (elements separated by «;», the stage contract) also a bare relative path element `x.md`, `dir/x.md` from that
  home or from `Platform/`; outside those columns a path of a prefix other than `Platform/`, `VMS/`, `../` names a file
  with a suffix (`common/crl` of a vector key is no file), and a path right after `:`, `$`, `/` is a part of another
  token (`vectors:common/sealing`, `$data/…`, `/etc/w2c/data/…`);
- after a path: `:N` or `:N–M` (also `N-M`) — lines of the file, at most its length; `#fragment` — a heading anchor of
  Markdown (GitHub slugs, `Check.anchors`), a JSON Pointer `#/…` of JSON or YAML, `#header`/`#row:<key>` of a TSV form
  (`m_form._tsv_problem`);
- `P/NN[.K] N<x>[.<y>…]` — a section heading `N<x>… …` of the norms of that chapter, or a paragraph that opens with it
  in bold (`**N1.2a The view.**`); of any chapter of a lesson with chapters when the reference names none;
  `P/NN[.K] «Title»` — a heading or a bold paragraph title of those norms (`**Races.**`), the number `N<x>` before it and
  a closing parenthesis after it aside (`### Data families (built from the standard files)`);
- `P/NN[.K]-MM` — an item of the readiness checklist or of the system checklist of that chapter (`outline`, as
  `Check.stage_norms` reads them); the column `norms` of the lesson's own `stages.tsv` is judged by `stage_norms`.

A file of the model export M (`model_and_judge` in the assembled filters, export_lists) names only files of M: a
reference from it to a file outside M dangles in M (the case of P01.309 M1: `stages.tsv` → `forms/group.tsv`, judge-only),
unless the cell says so — «judge-only:» in the same cell, as `m_form.judge_only_refs` asks of prose.

Not judged here: the gates of `stages.tsv`/`stages.kit.tsv` (`accept:`, `seams:`, `vectors:`, `verdicts:`, `puts:` —
`check_forms.gate_errors` against the scenario, seam and case tables and the vector packages), requirement ids
`P/NN.K-RNNN` (`m_form.req_refs`), tokens with placeholders (`<…>`, `*`, `{…}`, `…`), and names of files of the platform
(`configstore-rights.json`), which are no references to the course."""

import json
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

FORM_GLOBS = ("Platform/*/forms/**/*.tsv", "Platform/common/**/forms/**/*.tsv")
JUDGE_MARKS = ("judge-only:", "только для судьи:")
REF_COLUMNS = {"norm", "norms"}                         # elements «;»: sections, forms, packages (the stage contract)
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
PREFIXED = re.compile(
    r"(?<![\w$/.@~:-])"
    r"((?:Platform|VMS|common|forms|acceptance|spec|vectors|data|qualification|probes)/[\w.@/-]*[\w/]"
    r"|(?:\.\./)+[\w.@-][\w.@/-]*[\w/]|lifecycle\.md)"
    r"(?::([0-9]+)(?:[–-]([0-9]+))?(?![\w:]))?"
    r"(#[^\s;,`\"')\]]*[^\s;,`\"')\].:])?")
EXPLICIT = ("Platform/", "VMS/", "../")              # a path by itself; another prefix outside norm/norms needs a suffix
SUFFIX = re.compile(r"\.[A-Za-z0-9]+$")
ELEMENT = re.compile(r"((?:[\w.@-]+/)*[\w@-][\w.@-]*\.(?:md|tsv|json|yaml|yml))"
                     r"(?::([0-9]+)(?:[–-]([0-9]+))?)?(#\S+)?")
NUMBER = r"N[0-9](?:\.[0-9]+[a-z]?)*"
SECTION = re.compile(r"(?<![\w/])P/([0-9]{2})(?:\.([0-9]+))? (?:(" + NUMBER + r")(?!\w|\.[0-9])|«([^»\n]+)»)")
ITEM = re.compile(r"(?<![\w/])P/([0-9]{2})(?:\.([0-9]+))?-([0-9]{2})(?![\w-])")
PLACEHOLDER = re.compile(r"[<>*{}…]")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
RUN_IN = re.compile(r"^\*\*([^*\n]+?)\.?\*\*")         # a paragraph that opens with its bold title: **N1.2a The view.**
SECTION_HEAD = re.compile(r"(" + NUMBER + r")(?:\s+(.*))?$")
CHECKLISTS = ("Readiness checklist", "System checklist")


def forms(root):
    """The forms of the Platform lessons and of common, sources only (no ru/ translation)."""
    root = Path(root)
    found = {p for pattern in FORM_GLOBS for p in root.glob(pattern) if p.is_file() and not p.is_symlink()}
    return sorted(p for p in found if "ru" not in p.relative_to(root).parts)


def form_home(path):
    """The directory that holds the `forms/` of a form (a lesson root, `Platform/common/acceptance`)."""
    for parent in path.parents:
        if parent.name == "forms":
            return parent.parent
    return path.parent


def read_rows(path):
    """(column names, [(line, cells)]) of a TSV form: the header is the first line that is not a comment, or the last
    comment line before the data that has as many TAB fields (the scenario tables)."""
    lines = path.read_bytes().decode("utf-8").split("\n")
    head = next((i for i, line in enumerate(lines) if line and not line.startswith("#")), len(lines))
    if head == len(lines):
        return [], []
    names, first = lines[head].split("\t"), head + 1
    above = [i for i in range(head) if lines[i].startswith("#")]
    if above and "\t" in lines[above[-1]]:
        cells = lines[above[-1]].lstrip("#").strip(" ").split("\t")
        if len(cells) == len(names):
            names, first = [c.strip() for c in cells], head
    return names, [(n, line.split("\t")) for n, line in enumerate(lines[first:], first + 1)
                   if line and not line.startswith("#")]


class Index:
    """The targets of the references, read once per run: lessons, norms files, their sections, titles and checklist
    items, the files of M."""

    def __init__(self, check):
        self.check = check
        self.root = check.root
        self.lesson_dirs = {row["lesson"]: self.root / "Platform" / row["dir"]
                            for _, row in check.lessons_table()[1] if row.get("lesson") and row.get("dir")}
        self._norms, self._outline, self._lines, self._parsed = {}, {}, {}, {}
        self._model = None

    def norms(self, number, chapter):
        """[norms files] of `P/NN[.K]`; None — no such lesson."""
        key = (number, chapter)
        if key not in self._norms:
            home = self.lesson_dirs.get(number)
            if home is None:
                self._norms[key] = None
            else:
                spec = home / "spec"
                if chapter is not None:
                    files = [p for p in spec.glob(f"{number}.{chapter}-*.norms.md")
                             if re.fullmatch(rf"{number}\.{chapter}-[^.]+\.norms\.md", p.name)]
                else:
                    files = [p for p in spec.glob(f"{number}-*.norms.md")
                             if re.fullmatch(rf"{number}-[^.]+\.norms\.md", p.name)] or \
                            [p for p in spec.glob(f"{number}.*-*.norms.md")
                             if re.fullmatch(rf"{number}\.[0-9]+-[^.]+\.norms\.md", p.name)]
                self._norms[key] = sorted(files)
        return self._norms[key]

    def outline(self, path):
        """(section numbers, heading titles, checklist items) of a norms file."""
        if path not in self._outline:
            from check_spec import outline
            import m_form
            text = path.read_text(encoding="utf-8")
            numbers, titles = set(), set()
            for _, line, fence in m_form.fenced_lines(text):
                m = None if fence else (HEADING.match(line) or RUN_IN.match(line.strip()))
                if not m:
                    continue
                for title in {m[1].strip().rstrip("."), re.sub(r"\s*\([^()]*\)$", "", m[1].strip().rstrip("."))}:
                    s = SECTION_HEAD.match(title)
                    if s:
                        numbers.add(s[1])
                        title = (s[2] or "").strip().rstrip(".")
                    if title:
                        titles.add(title)
                        titles.add(re.sub(r"\s*\([^()]*\)$", "", title))
            self._outline[path] = (numbers, titles, set(outline(text, None, CHECKLISTS)[1]) - {""})
        return self._outline[path]

    def line_count(self, path):
        if path not in self._lines:
            data = path.read_bytes()
            self._lines[path] = data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
        return self._lines[path]

    def model(self):
        """{repository path: disposition} of the assembled export filters; {} — no filters to assemble."""
        if self._model is None:
            import m_form
            self._model = m_form.export_model(self.check)    # export_lists reports the faults of the filters
        return self._model

    def in_model(self, rel, is_dir):
        model = self.model()
        if is_dir:
            return any(p.startswith(rel + "/") and d == "model_and_judge" for p, d in model.items())
        return model.get(rel) == "model_and_judge"

    def fragment_problem(self, target, fragment):
        """None, or why `#fragment` of an existing file does not resolve."""
        import m_form
        if target.suffix == ".tsv":
            return m_form._tsv_problem(target, fragment, self._parsed)
        if fragment.startswith("/"):
            if target.suffix not in (".json", ".yaml", ".yml"):
                return "a JSON Pointer #/… addresses JSON or YAML"
            if target not in self._parsed:
                try:
                    text = target.read_text(encoding="utf-8")
                    self._parsed[target] = json.loads(text) if target.suffix == ".json" else yaml.safe_load(text)
                except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
                    return f"unreadable: {exc}"
            return None if m_form._pointer(self._parsed[target], fragment) else f"no JSON Pointer #{fragment}"
        if target.suffix != ".md":
            return f"#{fragment} addresses no heading of a {target.suffix or 'directory'}"
        return None if unquote(fragment) in self.check.anchors(target) else f"no heading anchor #{fragment}"


def resolve(index, form, token, link):
    """(the existing target, its repository path) or (None, [tried repository paths])."""
    root, home = index.root, form_home(form)
    first = token.split("/", 1)[0]
    if link or first == "..":
        bases = [form.parent]
    elif first in ("Platform", "VMS"):
        bases = [root]
    elif first == "common":
        bases = [root / "Platform"]
    elif first in ("forms", "acceptance", "spec", "vectors", "data", "qualification", "probes") or \
            token == "lifecycle.md":
        bases = [home]
    else:                                               # a bare element of a column norm/norms
        bases = [home, root / "Platform"]
    tried = []
    for base in bases:
        target = Path(posixpath.normpath((base / token).as_posix()))
        try:
            rel = target.relative_to(root).as_posix()
        except ValueError:
            continue
        tried.append(rel)
        if target.exists():
            return target, rel
    return None, tried


def cell_refs(cell, column):
    """[(kind, at, token, line from, line to, fragment)] of the references of one cell; kind: link, path, section,
    item."""
    out, taken = [], []

    def free(start, end):
        return not any(s < end and start < e for s, e in taken)

    for m in LINK.finditer(cell):
        target = m[1]
        if re.match(r"[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            continue                                    # a URL or an anchor of the cell itself
        parts = urlsplit(target)
        path = unquote(parts.path)
        if path and not PLACEHOLDER.search(path):
            out.append(("link", m.start(1), path, None, None, parts.fragment or None))
        taken.append((m.start(), m.end()))
    for m in PREFIXED.finditer(cell):
        if not free(m.start(), m.end()) or PLACEHOLDER.search(m[0]) or \
                PLACEHOLDER.search(cell[m.end():m.end() + 1] or ""):
            continue
        if column not in REF_COLUMNS and not m[1].startswith(EXPLICIT) and not SUFFIX.search(m[1].rsplit("/", 1)[-1]):
            continue                                    # `common/crl` of a vector key, not a file of the course
        out.append(("path", m.start(), m[1], m[2], m[3], m[4][1:] if m[4] else None))
        taken.append((m.start(), m.end()))
    if column in REF_COLUMNS:
        offset = 0
        for element in cell.split(";"):
            start = offset + len(element) - len(element.lstrip())
            offset += len(element) + 1
            m = ELEMENT.fullmatch(element.strip())
            if m and free(start, start + len(element.strip())) and not PLACEHOLDER.search(m[0]):
                out.append(("path", start, m[1], m[2], m[3], m[4][1:] if m[4] else None))
                taken.append((start, start + len(m[0])))
    for m in SECTION.finditer(cell):
        out.append(("section", m.start(), m[0], m[1], m[2], m[3] or m[4]))
    for m in ITEM.finditer(cell):
        out.append(("item", m.start(), m[0], m[1], m[2], m[3]))
    return sorted(out, key=lambda r: r[1])


def run(check):
    """Judge every reference of every form; errors through `check.error`, counts in `check.stats`."""
    index = Index(check)
    root = check.root
    for form in forms(root):
        rel_form = form.relative_to(root).as_posix()
        in_m = index.in_model(rel_form, False)
        own = re.match(r"([0-9]{2})-", form_home(form).name) if form_home(form).parent == root / "Platform" else None
        try:
            names, rows = read_rows(form)
        except (OSError, UnicodeError) as exc:
            check.error(form, f"form references: unreadable: {exc}")
            continue
        for n, cells in rows:
            for i, cell in enumerate(cells):
                column = names[i] if i < len(names) else f"#{i + 1}"
                marked = any(mark in cell for mark in JUDGE_MARKS)
                for kind, _, token, a, b, extra in cell_refs(cell, column):
                    where = f"line {n}, column {column}: «{token}»"
                    if kind == "item" and own and own[1] == a and form.name == "stages.tsv" and column == "norms":
                        continue                        # Check.stage_norms judges the items of the lesson's own stages
                    check.stats["form_refs"] += 1
                    problem = None
                    if kind in ("link", "path"):
                        problem = path_problem(index, form, token, kind == "link", a, b, extra, in_m and not marked)
                    elif kind == "section":
                        problem = section_problem(index, a, b, extra)
                    else:
                        problem = item_problem(index, a, b, token)
                    if problem:
                        check.stats["form_refs_dangling"] += 1
                        check.error(form, f"{where}: dangling reference: {problem}")


def path_problem(index, form, token, link, first, last, fragment, from_m):
    target, rel = resolve(index, form, token, link)
    if target is None:
        return f"no file {' or '.join(rel) if rel else token} (" + (
            "a Markdown link resolves from the directory of the form" if link else
            "Platform/…, VMS/… from the course root, common/… from Platform/, ../… from the form's directory, "
            "other paths from the home of the form") + ")"
    if first is not None:
        if target.is_dir():
            return f"lines of a directory {rel}"
        count = index.line_count(target)
        lo, hi = int(first), int(last) if last is not None else int(first)
        if lo < 1 or hi < lo:
            return f"lines {first}" + (f"–{last}" if last is not None else "") + \
                f" of {rel}: an empty range or one before line 1"
        if hi > count:
            return f"line {hi} is beyond the end of {rel} ({count} lines)"
    if fragment:
        problem = index.fragment_problem(target, fragment)
        if problem:
            return f"{rel}: {problem}"
    if from_m and "/ru/" not in f"/{rel}/" and index.model() and not index.in_model(rel, target.is_dir()):
        return (f"{rel} is not in M (judge-only in the export filters), and the form is a file of M: the reference "
                "dangles in M — name a file of M, remove the reference, or say «judge-only: …» in the same cell")
    return None


def section_problem(index, number, chapter, name):
    files = index.norms(number, chapter)
    address = f"P/{number}" + (f".{chapter}" if chapter is not None else "")
    if files is None:
        return f"no lesson {number} in Platform/lessons.tsv"
    if not files:
        return f"no norms file of {address}"
    for path in files:
        numbers, titles, _ = index.outline(path)
        if name in (numbers if re.fullmatch(r"N[0-9](?:\.[0-9]+[a-z]?)*", name) else titles):
            return None
    return f"no section «{name}» in the norms of {address} (a heading «{name} …» or «N… {name}»)"


def item_problem(index, number, chapter, token):
    files = index.norms(number, chapter)
    if files is None:
        return f"no lesson {number} in Platform/lessons.tsv"
    if not files:
        return f"no norms file of {token.rsplit('-', 1)[0]}"
    for path in files:
        if token in index.outline(path)[2]:
            return None
    return f"{token} is no item of the readiness or the system checklist of its norms"
