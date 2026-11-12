"""P01.251 (from verify_ji_p0226.py): verdict of verify_ji.py (P01.121 rules) on the J-input, with each hit accounted for.
Independent of the operator code: classes re-derived here from the Architect's answers
2026-11-11T09:23:54Z (verdict corpus = segment spec_verdicts/legacy_spec_verdicts) and
09:28:46Z (no code class inside acceptance/<n>/inputs/); exclusions read from the assembled filter FILTER-JI.json.
P01.251 adds two excluded classes inside routing directories: check_spec schemas of P01.228 (basis 'P01.228: data of check_spec'),
and lesson export lists forms/export.json (README of the common acceptance, export lists rule p. 3: exclude)."""
import json, sys
raw, flt = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
basis = {x['path']: (x['disposition'], x['basis']) for x in flt['files']}
def corpus(p): return any(s.lower().split('.', 1)[0] in {'spec_verdicts', 'legacy_spec_verdicts'} or 'mutant' in s.lower() for s in p.split('/'))
def inputs(p):
    s = p.split('/'); return any(s[i] == 'acceptance' and s[i+1].isdigit() and s[i+2] == 'inputs' for i in range(len(s) - 3))
r = {'orig_rules_output_OK': raw['OK']}
r['bool_checks_all_true'] = all(v is True for k, v in raw.items() if isinstance(v, bool) and k != 'OK')
r['refs_ok'] = raw['JI_refs'] == ['refs/heads/judge-input']
r['lesson_registries_in_JI'] = all(raw['named_inputs_present'][f'Platform/{l}/forms/{f}'] for l in ('01-store','02-installer','03-worker') for f in ('targets.tsv','targets.routing.tsv'))
h = raw['forbidden_hits']
r['code_hits_all_acceptance_inputs'] = all(inputs(p) for p in h['code']); r['code_hits'] = h['code']
r['verdict_hits_none_corpus'] = not any(corpus(p) for p in h['verdict_or_mutant_path']); r['verdict_hits'] = h['verdict_or_mutant_path']
r['other_hits_empty'] = not any(v for k, v in h.items() if k not in ('code', 'verdict_or_mutant_path'))
miss = raw['routing_files_missing_in_JI']
cls = {'verdict_corpus': [p for p in miss if corpus(p)],
       'check_spec_schema_OBSH39_P01228': [p for p in miss if not corpus(p) and p.endswith('.schema.json') and basis[p][1].startswith(('OBSH.39', 'P01.228'))],
       'lesson_export_list': [p for p in miss if not corpus(p) and __import__('re').fullmatch(r'Platform/\d\d-[a-z0-9-]+/forms/export\.json', p)]}
r['routing_missing_classified'] = {k: len(v) for k, v in cls.items()}
r['routing_missing_all_filter_excluded_and_classified'] = all(basis[p][0] == 'exclude' for p in miss) and sum(map(len, cls.values())) == len(miss)
r['routing_missing_schema_paths'] = cls['check_spec_schema_OBSH39_P01228']
r['named_inputs_present'] = all(raw['named_inputs_present'].values())
r['objects_physical_eq_reachable'] = raw['objects_physical_eq_reachable'][2]
r['counts'] = raw['counts']
r['OK'] = all(r[k] for k in ('bool_checks_all_true', 'code_hits_all_acceptance_inputs', 'verdict_hits_none_corpus', 'other_hits_empty',
                             'routing_missing_all_filter_excluded_and_classified', 'named_inputs_present', 'objects_physical_eq_reachable', 'refs_ok', 'lesson_registries_in_JI'))
json.dump(r, sys.stdout, indent=1); print(); sys.exit(0 if r['OK'] else 1)
