# P/09 input and refusal forms

This English text is the source; ru/forms/README.md is its Russian translation for people, not in the export (ADR-0121). The forms express existing norms under ADR-0125 addendum (5).

## Inputs and constants

[daemon-flags.tsv](daemon-flags.tsv) projects 34 existing process environment inputs with the common header. $NAME remains environment, commands=domainagent denotes the process. No public command-line flags or join argv are introduced: the command join keeps its implementation-chosen spelling under P/09.1 Implementation decides. The launcher still applies environment-file precedence, role, instance/box/server, aliases, paths and kit rules. The inherited LISTEN_PID/FDS/FDNAMES values keep the complete activation preconditions and descriptor/path checks of the local-token-door contract. Raw string declarations never waive those contracts.

Neither DOMAIN_URL nor RELAY_URL set and nonempty is the existing configuration refusal before the turn or key birth. A https relay address requires RELAY_MEMBER. RELAY accepts absent/empty or exactly 1. Contextual TLS/listener validation remains in P/02.4: an operation-time unknown row or key is not a new startup refusal. DOMAIN_FOLDERS=chains selects chains; every other/absent value selects all, so its type is string, not a new closed enum.

[runtime-constants.tsv](runtime-constants.tsv) declares 13 positive integer literals with the common header name,value,unit,norm,meaning. Units are s, count and bytes. These are not environment settings. BODY_LIMIT is the imported exact 16 MiB limit; formulas such as camera scheduling, relay age, kept_at rounding, and imported turn/token deadlines keep their own contracts.

## Refusal catalogue

[refusals.tsv](refusals.tsv) preserves all 22 original Н4 rows as 24 projections, retaining cause/outcome/diagnostic/caller byte for byte. The two compound relay rows each have two code projections with the same source row number. Ten imported local-door/start conditions and two explicit relay-start conditions give 36 projections in total. The original chapter/row addresses remain.

HTTP response_schema names an existing OpenAPI component. Fields name direct properties, including all directly required ones; the complete source cells and OpenAPI retain contextual requirements and exact error/reason words. The local door passes holder refusals as received except its explicitly normed mappings. A peer reply, a stored edit outcome, a journal or alarm is not a new HTTP failure of the agent. A code not fixed by its source is -, including the implementation-chosen join refusal and socket-start refusal; no new exit value is inferred. Relay refusals retain the Н2 order and absence of Retry-After.

