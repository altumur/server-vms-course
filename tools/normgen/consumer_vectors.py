"""Selected wire.tsv bindings. Only the Go API is declared here; the forms own the wire."""
from pathlib import Path

import gate
import tsv_input
import wire
import wire_vectors

API = {
    '03-worker/fetched': ('Fetched', 'cells'),
    '01-store/jcs': ('JCS', 'cells'),
    '06-console/rid': ('RidCells', 'cells'),
    '06-console/request-digest': ('RequestDigestCells', 'cells'),
    '06-console/requests-body': ('RequestsBody', 'cells'),
}


def declarations(root, g):
    assigned = g.lesson_consumers(root)
    selected = {key for key in assigned if key[0].split('/')[0] not in ('common', g.L.key)}
    # Local APIs are selected only by vector checks in parsed gate cells. Other
    # stage columns, comments, and text substrings cannot introduce a binding.
    stages = Path(root) / g.L.rel / 'forms/stages.kit.tsv'
    packages = set()
    if stages.is_file():
        try:
            table = tsv_input.read(stages, root=root)
            if 'gate' not in table.columns:
                raise wire.WireError(f'{stages}: missing gate column')
            for no, row in table.rows:
                try:
                    packages.update(gate.vector_packages(row['gate'], g.L.key))
                except gate.GateError as exc:
                    raise wire.WireError(f'{stages}:{no}: {exc}') from None
        except tsv_input.TSVError as exc:
            raise wire.WireError(str(exc)) from None
    local = {p for p in packages if p in API and p.split('/')[0] == g.L.key}
    missing_packages = local - {p for p, _ in assigned}
    if missing_packages:
        raise wire.WireError(f'{wire.FORM}: no assigned tables of selected local APIs {sorted(missing_packages)}')
    selected.update(key for key in assigned if key[0] in local)
    if not selected:
        return []
    bindings = wire.lesson_bindings(root, g.L.key, wire.parse(root, keys=selected, surfaces={"vectors"}))
    bindings = [b for b in bindings if b.surface == 'vectors']
    missing = selected - {(b.package, b.table) for b in bindings}
    if missing:
        raise wire.WireError(f'{wire.FORM}: no vector binding of selected tables {sorted(missing)}')
    out = []
    ex = wire.Expander(root)
    for b in bindings:
        if b.package not in API:
            raise wire.WireError(f'{wire.FORM}: no Go adapter API for assigned {b.package}')
        fn, args = API[b.package]
        runs, excluded = ex.run(b, g.L.key)
        out.append(dict(package=b.package, table=b.table, surface=b.surface, fn=fn, args=args,
                        inputs=sorted({k for d in b.inputs for k in d['cells']}), files=b.files,
                        compare=b.compare, doc=f'Native wire: Platform/{b.norm}.',
                        _form=True, _runs=runs, _excluded=excluded))
    return out


def render(root, g, decls):
    chosen = [d for d in decls if d.get('_form')]
    if not chosen:
        return {}, []
    runs = [r for d in chosen for r in d['_runs']]
    excluded = [e for d in chosen for e in d['_excluded']]
    return wire_vectors.render(root, g, chosen, runs, excluded, scaffold=False)
