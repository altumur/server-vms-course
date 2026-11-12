"""Checks of the reading form of M (ADR-0133 addendum (56); P01.175; decisions of the Architect 2026-11-11 on the
lesson-spec proposal, item 4; review P01.214 C1–C5; P01.228; the rollback of the format, ADR-0133 addenda (93), (94),
OBSH.50). Nine checks, each a FAIL with its file and line:

- `history_phrases` — no origin text in the files of M: a closed list of history phrases (both languages) and `ADR-0`
  outside tombstones, in the English sources and their translations of the lessons of `M_FORM_LESSONS` and of the
  common inputs of `M_FORM_COMMON`;
- `index_refs` — the `## Index` table of a chapter, where it has one (a topic whose rules stand in one place is in no
  row; a chapter without such topics has no index): each requirement is live in the norms of the lesson (not removed,
  not merged by the id map), ascending, once; each file address exists (`Platform/…` and `VMS/…` from the course root,
  any other path from the lesson root, no fallback root; the words in parentheses and «…» are not addresses); the
  translation has the same rows;
- `see_also_refs` — no «See also» lines (navigation is the index alone, the Architect 2026-11-12); formerly: the union of the ids of all index rows of its
  topics over the chapters of the lesson without the id itself, ascending, once; a requirement in no row has none;
  the translation has the same lines in the same order;
- `judge_only_refs` — a Markdown link or a path in backquotes from a Markdown file of M to a file outside M — a
  judge-only file of the assembled export lists or, for a lesson of `M_NARROW`, a file of another lesson that the
  table «What this lesson takes from common» of its README does not name — has the marker «(judge-only: …)» in the
  same sentence (a heading, a quoted section name «…» and the textual `sc. NN` are outside this check); a marker
  without such a reference is not judged;
- `req_refs` — every full id `P/NN.K-RNNN` of a lesson of the run in the text of the files of M and J (both
  dispositions of the assembled filter M, translations included) is a live requirement: a removed or merged id is an
  error (the writer readdresses it to the live id), and so is an id the lesson has not; a short `RNNN` of the English
  norms of a chapter — of that chapter, or of the chapter «chapter N.K» named before it in the sentence — is an error
  when it is removed or merged;
- `req_map` — the id map `decisions/journal/<module>/<lesson>/req-id-map.tsv` of the ids merged into paragraphs
  (ADR-0133 addendum (93)): the header `old new file source`; `old` — an id of the lesson, not live, not a tombstone
  of the norms, once; `new` — a live requirement of the lesson (no chains, no cycles); `file` — the address of the
  paragraph of `new` in its norms file, by the kinds of `history_rows`; nonempty source; a row of the history files
  of the lesson with `req_id` = `old`;
- `production_scoped` — the acting label «**Scope: production.**» opens the first paragraph after its req anchor or
  stands right after the id of a checklist item; a quoted label («**Scope: production.**», its definition in N0) does
  not act;
- `history_rows` — the history files `decisions/journal/<module>/<lesson>/history[-K].tsv`: the header
  `req_id file source date removed`, `req_id` `-` or a requirement of the lesson (live, a tombstone of the norms or an
  `old` of the id map), `file#fragment` exists by its kind
  (`#intro`; `#N0`…`#N5` with subsections — the section of the norms by its number in any language; `#/…` in YAML or
  JSON — a JSON Pointer into the parsed document; `#header` — the comment lines of a TSV before its column header,
  `#row:<key>` — the one row of a TSV whose first column is the key, or `#row:<column>=<value>&…` — the one row
  whose named columns hold the values; any other fragment of Markdown — a heading
  anchor), an ISO date, nonempty source and removed text;
- `checklist_marks` — every item `- [ ] **P/NN.K-MM**` of the checklists of the norms names right after its id (after
  the label «**Scope: production.**» when it has it) one mark of the way it is closed: `[test]`, `[reading]`,
  `[stand]` or several of these words through «, »; a withdrawn item has none; the translation has the same English
  words (P/01.1-R151; the Architect on P01.176, P01.228).

A lesson of `M_FORM_STAGE_A` is judged by stage A of its form only: `history_phrases` without its `forms/*.tsv` and
`data/*.tsv`, `judge_only_refs`, `history_rows`, `req_map` and `req_refs`. A lesson without `forms/export.json` takes
its files of M from the common filter M (`export_lists`, ADR-0135 addendum (14)).

The granularity of a requirement is not judged here: an anchor `<!-- req: … -->` opens one paragraph, which carries one
rule or several (the paragraph layout of ADR-0133 addendum (93), P/01; the other lessons keep one rule per item until
their own task) — the review reads it. The checks hold what the layout changes: the merged ids (`req_map`, the
reservation in check_forms.check_req_anchors, `history_rows`), the references to them (`req_refs`, `index_refs`).

Built text: `data/*.schema.json` (v7.build from the dialect and `common.form.yaml`) is not read by `history_phrases`.
The built blocks of the norms (`<!-- form|families|canonical:begin -->` … `:end -->`, v7/sections.py) are read as any
text of M; at stage A a finding in a block that a file the stage does not judge carries (the lesson's data/*.schema.json
and data/*.tsv, the common data catalog) is that file's, counted as history_block_carried. `judge_only_refs` takes a
bare name of a platform file of the data catalog (`ca.pem`) for that file, not a judge-only file of the course of the
same name. See references/validation.md, «Форма M».
"""
import datetime
import fnmatch
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

# Lessons whose M is in the reading form (P01.175, P01.177). A lesson enters when its form is brought in by its own
# task: the checks run on a lesson only after its norms carry no history, their index and «See also» lines.
M_FORM_LESSONS = {"P/01", "P/02", "P/03", "P/04", "P/05", "P/06", "P/07", "P/08", "P/09", "P/10"}  # форма M приведена у всех уроков Платформы (OBSH.41, этап Б принят 2026-11-12)

# Lessons whose stage A of the form is accepted (OBSH.41; the Architect on P04.29, P01.228): history out of the text and
# the judge-only markers, before their norms get the index, «See also», the marks of the checklist (stage B). Only
# history_phrases (outside STAGE_A_OUTSIDE), judge_only_refs and history_rows run on them. A lesson leaves the set when
# it enters M_FORM_LESSONS: a lesson in both is an error.
M_FORM_STAGE_A = set()  # все уроки прошли этап Б (OBSH.41)
STAGE_A_OUTSIDE = ("forms/*.tsv", "data/*.tsv")         # the forms and the data are cleaned at stage B

# The common inputs (paths under Platform/common/ that the common filter gives to M) read by `history_phrases`. Empty:
# on main 2026-11-11 the common inputs carry history (Platform/common/acceptance/: 107 phrases and 148 ADR numbers in
# the sources and translations; the whole Platform/common: 1715 and 1454). They enter by the word of the Architect
# after the common acceptance is cleaned; a prefix, e.g. "Platform/common/acceptance/".
M_FORM_COMMON = ("Platform/common/acceptance/",)  # P01.230: общая приёмка в форме M после P01.229

