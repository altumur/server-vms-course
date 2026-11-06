"""Read consumers.tsv by full package path and explicit consumers union lesson owner. Common packages have no implicit owner; local lesson tables remain without explicit consumers rows. Reading/selection does not execute vectors: generators must reject missing wire/API declarations."""
import re
from pathlib import Path

FORM = 'Platform/common/vectors/consumers.tsv'
LESSONS = 'Platform/lessons.tsv'
COLUMNS = ['package', 'table', 'lesson', 'norm']


class ConsumerError(Exception):
    pass


def lessons(root):
    path = Path(root) / LESSONS
    if not path.is_file():
        raise ConsumerError(f'no {LESSONS}')
    out = set()
    for no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        cells = line.split('\t')
        if len(cells) < 4 or not re.fullmatch(r'\d\d-[a-z][a-z0-9-]*', cells[1]):
            raise ConsumerError(f'{LESSONS}:{no}: invalid lesson')
        if cells[1] in out:
            raise ConsumerError(f'{LESSONS}:{no}: duplicate lesson {cells[1]}')
        out.add(cells[1])
    return out


def table_path(root, package, table, known=None, where=FORM):
    known = lessons(root) if known is None else known
    if not re.fullmatch(r'(common|\d\d-[a-z][a-z0-9-]*)/[a-z0-9-]+', package):
        raise ConsumerError(f'{where}: unknown package {package!r}; expected full (common|NN-name)/name')
    owner, name = package.split('/')
    if owner != 'common' and owner not in known:
        raise ConsumerError(f'{where}: unknown package owner {owner!r}')
    directory = Path(root) / 'Platform' / owner / 'vectors' / name
    if not directory.is_dir():
        raise ConsumerError(f'{where}: unknown package {package!r}')
    if not table or table in ('.', '..') or Path(table).name != table:
        raise ConsumerError(f'{where}: unknown table {table!r}')
    path = directory / table
    if not path.is_file():
        raise ConsumerError(f'{where}: unknown table {package} {table}')
    return path


def read(root):
    """Return {(full package, table):set(lesson)}; validate all rows before selecting a lesson and preserve form order."""
    root = Path(root)
    known = lessons(root)
    path = root / FORM
    if not path.is_file():
        raise ConsumerError(f'no {FORM}')
    out, seen, header = {}, set(), False
    for no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        cells = line.split('\t')
        if not header:
            if cells != COLUMNS:
                raise ConsumerError(f'{FORM}:{no}: columns must be {COLUMNS}')
            header = True
            continue
        where = f'{FORM}:{no}'
        if len(cells) != len(COLUMNS):
            raise ConsumerError(f'{where}: {len(cells)} cells, expected {len(COLUMNS)}')
        package, table, consumer, _ = cells
        if consumer not in known:
            raise ConsumerError(f'{where}: unknown lesson {consumer!r}')
        table_path(root, package, table, known, where)
        identity = package, table, consumer
        if identity in seen:
            raise ConsumerError(f'{where}: duplicate (package, table, lesson) {identity}')
        seen.add(identity)
        owners = out.setdefault((package, table), set())
        owners.add(consumer)
        owner = package.split('/')[0]
        if owner != 'common':
            owners.add(owner)
    if not header:
        raise ConsumerError(f'{FORM}: no header')
    # Ownership does not require an explicit assignment. Common directories are deliberately not scanned.
    for owner in sorted(known):
        for p in sorted((root / 'Platform' / owner / 'vectors').glob('*/*.tsv')):
            out.setdefault((f'{owner}/{p.parent.name}', p.name), set()).add(owner)
    return out


def for_lesson(root, owner):
    if owner not in lessons(root):
        raise ConsumerError(f'{FORM}: unknown lesson {owner!r}')
    return {key for key, consumers in read(root).items() if owner in consumers}
