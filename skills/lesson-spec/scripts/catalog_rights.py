"""Catalog ⊆ rights (ADR-0083 доп. (6)): every operation of every catalog participant is allowed by a rights file
derived from the subsystem manifests (P/02.5 Н1.4), evaluated by P/01.2 Н1.2. Store rows only: objects and files are not under the
store's rights. The rights file comes from any implementation's rights command; this script does not derive rights.

    catalog_rights.py --catalog Platform/common/data/catalog.tsv --rights rights.json --manifest testsub.subsystem.yaml ...
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from check_spec import CATALOG_FIELDS, parse_ops  # noqa: E402

WRITE_OPS = {"create", "put", "cas", "guard", "mark", "append"}
STORE_ROLE = re.compile(r"console|resource|domainagent|domainconsole|domain|<s>(?:controller|worker|domain)")


def matches(pattern, key):
    """М10/6 Н1.2 pattern: `*` last — prefix; any other `*` and a non-leading `!` are literal."""
    return key.startswith(pattern[:-1]) if pattern.endswith("*") else key == pattern


def allowed(rights, role, action, key):
    """М10/6 Н1.3 `allowed`; `never` and admin are out of scope (admin is not a catalog store participant)."""
    patterns = rights.get("roles", {}).get(role, {}).get(action)
    if patterns is None:
        return False
    if any(p.startswith("!") and matches(p[1:], key) for p in patterns):
        return False
    return any(not p.startswith("!") and matches(p, key) for p in patterns)


def declared(manifest, dotted):
    node = manifest
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def instance(key, sub):
    """A concrete key for one manifest, or None when a <manifest:…> variable needs the manifest's own names."""
    if "<manifest:" in key:
        return None
    key = re.sub(r"<(?:sub|s)>", sub, key)
    key = re.sub(r"<[^<>]+>", "x1", key)
    return key[:-1] + "x1" if key.endswith("/*") else key


def roles_of(field):
    """`role(cond),role` → [(role, conditional)]."""
    return [(r, bool(c)) for r, c in re.findall(r"(<s>[a-z]+|[a-z][a-z-]*)(\([^()]*\))?", field)]


def ops_roles(text):
    """Catalog `ops` → [(role, action, conditional)]; create/put/cas/guard/mark/append need write, delete — delete."""
    out = []
    for part in text.split("; "):
        op, _, rest = part.partition("=")
        for role, conditional in roles_of(rest):
            out.append((role, "delete" if op == "delete" else "write", conditional))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--rights", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, action="append", required=True,
                        help="subsystem manifest file; repeat for each")
    args = parser.parse_args()
    rights = json.loads(args.rights.read_text(encoding="utf-8"))
    manifests = {}
    for path in args.manifest:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifests[manifest["name"]] = manifest
    rows = [line.split("\t") for line in args.catalog.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")]
    header, rows = rows[0], rows[1:]
    assert header == CATALOG_FIELDS, header
    denied, conditional_denied, absent, checked, skipped = [], [], set(), 0, 0
    for cols in rows:
        row = dict(zip(CATALOG_FIELDS, cols))
        if row["kind"] != "row":
            continue
        parse_ops(row["ops"])  # grammar as check_spec
        wanted = ops_roles(row["ops"])
        if row["readers"] != "*":
            wanted += [(role, "read", conditional) for role, conditional in roles_of(row["readers"])]
        for sub, manifest in manifests.items():
            if row["when"] != "-" and not declared(manifest, row["when"]):
                continue
            key = instance(row["key"], sub)
            if key is None:
                skipped += 1
                continue
            for role, action, conditional in wanted:
                if not STORE_ROLE.fullmatch(role):
                    continue
                concrete = role.replace("<s>", sub)
                if concrete not in rights.get("roles", {}):
                    absent.add(concrete)
                    continue
                checked += 1
                if not allowed(rights, concrete, action, key):
                    line = f"{row['key']} ({row['norm']}): {concrete} {action} {key}"
                    (conditional_denied if conditional else denied).append(line)
    for line in denied:
        print("DENIED", line)
    for line in conditional_denied:
        print("CONDITIONAL", line, "— the participant's condition may name another manifest; check by reading")
    if absent:
        print("ABSENT roles not derived for these manifests:", ", ".join(sorted(absent)))
    print(f"checked={checked} denied={len(denied)} conditional={len(conditional_denied)} "
          f"skipped_manifest_variables={skipped}")
    return int(bool(denied))


if __name__ == "__main__":
    sys.exit(main())
