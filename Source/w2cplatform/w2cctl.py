"""python3 -m w2cplatform.w2cctl — the platform's operator tool (the product's `w2cctl`): secrets at rest.

    w2cctl secrets new <path>              a key ring with one key (`sealing.new_key_file`): 0640, never inside a store
    w2cctl secrets status [<prefix> ...]   every `*_secret` of the rows under the prefixes — at the top of a row, or of a
                                           JSON object that is one of its values — counted: in the clear, sealed under
                                           the ring's current key, under an older one; exit 1 when one is in the clear
                                           and there is a ring to seal it with
    w2cctl secrets seal [<prefix> ...]     seal what is in the clear, re-seal what an older key sealed, under the current
                                           key, by CAS, the row's meaning unchanged

The prefixes are, by default, the domain's and the people's — `domain/`, `identity/` (DOMAIN-PLATFORM.md: the signer's
keys, the people's hashes, the emergency hashes and the books' tokens lay there in the clear, and nothing sealed or even
counted them) — and the unit rows of every loaded spec (`SPEC_DIR`), whose secrets the console seals already. The store
is `PLATFORM_STORE`, the ring `SECRETS_KEY`. Rotation is a new line on top of the ring, then `seal`.
"""
from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger("w2cplatform.w2cctl")

DOMAIN_PREFIXES = ("domain/", "identity/")


def prefixes(env: dict | None = None) -> list[str]:
    from w2cplatform import catalog
    out = list(DOMAIN_PREFIXES)
    try:
        out += [f"{s.name}/{s.rows}/" for s in catalog.specs(env)]
    except ValueError:
        pass                                              # no spec directory: the domain's and the people's only
    return out


def status(vars_, sealer, wanted) -> dict:
    """{prefix: {"clear": n, "current": n, "older": n}} — every secret of every row under each prefix."""
    from w2cplatform.domain.carry import _walk
    from w2cplatform.sealing import is_sealed, kid_of
    out = {}
    for prefix in wanted:
        n = {"clear": 0, "current": 0, "older": 0}

        def count(field, value, ctx):
            if not is_sealed(value):
                n["clear"] += 1
            elif sealer is not None and kid_of(value) == sealer.current:
                n["current"] += 1
            else:
                n["older"] += 1
            return value
        for key in vars_.list(prefix):
            items, _ = vars_.get(key)
            if items:
                _walk(items, count, key)
        out[prefix] = n
    return out


def seal(vars_, sealer, wanted) -> int:
    """Seal every secret in the clear and re-seal what an older key sealed; returns how many rows were written."""
    from w2cplatform.domain.carry import _walk
    from w2cplatform.sealing import Sealed, is_sealed, kid_of
    from w2cplatform.variables import Conflict
    if sealer is None:
        return 0
    written = 0
    for prefix in wanted:
        for key in vars_.list(prefix):
            items, idx = vars_.get(key)
            if not items:
                continue
            changed = []

            def one(field, value, ctx):
                if is_sealed(value) and kid_of(value) == sealer.current and sealer.bound(field, value, ctx):
                    return value
                try:
                    clear = sealer.open(field, value, ctx, fallback=True) if is_sealed(value) else value
                except Sealed as e:
                    log.warning("%s: a sealed value this ring cannot open is left as it is (%s)", ctx, e)
                    return value
                changed.append(field)
                return sealer.seal(field, clear, ctx)
            new = _walk(items, one, key)
            if not changed:
                continue
            try:
                vars_.put(key, new, cas=idx)
                written += 1
            except Conflict:
                log.info("%s changed while being sealed: its own write sealed it", key)
    return written


def main(argv: list[str], env: dict | None = None) -> int:
    from w2cplatform.sealing import Sealer, new_key_file, platform_stores
    from w2cplatform.variables import open_vars
    env = os.environ if env is None else env
    if argv[:2] == ["secrets", "new"] and len(argv) == 3:
        new_key_file(argv[2], store=platform_stores(env))
        print(f"a key ring with one key: {argv[2]}")
        return 0
    if argv[:1] != ["secrets"] or len(argv) < 2 or argv[1] not in ("status", "seal"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    vars_ = open_vars(env["PLATFORM_STORE"])
    sealer = Sealer.from_env(env)
    wanted = argv[2:] or prefixes(env)
    if argv[1] == "seal":
        print(f"{seal(vars_, sealer, wanted)} row(s) sealed" if sealer else "no SECRETS_KEY: nothing to seal with")
        return 0 if sealer else 1
    got = status(vars_, sealer, wanted)
    for prefix, n in got.items():
        print(f"{prefix:28s} clear {n['clear']:5d}   current {n['current']:5d}   older {n['older']:5d}")
    return 1 if sealer is not None and any(n["clear"] for n in got.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
