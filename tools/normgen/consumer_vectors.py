"""Cross-lesson wire.tsv table bindings. Only the Go API is declared here; consumers.tsv assigns rows."""
import wire
import wire_vectors

API = {
    '01-store/jcs': ('JCS', 'cells'),
    '06-console/rid': ('RidCells', 'cells'),
    '06-console/request-digest': ('RequestDigestCells', 'cells'),
    '06-console/requests-body': ('RequestsBody', 'cells'),
}


def declarations(root, g):
    foreign = {key for key in g.lesson_consumers(root)
               if key[0].split('/')[0] not in ('common', g.L.key)}
    if not foreign:
        return []
    bindings = wire.lesson_bindings(root, g.L.key, wire.parse(root, keys=foreign, surfaces={"vectors"}))
    bindings = [b for b in bindings if b.surface == 'vectors']
    missing = foreign - {(b.package, b.table) for b in bindings}
    if missing:
        raise wire.WireError(f'{wire.FORM}: no vector binding of assigned foreign tables {sorted(missing)}')
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
