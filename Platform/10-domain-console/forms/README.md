# P/10 input and refusal forms

This English text is the source; ru/forms/README.md is its Russian translation for people, not in the export (ADR-0121). These forms express the existing norms under ADR-0125 addendum (5).

## Inputs and constants

[daemon-flags.tsv](daemon-flags.tsv) projects 20 existing environment inputs. The common header is flag,type,default,default_text,required,commands,bad,norm. $NAME remains environment; commands=domainconsole denotes the process. The setting channel stays environment-only. The launcher applies file precedence and role/instance/box/server validation. Alias equality, path resolution, TLS kits, listener admission, ports and own-client name checks retain their complete imported contracts, including the distinction between an implicit wildcard and an explicit address.

TIMEZONE uses exactly the IANA-name spelling of the environment contract: empty or out of form refuses start with code 2, but there is no zone-database lookup. W2C_DEBUG_PERSON retains every identity/credential/loopback guard of the gate contract; it creates no forwarding credential. DOMAIN_CONSOLE_HOST/PORT is the main door; this form introduces no callback listener or callback port.

[runtime-constants.tsv](runtime-constants.tsv) has the common header name,value,unit,norm,meaning and projects four existing positive integer limits. DOMAIN_PAGE_MEMBERS is the existing 1000-member bound of the aggregate view and member-list pages; RELAY_MEMBERS_MAX is the 5000-name relay bound. LOST_AFTER is the imported 45-second silence threshold; ALARMS_WINDOW is the existing one-day default window, in seconds. They are not environment settings. Cursor contents, projections, complete/contested data, report clocks and witness calculations remain their source contracts.

## Refusal catalogue

[refusals.tsv](refusals.tsv) preserves all 16 original Н4 rows as 25 code projections. word/outcome/cause contain the original three cells byte for byte; diagnostic/caller are absent (-) for those source rows. chapter=10 and row preserve the published addresses; a compound code yields several projections with the same row. Rows 17–22 project existing manifest/rights/schema startup admission, TIMEZONE, implicit-wildcard/kit admission, alias conflicts, the prohibited callback and the trusted alarms input. They do not add HTTP doors or startup refusal conditions.

The header is chapter,row,name,surface,code,kind,fields,headers,log,norm,word,response_schema,cause,outcome,diagnostic,caller, with literal TAB separators. HTTP response_schema names an OpenAPI component; fields lists directly required/directly declared properties. A composed or referenced schema still applies in full even when fields is -. The added names GateDenied, ConsoleRefusal and DomainPassRefusal only reference existing published schemas. DomainPassRefusal includes the existing manifest-mapped ProblemRefusal of the second kind, so a catalogue row does not force error/detail on a code/message body. It does not rewrite a worker reply. The full pass contract also retains its independently specified deadline/status and dynamic headers.

The word cell is a source catalogue index, never a free choice of error for a condition. The transition-3 siblings/executors replies have surface=peer: they are passed as received from the domain writer and introduce no own HTTP failure. A TLS chain refused at the handshake has no HTTP status; row 1 retains this distinction. All other ordering, role/gate/body rules and exact conditional bodies remain in the preserved source cells and OpenAPI.

This slice contains no stages or new acceptance seams. Their authorship and the implementation acceptance remain separate.