# Lessons whose M is the narrow M of their pair (ADR-0133 addendum (94); P01.280 §8): the files of the lesson, the common
# inputs (Platform/common/), PAIR_ALWAYS and the files of other lessons that the table «What this lesson takes from
# common» of its README.md names (links of its rows). The export filters cut whole files: a reference from M of the
# lesson to a file of another lesson that the table does not name points outside M, as to a judge-only file
# (judge_only_refs) — the writer removes the reference or adds the file to the table, which the export side follows.
M_NARROW = {"P/01"}
DEPENDENCIES = {"en": "## What this lesson takes from common", "ru": "## Что урок берёт из common"}
PAIR_ALWAYS = ("Platform/README.md", "Platform/lessons.tsv")
# Files of Platform/common/ that belong to another lesson's material and stay out of the narrow M of a pair, by lesson
# (ADR-0133 addendum (93) item 6; project P01.280, inventory P01.283; OBSH.52): a reference from M of the lesson to one
# of them is a reference outside M and needs «(judge-only: …)».
PAIR_COMMON_EXCLUDE = {
    "P/01": ("Platform/common/acceptance/testsub-stand.md", "Platform/common/vectors/slot/README.md"),
}

# The id map of a lesson whose requirements were merged into paragraphs (ADR-0133 addendum (93); P01.280 §3): a journal
# beside the history files, outside M and J. A merged id keeps no tombstone in M: its row reserves it (no reuse) and
# names the live id of its paragraph; the history file keeps the removed text under the old id.
REQ_MAP = "req-id-map.tsv"
REQ_MAP_HEADER = ["old", "new", "file", "source"]

# Closed list of history phrases (ADR-0133 addendum (56) item 1). A paraphrase passes — the review by the checklist.
HISTORY_PHRASES = re.compile("|".join([
    r"Architect's decision", r"decision of the Architect", r"Decided by the Architect",
    r"reconciliation of python and go", r"(?<![A-Za-z])moved from", r"without a change of behaviour",
    r"analysis of (?:the )?review", r"review of stage",
    r"решени[еяю] «?Архитектора", r"решил «?Архитектор", r"сверк[аиуе] python и go", r"перенес[её]н[а-я]* из",
    r"без изменения поведения", r"разбор[а-я]* ревью", r"ревью стади[ия]",
]), re.I)
ADR_NUMBER = re.compile(r"ADR-0")                       # decision item 2: a number of an ADR is origin too
# Not history (decision items 2, 3): a tombstone of a removed requirement and a withdrawn checklist item «снята: `ADR`»
# keep an id from reuse; a row of a closed list added by another lesson names that lesson, not an ADR.
TOMBSTONE = re.compile(r"<!-- removed: \S+ by ADR-[0-9]{4} -->")
WITHDRAWN = re.compile(r"\*\*[^*\s]+\*\*\s+(?:снята|withdrawn|removed):\s*`?ADR-[0-9]{4}`?")

# ADR numbers outside the norms that stay for now, by lesson, as paths from the lesson root (fnmatch). Item 2 of the
# decision removes the numbers from the text of the norms; P01.177 removed them from spec/*.norms.md, P01.176 from
# forms/*.tsv. The other files of M have not been cleaned yet: they enter by the word of the Architect. An exact path
# whose source and translation carry no number any more is stale — an error.
ADR_LATER = {
    "P/01": {
        "README.md": "outside the norms; not cleaned by P01.177",
        "lifecycle.md": "outside the norms; not cleaned by P01.177",
        "spec/01-store.README.md": "outside the norms; not cleaned by P01.177",
        "spec/01-store.api.openapi.yaml": "outside the norms; not cleaned by P01.177",
        "acceptance/1/README.md": "outside the norms; not cleaned by P01.177",
        "acceptance/2/README.md": "outside the norms; not cleaned by P01.177",
        "acceptance/3/README.md": "outside the norms; not cleaned by P01.177",
        "vectors/jcs/README.md": "outside the norms; not cleaned by P01.177",
        "vectors/rights-evaluator/README.md": "outside the norms; not cleaned by P01.177",
    },
    # the debugTip runtime string carries «ADR-0050» byte for byte in module/console.js WORDS, whose canonical bytes the
    # course pins (J-P07-01 SHA in the frozen Source tests); the number stays until the module is regenerated (P07.16)
    "P/07": {
        "data/localization.tsv": "pinned: debugTip = WORDS of the canonical module bytes (J-P07-01), the Architect on P07.16",
    },
}
BUILT = ("data/*.schema.json",)                          # v7.build: judged at the dialect and common.form.yaml
# The built blocks of the norms between their markers (v7/sections.py): the words of the builder and the values of the
# files it builds from. history_phrases reads a block as any text of M. At stage A a finding in a block whose text a
# file the stage does not judge carries (CARRIERS of the lesson, the common data catalog) is a finding of that file:
# it is counted (history_block_carried) and judged with the file at stage B; the words of the builder are judged here.
BLOCK_MARKER = re.compile(r"<!-- (form|families|canonical):(begin|end) -->")
CARRIERS = ("data/*.schema.json", "data/*.tsv")          # from the lesson root
CATALOG = "Platform/common/data/catalog.tsv"
CARRIED_WINDOW = 24                                     # characters of context beside a finding, inside its cell

LANG = {"en": {"index": "## Index", "see": "See also:"}, "ru": {"index": "## Указатель", "see": "См. также:"}}
JUDGE_MARKS = ("judge-only:", "только для судьи:")         # «(judge-only: …)», also «(`X`; judge-only: …)»
LABELS = ("**Scope: production.**", "**Охват: боевой.**")
REQ = r"P/[0-9]{2}(?:\.[0-9]+)?-R[0-9]{3}"
REQ_ID = re.compile(REQ)
REQ_ANCHOR = re.compile(r"<!-- req: (" + REQ + r") -->")
REMOVED_ANCHOR = re.compile(r"<!-- removed: (" + REQ + r") by ADR-[0-9]{4} -->")
CHECK_ITEM = re.compile(r"^\s*- \[[ x]\] \*\*[^*\s]+\*\*\s+")
# An item of a checklist of the norms and the mark of the way it is closed (P/01.1-R151): the words are English in both
# languages; the label of production scope stands between the id and the mark.
ITEM_ID = re.compile(r"^\s*[-*+] \[[ xX]\] \*\*(P/[0-9]{2}(?:\.[0-9]+)?-[0-9]{2})\*\*")
MARK_WORDS = ("test", "reading", "stand")
MARK = re.compile(r"\[([^\]\n]*)\]")
WITHDRAWN_TAIL = re.compile(r"\s+(?:снята|withdrawn|removed):\s*`?ADR-[0-9]{4}")   # WITHDRAWN after a mark
SECOND_MARK = re.compile(r"\s*\[(?:test|reading|stand)(?:, [^\]\n]*)?\]")
HISTORY_HEADER = ["req_id", "file", "source", "date", "removed"]
HISTORY_FILE = re.compile(r"history(?:-((?:0|[1-9][0-9]?)))?\.tsv")
SECTION_NUMBER = re.compile(r"N[0-9](?:\.[0-9]+[a-z]?)*")
TEXT_SUFFIXES = {".md", ".tsv", ".yaml", ".yml", ".json"}


