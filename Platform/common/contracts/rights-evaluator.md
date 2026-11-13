# Rights evaluator

This English text is the source; the Russian translation `ru/contracts/rights-evaluator.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The evaluator computes the right of a role to perform one action on one key using the loaded rights file. The actions are `read`, `write` and `delete`; each action has its own list of patterns. An absent `delete` is an empty list: no deletes. The evaluator does not derive `delete` from `write`.

## Patterns

An exact pattern matches the key equal to it. A `*` as the last character makes the pattern a prefix; a `*` not last is a literal character. A `!` only as the first character makes the pattern a negation; a `!` not first is a literal character. The pattern after the leading `!` uses the same exact-or-prefix rule. A negation wins regardless of its place in the list.

The strings `""`, `"!"`, `"!*"`, `"p/!x"` and `"a*b"` are admissible patterns. `""` matches only the empty key; `"!"` negates the empty key; `"!*"` negates everything. A final wildcard after a literal star is still a prefix: `a**` matches keys beginning with `a*`.

## Evaluation

For `allowed(role, action, key)`, with `action` one of `read`, `write`, `delete`:

1. The role is absent from the file: deny.
2. Any negated pattern of that role for the action matches: deny.
3. Any positive pattern of that role for the action matches: allow.
4. Otherwise: deny.

The result is `allow` or `deny`. The store applies its identity checks, `never` rules and the exceptions for admin and internal roles in [P/01.2](../../01-store/spec/01.2-store.norms.md#n13-evaluator); they are outside the pattern evaluator.

## Consumers and vectors

The common package [`rights-evaluator`](../vectors/rights-evaluator/README.md) defines the command wire, rights-file fixture and the consumer's duties. The rights-file form and loading are [P/01.2 N1.2](../../01-store/spec/01.2-store.norms.md#n12-rights-file).
