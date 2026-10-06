"""How a spec's file is read: YAML 1.2 core, a subset, one way everywhere the course loads a spec (ADR-0012, ADR-0019).

    load(path)            the file's mapping, or a ValueError naming the file, where (the path of keys) and the line
    loads(text, where)    the same of bytes, text or an open file in hand (a test's spec, a probe's)
"""
# ================================================================================================
# NOTES — what this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# A spec is read by two loaders, the course's (PyYAML) and the product's (its own parser in Go), and «one YAML» means
# both read the same file as the same spec (ADR-0019). PyYAML's `safe_load` is YAML 1.1 and forgiving where a spec may
# not be: a key said twice kept the last and threw the first away with the keys under it (a second `lease:` turned
# `off` into `forever`, a second `placement:` hid a typo — the fourteenth review, major 9); `On`/`Off`/`Yes`/`No` were
# booleans; `0x10`, `1_000`, `010` (octal) were numbers; an anchor, a merge key or a tag copied or retyped what the
# eye does not see. So the course reads a spec by THIS loader, and the rules are «Архитектор»'s (2026-10-06, the
# table `tests/testdata/spec_verdicts.tsv` the product holds byte for byte):
#
#   the text          UTF-8, no BOM, no NUL; indentation by spaces (a tab is refused by the scanner itself)
#   the document      one, and a mapping: a list, a scalar, an empty file or a second `---` is no spec
#   refused           an anchor (`&`), an alias (`*`), a merge key (`<<`), any tag (`!…`, `!!str`), a key said twice in
#                     one mapping (a flow `{a: 1, a: 2}` as well), a key that is a map or a list, nesting deeper than
#                     `MAX_DEPTH` — each named with the path of keys it stands under and its line
#   scalars           YAML 1.2 core, decimal only: `true`/`false` (`True`, `TRUE`) are booleans and nothing else —
#                     `On`, `off`, `yes`, `No` are words; `null`/`~`/nothing is null; an integer is decimal digits
#                     (`010` is ten; `0x10`, `0o7`, `1_000`, `1:30` are words) within ±(2^53 − 1), what a JSON reader
#                     holds exactly; a float is `1.5`, `1e308`, `.5`, `.inf`, `.nan`; a timestamp is a word
#
# Every refusal is a ValueError naming the file — PyYAML's own errors, a nesting past the stack, a malformed byte —
# never an AttributeError or a RecursionError out of a load (the review's minor 25).
#
# ## Module-level names
# - `MAX_DEPTH` — how deep a spec nests: a spec's deepest is a JSON Schema in a field (`requests.schema.properties.<f>.
#   anyOf[i].properties`, a dozen levels); 64 is past every one, and a file past it is no spec somebody wrote by hand.
# - `MAX_INT` — 2^53 − 1.
# - `SpecLoader` — PyYAML's `SafeLoader` with the resolver, the composer and the constructor above.
# - `load(path)`, `loads(data, where)`.
# ================================================================================================
from __future__ import annotations

import re

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

MAX_DEPTH = 64
MAX_INT = 2 ** 53 - 1

_TAG = "tag:yaml.org,2002:"