def req_key(value):
    m = re.fullmatch(r"P/([0-9]{2})(?:\.([0-9]+))?-R([0-9]{3})", value)
    return (int(m[1]), int(m[2] or 0), int(m[3])) if m else (999, 999, 999)


def req_map_lines(path):
    """[(line, [cells])] of the data rows of an id map REQ_MAP (after its header line); [] — no map."""
    try:
        lines = Path(path).read_bytes().decode("utf-8").split("\n")
    except (OSError, UnicodeError):
        return []
    if lines and lines[-1] == "":
        lines.pop()
    return [(n, line.split("\t")) for n, line in enumerate(lines[1:], 2)]


def read_req_map(path):
    """{old id: new id} of an id map (a missing or broken map gives what it can: req_map names its errors). Also read
    by check_forms.check_req_anchors: a merged id is reserved as a tombstone is."""
    out = {}
    for _, cells in req_map_lines(path):
        if cells and REQ_ID.fullmatch(cells[0]):
            out.setdefault(cells[0], cells[1] if len(cells) > 1 else "")
    return out


def fenced_lines(text):
    """(line number, line, inside a code fence) for every line; a fence line itself counts as inside."""
    fence = None
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if fence is None and (stripped.startswith("```") or stripped.startswith("~~~")):
            fence = stripped[:3]
            yield n, line, True
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            yield n, line, True
            continue
        yield n, line, False


class Lesson:
    """A lesson of M_FORM_LESSONS: its home, the files of M (sources) by its forms/export.json, the chapter norms."""

    def __init__(self, check, key, home):
        self.check, self.key, self.home = check, key, home
        self.rel = home.relative_to(check.root).as_posix()
        self.number = key.split("/")[1]
        self.chapters = sorted(
            (p for p in (home / "spec").glob("*.norms.md")
             if re.fullmatch(rf"{self.number}(?:\.(?:0|[1-9][0-9]?))?-[^.]+\.norms\.md", p.name)),
            key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"([0-9]+)", p.name)])
        self._req = None
        self._merged = None

    def chapter_of(self, path):
        m = re.fullmatch(rf"{self.number}\.([0-9]+)-.*", path.name)
        return m[1] if m else None

    def translation(self, path):
        return self.home / "ru" / path.relative_to(self.home)

    def m_files(self, model):
        """The sources of M of the lesson: model_and_judge records under its directory, outside ru/."""
        out = []
        for path, disposition in model.items():
            if disposition == "model_and_judge" and path.startswith(self.rel + "/") and \
                    not path[len(self.rel) + 1:].startswith("ru/"):
                out.append(self.check.root / path)
        return sorted(out)

    def requirements(self):
        """{id: (norms file, line)} of the req anchors and the set of removed ids over the English chapter norms."""
        if self._req is None:
            live, removed = {}, set()
            for norms in self.chapters:
                text = norms.read_text(encoding="utf-8")
                for n, line in enumerate(text.splitlines(), 1):
                    for m in REQ_ANCHOR.finditer(line):
                        live.setdefault(m[1], (norms, n))
                    removed.update(REMOVED_ANCHOR.findall(line))
            self._req = (live, removed)
        return self._req

    def journal(self):
        module = "vms" if self.key.startswith("V/") else "platform"
        return self.check.root / "decisions/journal" / module / self.home.name

    def merged(self):
        """{old id: new id} of the id map (REQ_MAP) of the lesson: the rows whose old is an id; req_map judges the rest."""
        if self._merged is None:
            self._merged = read_req_map(self.journal() / REQ_MAP)
        return self._merged

    def retired(self):
        """The ids that are no requirement any more and are not reused: the tombstones of the norms and the merged ids."""
        return self.requirements()[1] | set(self.merged())


def export_model(check):
    """{repository path: disposition} of the assembled M (common filter and the lesson lists)."""
    import export_lists
    assembled, _, _ = export_lists.assemble(check.root)
    return {r["path"]: r["disposition"] for r in assembled["model"]}


def lesson_homes(check, lessons):
    homes = {}
    for _, row in check.lessons_table()[1]:
        key = f"P/{row.get('lesson')}"
        if key in M_FORM_LESSONS | M_FORM_STAGE_A and (lessons is None or row.get("lesson") in lessons) and \
                row.get("dir"):
            homes[key] = check.root / "Platform" / row["dir"]
    return homes


def run(check, lessons=None):
    """The checks over the lessons of M_FORM_LESSONS and M_FORM_STAGE_A that this run checks (`lessons` — lesson
    numbers; None — all) and the common inputs of M_FORM_COMMON."""
    homes = lesson_homes(check, lessons)
    if not homes and not M_FORM_COMMON:
        return
    model = export_model(check)
    checked = []
    for key, home in sorted(homes.items()):
        lesson = Lesson(check, key, home)
        if key in M_FORM_LESSONS and key in M_FORM_STAGE_A:
            check.error(home, f"{key} is in M_FORM_LESSONS and in M_FORM_STAGE_A: stage B of the form judges stage A "
                              "too — remove the lesson from m_form.M_FORM_STAGE_A")
        stage_a = key not in M_FORM_LESSONS
        # The files of M: the lesson's own list forms/export.json, or the common filter M for a lesson that has not
        # brought its list yet (export_lists assembles both).
        files = lesson.m_files(model)
        if not files:
            check.error(home / "forms/export.json" if (home / "forms/export.json").is_file() else home,
                        f"{key} is in the form of M, and the assembled filter M names no file model_and_judge of it")
            continue
        checked.append(lesson)
        history_phrases(check, lesson, files, STAGE_A_OUTSIDE if stage_a else ())
        judge_only_refs(check, lesson, files, model)
        history_rows(check, lesson)
        req_map(check, lesson)
        if stage_a:
            continue
        index_refs(check, lesson)
        see_also_refs(check, lesson)
        production_scoped(check, lesson, files)
        checklist_marks(check, lesson)
    req_refs(check, checked, model)
    common_history(check, model)


# --- history_phrases ---------------------------------------------------------------------------------------------

def _later(lesson, rel):
    return next((glob for glob in ADR_LATER.get(lesson.key, {}) if fnmatch.fnmatchcase(rel, glob)), None) \
        if lesson is not None else None


