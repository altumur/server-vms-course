# `peer` vectors

This English text is the source; the Russian translation `ru/vectors/peer/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The [`peer` contract](../../contracts/peer.md) defines the function by which a client accepts the server of an `https://` door: the anchor fingerprint, the signature path, certificate validity, the leaf role and the host name. The owner is P/09.

## Run

The function input is a JSON object `{chain: [<PEM>…], fingerprints: [<hex>…], role, host, now}`. `chain` is the certificate chain received from the server, in server order, leaf first. `fingerprints` contains trusted CA fingerprints: sha256 hex of the CA certificate's DER. `role` is the expected leaf role; `host` is the destination name; `now` supplies the time for certificate validity checks, instead of the process clock.

The adapter validates the input form before the call. The trusted input fields `fingerprints`, `role`, `host` and `now` are required; missing required fields give native exit code 2, and stdout is not compared. This follows the trusted-input rule in [domain vector commands](../../acceptance/domain-stand.md#domain-vector-commands).

The received `chain` is evaluated by the function, rather than rejected as a trusted-input form error. The contract's order applies: the host check comes first; then a chain that is not a non-empty list of readable PEM certificates gives `bad_chain`, with native exit code 0. Each element must be exactly one CERTIFICATE block with strict base64 and fully parsed DER. An empty `fingerprints` list is a function input; the contract checks it after the chain form.

The native output at exit code 0 is a JSON object `{"result":"ok"}` or `{"result":"refused","reason":<word>}`. The refusal vocabulary is `ip_address`, `bad_chain`, `foreign_ca`, `expired`, `no_role`, `wrong_role`, `wrong_name`. Native form validation checks the actual JSON object returned by the implementation. The judge compares a subset of its fields; the expected answer is not an input to the function.

## Who performs

The clients of another cluster execute the function: the agent and relay (`09-agent`), the cluster console (`06-console`) and process `domain` (`08-domain`). The domain console (`10-domain-console`), as a server of class `role`, performs the leaf-role checks, steps 6–7, over the client's leaf. A role executes the function checks called by its norm.

## Vector wire

The public `table` selector is `cases.tsv` for the peer check (judge-only: `cases.tsv`).

The `common/peer` rows of [the single form](../wire.tsv) (judge-only: `wire.tsv`) bind headers, selected inputs, native framing and comparison; [wire grammar](../wire.md) defines the frame. Layout is an excluded function declaration, never proof that its separate acceptance ran. The contract governs a discrepancy; «Specification» corrects the vector.

Concrete certificates, case inputs, answer associations and coverage are in [case data and coverage](README.cases.md) (judge-only: `README.cases.md`).