class SpecLoader(yaml.SafeLoader):
    """`SafeLoader` reading YAML 1.2 core, a subset: see the notes above."""

    yaml_implicit_resolvers: dict = {}           # nothing of YAML 1.1's: the five below, and only they

    def __init__(self, stream, where: str = "<spec>"):
        super().__init__(stream)
        self.name = where                         # what every mark (and so every PyYAML error) names
        self.where = where
        self._path: list[str] = []

    # -- composing: the path of every node, and what a spec may not say -----------------------------
    def _refuse(self, what: str, mark) -> None:
        at = ".".join(self._path) or "the top"
        raise ValueError(f"{self.where}: {at} (line {mark.line + 1}): {what} — a spec is YAML 1.2 core without anchors, "
                         f"aliases, tags or duplicate keys (ADR-0012)")

    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(parent, MappingNode):
            self._path.append(str(index.value) if isinstance(index, ScalarNode) else "<key>" if index is None else "?")
        elif isinstance(parent, SequenceNode):
            self._path.append(f"[{index}]")
        try:
            if isinstance(event, yaml.AliasEvent):
                self._refuse(f"an alias (*{event.anchor})", event.start_mark)
            if event.anchor is not None:
                self._refuse(f"an anchor (&{event.anchor})", event.start_mark)
            if getattr(event, "tag", None) is not None:
                self._refuse(f"a tag ({event.tag})", event.start_mark)
            if len(self._path) > MAX_DEPTH:
                self._refuse(f"nested deeper than {MAX_DEPTH} levels", event.start_mark)
            if index is None and isinstance(parent, MappingNode) and isinstance(event, yaml.ScalarEvent) \
                    and event.value == "<<" and event.implicit[0]:
                self._refuse("a merge key (<<)", event.start_mark)
            node = super().compose_node(parent, index)
            node.spec_path = ".".join(self._path)
            return node
        finally:
            if parent is not None:
                self._path.pop()

    # -- constructing: a key once per mapping; integers a JSON reader holds -------------------------
    def construct_mapping(self, node, deep=False):
        if not isinstance(node, MappingNode):
            raise ValueError(f"{self.where}: line {node.start_mark.line + 1}: a mapping was expected")
        out: dict = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            at = getattr(node, "spec_path", "") or "the top"
            if isinstance(key, (dict, list)):
                raise ValueError(f"{self.where}: {at} (line {key_node.start_mark.line + 1}): a key is a word, not "
                                 f"a {type(key).__name__}")
            if key in out:
                raise ValueError(f"{self.where}: {at} (line {key_node.start_mark.line + 1}): the key {key!r} is said "
                                 f"twice — YAML would keep the last and drop the first with all under it; a spec says "
                                 f"each key once (ADR-0012)")
            out[key] = self.construct_object(value_node, deep=deep)
        return out

    def construct_spec_int(self, node):
        value = self.construct_scalar(node)
        n = int(value, 10)                        # decimal, whatever its leading zeros: `010` is ten (YAML 1.2)
        if abs(n) > MAX_INT:
            raise ValueError(f"{self.where}: {getattr(node, 'spec_path', '')} (line {node.start_mark.line + 1}): "
                             f"{value} is past ±(2^53 − 1), the integers a JSON reader holds exactly")
        return n


# The resolver of YAML 1.2's core schema, decimal integers only (the order matters: the first that matches wins, and an
# integer is a float's text too).
SpecLoader.add_implicit_resolver(_TAG + "bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
SpecLoader.add_implicit_resolver(_TAG + "int", re.compile(r"^[-+]?[0-9]+$"), list("-+0123456789"))
SpecLoader.add_implicit_resolver(
    _TAG + "float",
    re.compile(r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+.0123456789"))
SpecLoader.add_implicit_resolver(_TAG + "null", re.compile(r"^(?:~|null|Null|NULL|)$"), ["~", "n", "N", ""])
SpecLoader.add_constructor(_TAG + "int", SpecLoader.construct_spec_int)
SpecLoader.add_constructor(_TAG + "bool", lambda self, node: self.construct_scalar(node) in ("true", "True", "TRUE"))


def loads(data, where: str = "<spec>") -> dict:
    """The mapping a spec's text says, or a ValueError naming `where` (an open file: its name)."""
    if hasattr(data, "read"):
        where = getattr(data, "name", where) if where == "<spec>" else where
        data = data.read()
    if isinstance(data, (bytes, bytearray)):
        if data.startswith(b"\xef\xbb\xbf"):
            raise ValueError(f"{where}: begins with a byte order mark — a spec is UTF-8 without one")
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"{where}: byte {e.start} is not UTF-8 — a spec is UTF-8 text") from None
    else:
        text = str(data)
    if text.startswith("﻿"):
        raise ValueError(f"{where}: begins with a byte order mark — a spec is UTF-8 without one")
    if "\x00" in text:
        raise ValueError(f"{where}: holds a NUL at character {text.index(chr(0))} — a spec is text")
    try:
        loader = SpecLoader(text, where)
        try:
            got = loader.get_single_data()
        finally:
            loader.dispose()
    except ValueError:
        raise
    except yaml.YAMLError as e:
        raise ValueError(f"{where}: not a spec's YAML — {e}") from None
    except RecursionError:
        raise ValueError(f"{where}: nested past what is read") from None
    if not isinstance(got, dict):
        raise ValueError(f"{where}: a spec is a mapping of keys, not {'nothing' if got is None else type(got).__name__}")
    return got


def load(path: str) -> dict:
    """The mapping of the spec file `path`, or a ValueError naming it."""
    with open(path, "rb") as f:                   # a file that is not there is not a spec refused: OSError, as it was
        data = f.read()
    return loads(data, path)