def carried_text(check, lesson):
    """The text that the files a built block of a lesson at stage A builds from carry and the stage does not judge: the
    string values of its data/*.schema.json, the lines of its data/*.tsv and of the common data catalog (one line each,
    as a table cell has them)."""
    out = []

    def strings(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for k, v in node.items():
                strings(k)
                strings(v)
        elif isinstance(node, list):
            for v in node:
                strings(v)

    paths = sorted({p for glob in CARRIERS for p in lesson.home.glob(glob)}) + [check.root / CATALOG]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                strings(json.loads(text))
            else:
                out.extend(text.split("\n"))
        except (OSError, UnicodeError, ValueError):
            continue                                    # the file's own checks name it
    return "\n".join(s.replace("\n", " ") for s in out)


def _unescape(text):
    return text.replace("\\|", "|").replace("\\<", "<")


def carried(corpus, line, start, end):
    """A finding at line[start:end] of a built block is carried by a file of the corpus: a context of CARRIED_WINDOW
    characters before or after it, inside its table cell, stands in the corpus as is."""
    bars = [-1] + [i for i, ch in enumerate(line) if ch == "|" and (i == 0 or line[i - 1] != "\\")] + [len(line)]
    lo = max(b for b in bars if b < start) + 1
    hi = min(b for b in bars if b >= end)
    for a, b in ((max(lo, start - CARRIED_WINDOW), end), (start, min(hi, end + CARRIED_WINDOW))):
        window = _unescape(line[a:b]).strip()
        if len(window) >= end - start + CARRIED_WINDOW // 2 and window in corpus:
            return True
    return False


def _carried_counted(check, corpus, line, m):
    if carried(corpus, line, m.start(), m.end()):
        check.stats["history_block_carried"] += 1
        return True
    return False


def scan_history(check, path, later=None, corpus=None):
    """Errors for the history phrases and ADR numbers of one file; returns the count of ADR numbers it carries.
    `corpus` — at stage A, carried_text of the lesson: a finding in a built block that it carries is not an error here."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        check.error(path, str(exc))
        return 0
    numbers, block = 0, None
    for n, line in enumerate(text.splitlines(), 1):
        marker = BLOCK_MARKER.fullmatch(line.strip())
        if marker:
            block = marker[1] if marker[2] == "begin" else None
            continue
        where = f" (in the built block «{block}»: the builder or the file it builds from, then rebuild)" if block else ""
        carriable = block is not None and corpus is not None
        for m in HISTORY_PHRASES.finditer(line):
            if not (carriable and _carried_counted(check, corpus, line, m)):
                check.error(path, f"line {n}: history in M «{m.group(0)}» — origin is a row of "
                                  "decisions/journal/<module>/<lesson>/history[-K].tsv, not text of M (ADR-0133 addendum "
                                  f"(56)){where}")
        bare = WITHDRAWN.sub("", TOMBSTONE.sub("", line))
        found = [m for m in ADR_NUMBER.finditer(bare)                         # a block has no tombstone to shift
                 if not (carriable and bare == line and _carried_counted(check, corpus, line, m))]
        numbers += len(found)
        if found and later is None:
            check.error(path, f"line {n}: an ADR number in M — origin, not a norm: the rule in words, the number to "
                              f"the column source of the history file (decision of the Architect 2026-11-11, item 2){where}")
    check.stats["history_phrases"] += 1
    return numbers


def history_phrases(check, lesson, files, outside=()):
    """`outside` — globs from the lesson root not judged at this stage of the form (STAGE_A_OUTSIDE); at that stage the
    findings of the built blocks carried by the files they build from are those files' (carried_text)."""
    carried = {}
    corpus = carried_text(check, lesson) if outside else None
    for source in files:
        rel = source.relative_to(lesson.home).as_posix()
        if source.suffix not in TEXT_SUFFIXES or any(fnmatch.fnmatchcase(rel, b) for b in BUILT + tuple(outside)):
            continue
        later = _later(lesson, rel)
        for path in (source, lesson.translation(source)):
            if path.is_file():
                carried[rel] = carried.get(rel, 0) + scan_history(check, path, later, corpus)
                if later is not None:
                    check.stats["history_adr_later"] += 1
    for glob in ADR_LATER.get(lesson.key, {}):
        if not any(ch in glob for ch in "*?[") and not carried.get(glob) and \
                not any(fnmatch.fnmatchcase(glob, o) for o in outside):
            check.error(lesson.home / glob, f"stale ADR_LATER entry of {lesson.key}: the file carries no ADR number "
                                            "(or is not in M) — remove the entry from m_form.ADR_LATER")


def common_history(check, model):
    if not M_FORM_COMMON:
        return
    common = check.root / "Platform/common"
    for path, disposition in sorted(model.items()):
        if disposition != "model_and_judge" or not any(path.startswith(p) for p in M_FORM_COMMON):
            continue
        source = check.root / path
        if source.suffix not in TEXT_SUFFIXES or not source.is_file():
            continue
        scan_history(check, source)
        translation = common / "ru" / source.relative_to(common)
        if translation.is_file():
            scan_history(check, translation)


# --- index_refs ----------------------------------------------------------------------------------------------------

def index_rows(path, language):
    """[(line, topic, requirements cell, [addresses])] of the index table of a chapter; None — no index."""
    heading = LANG[language]["index"]
    rows, inside, seen = [], False, False
    for n, line, fence in fenced_lines(path.read_text(encoding="utf-8")):
        if fence:
            continue
        if line.startswith("## ") or line.startswith("# "):
            inside = line.strip() == heading
            seen |= inside
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or set("".join(cells)) <= set("-: ") or cells[0] in ("Topic", "Тема"):
            continue
        rows.append((n, cells[0], cells[1], file_addresses(cells[2])))
    return rows if seen else None


def file_addresses(cell):
    """The backquoted addresses at the top level of a Files cell: not inside parentheses or «…»."""
    out, depth, quote, i = [], 0, 0, 0
    while i < len(cell):
        ch = cell[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "«":
            quote += 1
        elif ch == "»":
            quote = max(0, quote - 1)
        elif ch == "`":
            end = cell.find("`", i + 1)
            if end < 0:
                break
            if depth == 0 and quote == 0:
                out.append(cell[i + 1:end])
            i = end
        i += 1
    return out


def resolve_address(check, lesson, address):
    """`Platform/…`, `VMS/…` — from the course root, any other path — from the lesson root; no fallback root."""
    base = check.root if address.split("/", 1)[0] in ("Platform", "VMS") else lesson.home
    target = Path(posixpath.normpath((base / address).as_posix()))
    try:
        target.relative_to(check.root)
    except ValueError:
        return None
    return target


def index_refs(check, lesson):
    """A chapter may have no index and an index may be short: a topic is in a row only when its rules stand in more than
    one place (one paragraph of several rules is one place) — completeness is judged by reading. Every row leads to
    live requirements and existing files."""
    live, removed = lesson.requirements()
    merged = lesson.merged()
    for norms in lesson.chapters:
        rows = index_rows(norms, "en")
        translation = lesson.translation(norms)
        ru_rows = index_rows(translation, "ru") if translation.is_file() else None
        if rows is None:
            if ru_rows is not None:
                check.error(translation, "the translation has an index, the source has none")
            continue
        for n, _, cell, addresses in rows:
            ids = [token.strip() for token in cell.split(",") if token.strip()]
            for token in ids:
                check.stats["index_refs"] += 1
                if not REQ_ID.fullmatch(token):
                    check.error(norms, f"line {n}: index: «{token}» is not a requirement id P/NN.K-RNNN")
                elif token in removed:
                    check.error(norms, f"line {n}: index: {token} is a removed requirement")
                elif token in merged and token not in live:
                    check.error(norms, f"line {n}: index: {token} is merged into {merged[token]} ({REQ_MAP}): the row "
                                       "names the live id once")
                elif token not in live:
                    check.error(norms, f"line {n}: index: {token} is not a requirement of {lesson.key}")
            good = [t for t in ids if REQ_ID.fullmatch(t)]
            if good != sorted(set(good), key=req_key):
                check.error(norms, f"line {n}: index: the requirements go ascending, each once")
            for address in addresses:
                check.stats["index_refs"] += 1
                target = resolve_address(check, lesson, address)
                if target is None or not target.exists():
                    check.error(norms, f"line {n}: index: no file `{address}` (Platform/… and VMS/… from the course "
                                       f"root, other paths from the lesson root {lesson.rel}/)")
        if ru_rows is None:
            if translation.is_file():
                check.error(translation, f"the source has an index, the translation has no «{LANG['ru']['index']}»")
            continue
        if len(ru_rows) != len(rows):
            check.error(translation, f"index: {len(ru_rows)} rows, the source has {len(rows)}")
            continue
        for (n, _, cell, addresses), (_, _, en_cell, en_addresses) in zip(ru_rows, rows):
            if REQ_ID.findall(cell) != REQ_ID.findall(en_cell) or addresses != en_addresses:
                check.error(translation, f"line {n}: index row differs from the source in its requirements or files")


# --- see_also_refs -------------------------------------------------------------------------------------------------

def see_lines(path, language):
    """[(line, current req anchor or None, [tokens])] of the «See also» lines outside code."""
    word, out, current = LANG[language]["see"], [], None
    for n, line, fence in fenced_lines(path.read_text(encoding="utf-8")):
        if fence:
            continue
        m = REQ_ANCHOR.search(line)
        if m:
            current = m[1]
        stripped = line.strip()
        if stripped.startswith(word):
            tokens = [t.strip() for t in stripped[len(word):].strip().rstrip(".").split(",") if t.strip()]
            out.append((n, current, tokens))
    return out


def see_also_refs(check, lesson):
    """Navigation of form M is the index alone (the Architect 2026-11-12, by P08.25: «See also» lines with the union of
    the topics tripled the norms — P/01.3 489 KB, 377 KB of them «See also»): a «See also» line is an error."""
    for norms in lesson.chapters:
        for path, language in ((norms, "en"), (lesson.translation(norms), "ru")):
            if not path.is_file():
                continue
            for n, current, _ in see_lines(path, language):
                check.stats["see_also_refs"] += 1
                check.error(path, f"line {n}: a «{LANG[language]['see']}» line — form M navigates by the index alone "
                                  "(no per-requirement «See also»)")


# --- judge_only_refs -----------------------------------------------------------------------------------------------

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ«\[*(`])")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK_TARGET = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
PATHISH = re.compile(r"[\w.*/<>{}-]+\.[A-Za-z0-9]+")


def units(text):
    """(first line, text) of every sentence of the Markdown prose outside code; headings are left out; a table row
    and a list item start a unit of their own."""
    block, start = [], None

    def flush():
        if block:
            joined, first = "\n".join(block), start
            offset = 0
            for part in SENTENCE_END.split(joined):
                at = joined.find(part, offset)
                yield first + joined.count("\n", 0, at), part
                offset = at + len(part)

    out = []
    for n, line, fence in fenced_lines(text):
        stripped = line.strip()
        boundary = fence or not stripped or stripped.startswith("#") or stripped.startswith("|") or \
            re.match(r"^\s*(?:[-*+]|[0-9]+[.)])\s", line) or stripped.startswith("<!--")
        if boundary:
            out.extend(flush())
            block, start = [], None
            if fence or not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
                continue
            if stripped.startswith("|"):
                out.append((n, stripped))
                continue
        if start is None:
            start = n
        block.append(line)
    out.extend(flush())
    return out


def quoted(text, at):
    """Inside «…» — a quoted name of a section, not a reference."""
    return text.count("«", 0, at) > text.count("»", 0, at)


def platform_files(check):
    """The names of the files of the platform: the last segment of each `file` key of the common data catalog that is
    a name, not a placeholder (`/etc/w2c/tls/ca.pem` → `ca.pem`). A bare name of one of them in M is that file of the
    platform, which M defines, not a file of the course of the same name."""
    names = set()
    try:
        lines = (check.root / CATALOG).read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeError):
        return names                                    # the catalog's own checks name it
    for line in lines:
        cols = line.split("\t")
        if len(cols) > 1 and not line.startswith("#") and cols[1] == "file":
            name = cols[0].rsplit("/", 1)[-1]
            if name and not re.search(r"[<>%*]", name):
                names.add(name)
    return names


def dependencies(check, lesson):
    """The repository paths that the table «What this lesson takes from common» of the README of the lesson names: the
    link targets of its section and the backquoted paths `Platform/…`; None — the README has no such section."""
    readme = lesson.home / "README.md"
    if not readme.is_file():
        return None
    out, inside, seen = set(), False, False
    for _, line, fence in fenced_lines(readme.read_text(encoding="utf-8")):
        if fence:
            continue
        if line.startswith("## ") or line.startswith("# "):
            inside = line.strip() == DEPENDENCIES["en"]
            seen |= inside
            continue
        if not inside:
            continue
        for m in LINK_TARGET.finditer(line):
            target = unquote(urlsplit(m[1]).path)
            if target:
                full = Path(posixpath.normpath((readme.parent / target).as_posix()))
                if full.is_relative_to(check.root):
                    out.add(full.relative_to(check.root).as_posix())
        for m in CODE_SPAN.finditer(line):
            if m[1].split("/", 1)[0] == "Platform":
                out.add(posixpath.normpath(m[1]))
    return out if seen else None


def pair_m(check, lesson, model):
    """The files of M of the pair of a lesson of M_NARROW: model_and_judge records of the lesson, of Platform/common/
    without its PAIR_COMMON_EXCLUDE, PAIR_ALWAYS and of the dependency table; None — the README has no dependency
    table."""
    named = dependencies(check, lesson)
    if named is None:
        return None
    excluded = set(PAIR_COMMON_EXCLUDE.get(lesson.key, ()))
    return {p for p, d in model.items() if d == "model_and_judge" and p not in excluded and (
        p.startswith(lesson.rel + "/") or p.startswith("Platform/common/") or p in PAIR_ALWAYS or p in named)}


def judge_only_refs(check, lesson, files, model):
    judge = {p for p, d in model.items() if d == "judge_only" and "/ru/" not in p}
    seen_model = {p for p, d in model.items() if d == "model_and_judge"}
    outside = set()                                     # model_and_judge of the course, outside M of the pair
    if lesson.key in M_NARROW:
        pair = pair_m(check, lesson, model)
        if pair is None:
            check.error(lesson.home / "README.md", f"{lesson.key} is in m_form.M_NARROW, and its README.md has no "
                                                   f"«{DEPENDENCIES['en'][3:]}»: the narrow M of the pair is the lesson, "
                                                   "common and the files that table names")
            pair = {p for p in seen_model if p.startswith(lesson.rel + "/") or p.startswith("Platform/common/")}
        outside = {p for p in seen_model - pair if "/ru/" not in p}
        seen_model = pair
        judge |= outside
    own_judge = {posixpath.basename(p) for p in judge if p.startswith(lesson.rel + "/")} - platform_files(check)
    own_model = {posixpath.basename(p) for p in seen_model if p.startswith(lesson.rel + "/")}
    root = check.root

    def rel(path):
        return posixpath.normpath(path.as_posix() if isinstance(path, Path) else path)

    def target_of(token, base_dir, link):
        token = unquote(urlsplit(token).path) if link else token
        if not token or (not link and not PATHISH.fullmatch(token)):
            return None
        candidates = [rel((base_dir / token).relative_to(root) if (base_dir / token).is_relative_to(root) else token)]
        if not link:
            candidates.append(rel(f"{lesson.rel}/{token}"))
            if token.split("/", 1)[0] in ("Platform", "VMS"):
                candidates.append(rel(token))
        for candidate in candidates:
            parts = candidate.split("/")
            if len(parts) > 3 and parts[0] in ("Platform", "VMS") and parts[2] == "ru":
                candidate = "/".join(parts[:2] + parts[3:])        # a translation of a file is that file for M
            if candidate in judge:
                return candidate
            if "*" in candidate and any(fnmatch.fnmatchcase(j, candidate) for j in judge) and \
                    not any(fnmatch.fnmatchcase(m, candidate) for m in seen_model):
                return candidate
        if not link and "/" not in token:
            name = token
            if name in own_judge and name not in own_model:
                return f"{lesson.rel}/…/{name}"
            if "*" in name and any(fnmatch.fnmatchcase(j, name) for j in own_judge) and \
                    not any(fnmatch.fnmatchcase(m, name) for m in own_model):
                return f"{lesson.rel}/…/{name}"
        return None

    for source in files:
        if source.suffix != ".md":
            continue
        for path in (source, lesson.translation(source)):
            if not path.is_file():
                continue
            base_dir = (path.parent if path == source else source.parent).resolve()
            link_dir = path.parent.resolve()
            for first, sentence in units(path.read_text(encoding="utf-8")):
                marked = any(mark in sentence for mark in JUDGE_MARKS)
                found = [(m.start(), m.group(1), False) for m in CODE_SPAN.finditer(sentence)] + \
                        [(m.start(), m.group(1), True) for m in LINK_TARGET.finditer(sentence)]
                for at, token, link in sorted(found):
                    target = target_of(token, link_dir if link else base_dir, link)
                    if target is None or quoted(sentence, at):
                        continue
                    check.stats["judge_only_refs"] += 1
                    if marked:
                        continue
                    n = first + sentence.count("\n", 0, at)
                    if target in outside or "*" in target and any(fnmatch.fnmatchcase(o, target) for o in outside):
                        check.error(path, f"line {n}: a reference to {target}, a file of another lesson outside M of "
                                          f"the pair {lesson.key} (the export filters cut whole files; the table "
                                          f"«{DEPENDENCIES['en'][3:]}» of README.md does not name it): add the file to "
                                          "that table or remove the reference; a closed reference carries "
                                          "«(judge-only: …)» in the same sentence")
                    else:
                        check.error(path, f"line {n}: a reference to the judge-only file {target} without "
                                          "«(judge-only: …)» in the same sentence (the file is not in M)")


# --- production_scoped ---------------------------------------------------------------------------------------------

def production_scoped(check, lesson, files):
    for source in files:
        if source.suffix != ".md":
            continue
        for path in (source, lesson.translation(source)):
            if not path.is_file():
                continue
            translated = path != source
            previous = ""                        # the last nonblank line before this one
            blank = True
            for n, line, fence in fenced_lines(path.read_text(encoding="utf-8")):
                if fence:
                    previous, blank = line, False
                    continue
                code = [(m.start(), m.end()) for m in CODE_SPAN.finditer(line)]
                for label in LABELS:
                    start = line.find(label)
                    while start >= 0:
                        acting = not line[:start].rstrip().endswith("«") and \
                            not any(a <= start < b for a, b in code)
                        if acting:
                            check.stats["production_scoped"] += 1
                            item = CHECK_ITEM.match(line)
                            opens = re.fullmatch(r"\s*(?:[-*+]\s+)?", line[:start]) is not None
                            # The source: the first paragraph after its req anchor. The translation has no anchors
                            # (en_mirror holds it to the source): the start of a paragraph.
                            first = REQ_ANCHOR.search(previous) is not None or \
                                (translated and (blank or previous.lstrip().startswith("<!--")))
                            if item and item.end() == start or opens and first:
                                pass
                            elif opens:
                                check.error(path, f"line {n}: the label {label} opens a paragraph that is not the first "
                                                  "after a req anchor: a production requirement is its own requirement")
                            else:
                                check.error(path, f"line {n}: the label {label} inside a paragraph: it opens the first "
                                                  "paragraph of its requirement or follows the id of a checklist item; "
                                                  "a mention is quoted «…»")
                        start = line.find(label, start + 1)
                if line.strip():
                    previous, blank = line, False
                else:
                    blank = True


# --- checklist_marks -----------------------------------------------------------------------------------------------

class Error(str):
    """Why a checklist item breaks the grammar of its mark."""


def checklist_items(text, label=LABELS[0]):
    """[(line, id, mark)] of the checklist items outside code: mark — the tuple of the words of the one mark right
    after the id (and the label `label`), "withdrawn" for a withdrawn item, or an error text by the grammar."""
    out = []
    for n, line, fence in fenced_lines(text):
        m = None if fence else ITEM_ID.match(line)
        if not m:
            continue
        rest = line[m.end():]
        labelled = rest.startswith(" " + label)
        after = rest[len(label) + 1:] if labelled else rest
        mark = MARK.match(after, 1) if after.startswith(" [") else None
        if WITHDRAWN.match(line, line.index("**")):
            out.append((n, m[1], Error("a withdrawn item has no mark") if mark else "withdrawn"))
            continue
        if mark is None:
            out.append((n, m[1], Error("no mark [test], [reading] or [stand] right after the id" +
                                       (f" and {label}" if labelled else ""))))
            continue
        words, tail = tuple(mark[1].split(", ")), after[mark.end():]
        if WITHDRAWN_TAIL.match(tail):
            out.append((n, m[1], Error("a withdrawn item has no mark")))
        elif label in tail:
            out.append((n, m[1], Error(f"the label {label} goes between the id and the mark")))
        elif any(w not in MARK_WORDS for w in words):
            out.append((n, m[1], Error(f"the mark [{mark[1]}]: the words {', '.join(MARK_WORDS)} through «, », "
                                       "a closed list")))
        elif len(set(words)) != len(words):
            out.append((n, m[1], Error(f"the mark [{mark[1]}] repeats a word")))
        elif SECOND_MARK.match(tail):
            out.append((n, m[1], Error("a second mark: one mark, several words in it through «, »")))
        elif tail and not tail.startswith(" "):
            out.append((n, m[1], Error(f"the mark [{mark[1]}] is not followed by a space")))
        else:
            out.append((n, m[1], words))
    return out


def withdrawn_items(text):
    """The ids of the withdrawn checklist items of a source of norms (stage_norms of check_spec: no stage required)."""
    return {value for _, value, mark in checklist_items(text) if mark == "withdrawn"}


def _shown(mark):
    return mark if mark == "withdrawn" else f"[{', '.join(mark)}]"


def checklist_marks(check, lesson):
    for norms in lesson.chapters:
        marks = {}
        for n, value, mark in checklist_items(norms.read_text(encoding="utf-8"), LABELS[0]):
            check.stats["checklist_marks"] += 1
            if isinstance(mark, Error):
                check.error(norms, f"line {n}: {value}: {mark} (P/01.1-R151)")
            else:
                marks[value] = mark
        translation = lesson.translation(norms)
        if not translation.is_file():
            continue
        for n, value, mark in checklist_items(translation.read_text(encoding="utf-8"), LABELS[1]):
            check.stats["checklist_marks"] += 1
            if isinstance(mark, Error):
                check.error(translation, f"line {n}: {value}: {mark} (P/01.1-R151)")
            elif value in marks and marks[value] != mark:
                check.error(translation, f"line {n}: {value}: the mark {_shown(mark)} differs from the source "
                                         f"{_shown(marks[value])}: the same English words")


# --- history_rows --------------------------------------------------------------------------------------------------

def _pointer(document, fragment):
    value = document
    for part in fragment.split("/")[1:]:
        part = unquote(part).replace("~1", "/").replace("~0", "~")
        if isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", part) and int(part) < len(value):
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return False
    return True


def _sections(path):
    numbers = set()
    for _, line, fence in fenced_lines(path.read_text(encoding="utf-8")):
        m = None if fence else re.match(r"^#{1,6}\s+(N[0-9](?:\.[0-9]+[a-z]?)*)(?:\s|$)", line)
        if m:
            numbers.add(m[1])
    return numbers


def _tsv(target):
    """(the comment lines before the column header, {value of the first column: [lines]}, column names, [(line, cells)])
    of a TSV form."""
    lines = target.read_bytes().decode("utf-8").split("\n")
    head = next((i for i, line in enumerate(lines) if line and not line.startswith("#")), len(lines))
    names = lines[head].split("\t") if head < len(lines) else []
    first = head + 1                                   # the first data line (index) after a plain header line
    # a commented header (scenario tables: «# scenario<TAB>step<TAB>…» and data from the first plain line, the
    # Architect on P01.249): the last # line before the data, with as many TAB fields as the first data line
    above = [i for i in range(head) if lines[i].startswith("#")]
    if above and "\t" in lines[above[-1]] and head < len(lines):
        cells = lines[above[-1]].lstrip("#").strip(" ").split("\t")
        if len(cells) == len(lines[head].split("\t")):
            names, first = [c.strip() for c in cells], head
    keys, rows = {}, []
    for n, line in enumerate(lines[first:], first + 1):
        if line and not line.startswith("#"):
            cells = line.split("\t")
            keys.setdefault(cells[0], []).append(n)
            rows.append((n, cells))
    return [line for line in lines[:head] if line.startswith("#")], keys, names, rows


def _tsv_problem(target, fragment, parsed):
    """A TSV is addressed by its rows, not by line numbers: `#header` — the comment of its header (the lines # before
    the column header), `#row:<key>` — the one row whose first column is the key (the Architect on P02.59, P01.228)."""
    if target not in parsed:
        try:
            parsed[target] = _tsv(target)
        except (OSError, UnicodeError) as exc:
            return f"unreadable: {exc}"
    comment, keys, names, rows = parsed[target]
    if fragment == "header":
        return None if comment else "#header: the form has no comment lines # before its column header"
    if not fragment.startswith("row:") or fragment == "row:":
        return "a TSV form is addressed by #header or #row:<value of the first column> (or #row:<column>=<value>&…)"
    key = fragment[len("row:"):]
    if "=" in key:
        # a composite key (the Architect on P03.29): named columns, each equal to its value; exactly one row matches
        wanted = []
        for part in key.split("&"):
            name, _, value = part.partition("=")
            if name not in names:
                return f"#row:{key}: no column «{name}» in the form (columns: {', '.join(names)})"
            wanted.append((names.index(name), value))
        if len({i for i, _ in wanted}) != len(wanted):
            return f"#row:{key}: a column is named twice"
        hit = [n for n, cells in rows if all((cells[i] if i < len(cells) else "") == v for i, v in wanted)]
        if not hit:
            return f"#row:{key}: no row matches"
        if len(hit) > 1:
            return f"#row:{key}: rows {', '.join(map(str, hit))} match: not an address — name more columns"
        return None
    if key not in keys:
        return f"#row:{key}: no row with the first column «{key}»"
    if len(keys[key]) > 1:
        return f"#row:{key}: the first column «{key}» repeats at lines {', '.join(map(str, keys[key]))}: not an address"
    return None


def history_rows(check, lesson):
    journal = lesson.journal()
    if not journal.is_dir():
        return
    live, _ = lesson.requirements()
    removed = lesson.retired()                         # a merged id keeps its history rows (the map, not M, keeps it)
    chapters = {lesson.chapter_of(p) for p in lesson.chapters}
    parsed = {}
    for path in sorted(journal.iterdir()):
        m = HISTORY_FILE.fullmatch(path.name)
        if not m:
            continue
        if m[1] is not None and m[1] not in chapters:
            check.error(path, f"a history file of chapter {m[1]}, which {lesson.key} has not")
        lines = path.read_bytes().decode("utf-8").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if not lines or lines[0].split("\t") != HISTORY_HEADER:
            check.error(path, f"line 1: the header is {' '.join(HISTORY_HEADER)} (TAB-separated)")
            continue
        for n, line in enumerate(lines[1:], 2):
            check.stats["history_rows"] += 1
            cols = line.split("\t")
            if len(cols) != len(HISTORY_HEADER):
                check.error(path, f"line {n}: {len(cols)} fields, expected {len(HISTORY_HEADER)}")
                continue
            req_id, address, source, date, text = cols
            if req_id != "-" and not REQ_ID.fullmatch(req_id):
                check.error(path, f"line {n}: req_id «{req_id}» is neither - nor a requirement id")
            elif req_id != "-" and req_id not in live and req_id not in removed:
                check.error(path, f"line {n}: req_id {req_id} is not a requirement of {lesson.key} (live, a tombstone "
                                  f"of the norms or an old id of {REQ_MAP})")
            if not source.strip():
                check.error(path, f"line {n}: an empty source")
            if not text.strip():
                check.error(path, f"line {n}: an empty removed text")
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date):
                    raise ValueError
                datetime.date.fromisoformat(date)
            except ValueError:
                check.error(path, f"line {n}: date «{date}» is not an ISO date YYYY-MM-DD")
            problem = address_problem(check, lesson, address, parsed)
            if problem:
                check.error(path, f"line {n}: file «{address}»: {problem}")


def address_problem(check, lesson, address, parsed):
    """None, or why `file#fragment` of a history row does not resolve (P01.214 C3)."""
    name, hashed, fragment = address.partition("#")
    if not name or not hashed or not fragment:
        return "expected <path from the lesson root>#<fragment>"
    if name.split("/", 1)[0] in ("ru", "journal") or name.startswith("/") or ".." in name.split("/"):
        return "a path of a source from the lesson root (not ru/, journal/, absolute or outside)"
    target = lesson.home / name
    if not target.is_file():
        return f"no file {lesson.rel}/{name}"
    if target.suffix == ".tsv":
        return _tsv_problem(target, fragment, parsed)
    if fragment == "header" and target.suffix != ".md" or fragment.startswith("row:"):
        return f"#{fragment} addresses a TSV form"
    if fragment == "intro":
        return None if target.suffix == ".md" else "#intro addresses the introduction of a Markdown file"
    if SECTION_NUMBER.fullmatch(fragment):
        if target.suffix != ".md":
            return f"#{fragment} addresses a section of norms in Markdown"
        return None if fragment in _sections(target) else f"no section {fragment} (a heading «{fragment} …»)"
    if fragment.startswith("/"):
        if target.suffix not in (".yaml", ".yml", ".json"):
            return "a JSON Pointer #/… addresses YAML or JSON"
        if target not in parsed:
            try:
                text = target.read_text(encoding="utf-8")
                parsed[target] = json.loads(text) if target.suffix == ".json" else yaml.safe_load(text)
            except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
                return f"unreadable: {exc}"
        return None if _pointer(parsed[target], fragment) else f"no JSON Pointer {fragment}"
    if target.suffix != ".md":
        return "a heading anchor addresses Markdown"
    return None if fragment in check.anchors(target) else f"no heading anchor #{fragment}"


# --- req_map -------------------------------------------------------------------------------------------------------

def history_ids(lesson):
    """The req_id values of the history files of the lesson."""
    out = set()
    journal = lesson.journal()
    for path in sorted(journal.iterdir()) if journal.is_dir() else []:
        if HISTORY_FILE.fullmatch(path.name):
            for _, cells in req_map_lines(path):
                if cells:
                    out.add(cells[0])
    return out


def req_map(check, lesson):
    """The id map of the merged ids (REQ_MAP): an old id of the lesson, not live and not a tombstone, once; the live id of
    its paragraph; the address of that paragraph in the norms file of the live id; the source; a history row."""
    path = lesson.journal() / REQ_MAP
    if not path.is_file():
        return
    lines = path.read_bytes().decode("utf-8").split("\n")
    if not lines or lines[0].split("\t") != REQ_MAP_HEADER:
        check.error(path, f"line 1: the header is {' '.join(REQ_MAP_HEADER)} (TAB-separated)")
        return
    live, tombstones = lesson.requirements()
    history = history_ids(lesson)
    prefix, single = lesson.key + ".", lesson.key + "-"      # P/NN.K-RNNN; a lesson of one chapter: P/NN-RNNN
    seen, parsed = {}, {}
    for n, cells in req_map_lines(path):
        check.stats["req_map"] += 1
        if len(cells) != len(REQ_MAP_HEADER):
            check.error(path, f"line {n}: {len(cells)} fields, expected {len(REQ_MAP_HEADER)}")
            continue
        old, new, address, source = cells
        if not REQ_ID.fullmatch(old) or not (old.startswith(prefix) or old.startswith(single)):
            check.error(path, f"line {n}: old «{old}» is not a requirement id of {lesson.key}")
        elif old in seen:
            check.error(path, f"line {n}: old {old} repeats (line {seen[old]}): one row per merged id")
        elif old in live:
            check.error(path, f"line {n}: old {old} is a live anchor of the norms: a merged id is not reused")
        elif old in tombstones:
            check.error(path, f"line {n}: old {old} has a tombstone in the norms: a retired id is kept in one place")
        elif old not in history:
            check.error(path, f"line {n}: old {old} has no row of the history files of {lesson.key} (req_id {old}): "
                              "the removed text stays there")
        seen.setdefault(old, n)
        if new not in live:
            why = "a merged id: no chains" if new in lesson.merged() else \
                "a removed id" if new in tombstones else "not a requirement of the lesson"
            check.error(path, f"line {n}: new «{new}» is not a live requirement of {lesson.key} ({why})")
        else:
            norms = live[new][0].relative_to(lesson.home).as_posix()
            problem = address_problem(check, lesson, address, parsed)
            if problem:
                check.error(path, f"line {n}: file «{address}»: {problem}")
            elif address.partition("#")[0] != norms:
                check.error(path, f"line {n}: file «{address}»: the paragraph of {new} is in {norms}")
        if not source.strip():
            check.error(path, f"line {n}: an empty source")


# --- req_refs ------------------------------------------------------------------------------------------------------

SHORT_REQ = re.compile(r"(?<![\w/.-])R([0-9]{3})(?![0-9])")
CHAPTER_WORD = re.compile(r"\bchapter ([0-9]{1,2})\.([0-9]+)\b")
LESSON_OF = re.compile(r"P/[0-9]{2}")


def retired_problem(lesson, value):
    """None for an id that is not removed or merged; else why a reference to it is an error."""
    live, tombstones = lesson.requirements()
    merged = lesson.merged()
    if value in merged and value not in live:
        return f"{value}, merged into {merged[value]} ({REQ_MAP}): readdress it to {merged[value]}"
    if value in tombstones:
        return f"{value}, a removed requirement: the rule it named is gone or lives under another id"
    return None


def req_refs(check, lessons, model):
    """Every full id of a lesson of the run in the text of M and J is live; a short id of the English norms is not
    removed or merged. A tombstone of the norms names its own removed id and is not a reference."""
    if not lessons:
        return
    by_key = {lesson.key: lesson for lesson in lessons}
    for rel in sorted(model):
        path = check.root / rel
        if path.suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue                                    # the file's own checks name it
        if "-R" not in text:
            continue
        for n, line in enumerate(text.split("\n"), 1):
            if "-R" not in line:
                continue
            for m in REQ_ID.finditer(REMOVED_ANCHOR.sub("", line)):
                lesson = by_key.get(LESSON_OF.match(m[0])[0])
                if lesson is None:
                    continue
                check.stats["req_refs"] += 1
                problem = retired_problem(lesson, m[0])
                if problem is None and m[0] not in lesson.requirements()[0]:
                    problem = f"{m[0]}, not a requirement of {lesson.key}"
                if problem:
                    check.error(path, f"line {n}: a reference to {problem}")
    for lesson in lessons:
        for norms in lesson.chapters:
            chapter = lesson.chapter_of(norms)
            for first, sentence in units(REMOVED_ANCHOR.sub("", norms.read_text(encoding="utf-8"))):
                for m in SHORT_REQ.finditer(sentence):
                    named = list(CHAPTER_WORD.finditer(sentence, 0, m.start()))
                    if named and int(named[-1][1]) != int(lesson.number):
                        continue                        # a short id of another lesson
                    part = named[-1][2] if named else chapter
                    value = f"{lesson.key}.{part}-R{m[1]}" if part is not None else f"{lesson.key}-R{m[1]}"
                    check.stats["req_refs"] += 1
                    problem = retired_problem(lesson, value)
                    if problem:
                        line = first + sentence.count("\n", 0, m.start())
                        check.error(norms, f"line {line}: a short reference R{m[1]} to {problem}")
