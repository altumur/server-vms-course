# The address contract: the login and the password in a url value

This English text is the source; the Russian translation `ru/contracts/url-credentials.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies
in the chapters; guess of stage C W03-E07, the Architect's decision of 2026-10-23). The owner is chapter
[P/06.2](../../06-console/spec/06.2-console.norms.md) of the console (N1.1 `url_field`, N1.1a, N3 «read_address»). Participants:
[the common row check](row-check.md) — the door of units and tables of the console ([P/06.1](../../06-console/spec/06.1-console.norms.md))
and the customer library ([P/03.6](../../03-worker/spec/03.6-worker.norms.md) N1.6); the display of an address in answers (P/06.2 N1.4) and
[the log mask](log-mask.md) of all processes (free text as a whole is that contract; C06-LOG-MASK-33-01); the declarations `credentials` and `secret_in` of a field `type: url` — the loader
[P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.2a; the refusal `bad_url` of a group source — P/04 N1.3 `group_by`.
Moved from P/06.2 N1.1 (`url_field` without `bound_to`, `common_words`, `normalisation`), N1.1a and N3 «read_address» without
a change of behaviour; the address rules A1–A15 are kept.

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## The field rule and the common vocabulary

```yaml
url_field:                                   # at a field with type: url (the form — Platform/02-installer/spec/02.1-installer.schema.json, P/02.1 N1.2a)
  credentials: {login: <a row field, not url and not a secret>, secret: <a *_secret field>}
  secret_in:                                 # a list, each element of one of three kinds; read by A1–A15 below
    - {param: [<name>…], login: [<name>…]}     # the name pattern — A5; login ⊆ param: the names from login are a login
                                             # (a refusal, without a mask), the others are a secret
    - {regex: '…(?P<login>…)(?P<secret>…)(?P<name>…)', in: path | query | authority | fragment | [list],
       schemes: [<schema>…], decoded: true | false}      # RE2; the groups are only login, secret, name, at least one of
                                                         # the first two; decoded is true by default (A13)
    - {nested: [<name>…]}                     # the value of the pair is a nested address: the united rule of the catalogue
                                             # together with the field rule, not deeper than 3 (A8; ADR-0053, addendum of 2026-10-06)
common_words: [password, passwd, pass, pwd, secret, token, key, credential, credentials, psk, privkey, apikey, =auth, =pin]
normalisation: A4 — only the name of a pair, for recognition; the value of a secret, the envelope and AAD are not transformed;
               the mask replaces the value in the written text
```

The display mask is `***` (P/06.2 N1.1 `mask`).

## Schemes (`schemes`)

The rule of a field `type: url` names the admissible schemes: `schemes` — a scheme name `[a-z][a-z0-9+.-]*` → `{host?, fragment?,
none?}` (the declaration in the manifest — [P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.3 `<schemes>`; the meaning — here;
guess of stage C URLC-HOST-01, the Architect's decision of 2026-10-23). A scheme of the value not from `schemes` — the refusal `bad_url`.

```yaml
node:      the authority node — as written, together with `userinfo@` and the port; the host in it — in one spelling (lower case, without
           the final root dot); none compares it byte for byte: a node with a port or userinfo is not none (`cfw://user:pw@local` —
           host local, group local, vectors group-of; the Architect's clarification of 2026-10-23; `driverpack://FILE/x` — none, `driverpack://file:1/x`
           — not, as in the vectors group-of; guess of stage C URLC-SCHEMES-01, revised, the Architect's decision of 2026-10-23); an IP-literal — with brackets:
           none ["[::1]"] matches `cfw://[::1]/…`, ["::1"] does not, `cfw://[::1]:99999` — a node with a port, not none; the IP literal
           of a node is not normalised, except for case: the node of `cfw://[::ffff:10.0.0.5]/x` is `[::ffff:10.0.0.5]` (guess of stage C
           GROUP-NODE-01, the Architect's decision of 2026-10-23)
           (URLC-SCHEMES-03; there is no vector — the manifests of the vectors have no none with an IP-literal; by reading)
host:      authority (the default) — the host is the host of authority (after the last «@», without the port); path — the host is the first segment
           of the path, the authority node is the hub
           (`mirror://<hub>/<host>/…`); the first segment at host: path is `host[:port]` by the rule of authority (the port — port
           below): `mirror://hub/h:99999/x` — accepted, `mirror://hub/h:abc/x` — bad_url; an empty first segment — no host:
           `mirror://hub/` — bad_url
fragment:  none — `#` is an ordinary character, not the start of a fragment (A2); without the key — `#` starts a fragment
none:      [<value>…] — the exact values of the authority node that mean «no host» (`mirror://local/…` — its own copy, whatever
           the path); the check «no host» is not applied to such a link, group_by P/04 N1.3 does not take it into a group
path:      the path is required only at host: path, including with a node from none: `mirror://local`, `driverpack://file` without
           a path — bad_url; `mirror://local/x` and `mirror://local/` at none: [local] — accepted; `mirror://local:80/` — a node with
           a port is not none, the first segment is empty — no host, bad_url; at host: authority the path is not required, also with a node from
           none: `cfw://local` at none: [local] — accepted (no host); `cfw://local:80` — a node with a port is not none: host local,
           accepted
zone:      an IP literal with a zone of RFC 6874 (`[fe80::1%25eth0]`) — a readable host, not a character outside the grammar of A2 (guess of stage C GO-URL-01, the Architect's decision of 2026-10-23;
           vectors group-of); in the one spelling, lower case applies only to the address of the IP literal, the zone stays as written, without a change of
           case and without decoding %XX: none ["[fe80::1%25Eth0]"] matches `cfw://[FE80::1%25Eth0]/x`, not `…%25eth0`;
           an empty zone (`%25]`) and `%` without `25` (`[fe80::1%eth0]`) — bad_url; `%25Eth%30` — accepted, the zone is not changed (guess
           of stage C URLC-ZONE-02, the Architect's decision of 2026-10-23)
empty:     at host: path an empty authority node is admissible — the host is the first segment of the path (`mirror:///10.0.0.5/y` — host 10.0.0.5); at host: authority
           an empty node — no host, bad_url (`rtsp:///s`; GO-URL-01); at host: path a non-empty node without a host (`mirror://:80/10.0.0.5/y`,
           `mirror://u@/10.0.0.5/y`) — bad_url; an empty node is not compared with none — none [""] does not make it «no host»
           (guess of stage C URLC-GO-EDGE-01, the Architect's decision of 2026-10-23)
port:      *DIGIT by RFC 3986, without a limit of the TCP port number (`h:99999` — accepted); a non-numeric port — bad_url (a password in the place
           of the port — A12), the refusal does not repeat the value
```

## The address: where the login and the password are in it

The value of a field `type: url` is read by the rule of this field (`credentials`, `secret_in`) and by the common vocabulary
`common_words`. A nested address is also read by the united rule of the catalogue (ADR-0053, addendum of 2026-10-06).
A finding is a password or a login together with the stretch of the value where it is written. The display (A14) and the refusal (A15) are built
from all findings of the value.

**A1. The address and the head.** A scheme is a letter, then letters, digits, `+`, `.`, `-`, and right after it `://`. The case of a scheme
does not matter: `DriverPack://` and `driverpack://` are one scheme. The outer address starts at the first `://` of the value.
The head is the text before the first `://`; in a value without `://` the head is the whole value. A value without `://` is read
as text. In it are read the head (A11b), an address escaped as a whole (A9), and pairs, as in the log mask: a name is
letters, digits, `_ . - %` and non-ASCII characters before `=`; a value runs up to `&`, `;`, `,` or a space (by A5 and A7).
The reason: by RFC 3986 such a value is not an address, but whoever opens it will read pairs and `@` in it.

**A2. The parts of an address** (`regex.in` names them):

| part | from | to |
|---|---|---|
| authority | `://` | the first `/`, `?` or `#` |
| path | the end of authority | the first `?` or `#` |
| query | `?` | `#` |
| fragment | `#` | the end of the address |

In free text (a value without `://` by A1, a log line — [the log mask contract](log-mask.md)) an address ends at a space, a quote, `\`, `<` or `>`.
A value of a field `type: url` with `://` is one address as a whole: these characters do not cut it. A character that the grammar of RFC 3986
admits nowhere — a space and control characters, `"`, `<`, `>`, `\`, `^`, `` ` ``, `{`, `|`, `}` — makes the url
unparsable: the refusal `bad_url` before storing (A15). Non-ASCII characters are admissible: A4 reads them. `'` is a character of the grammar
(sub-delims): in `https://hub.ex'ample/x?token=…` the address does not end at `'`, and `token` in it is a password (reconciliation of python and go M10/6–11, S4).
For a scheme with `fragment: none` (P/02.1 N1.2a `schemes`) the character `#` is an ordinary character, not the start of a fragment.

**A3. Pairs.** A pair is `name=value` inside a part of the value. The name is the text of the part before its first `=`,
the value is the rest of the part.

| where | how it is cut into parts |
|---|---|
| from the first `://` to the first `?` after it (authority and path) | into segments by `/`, each segment — by `&`, `;`, `#` |
| from this `?` to the end of the value | by `&` and `;`; `#` does not cut a value: in `?pwd=ab#cd` the value is `ab#cd`; the fragment after the first `#` is read once more by its own parts by `&` and `;`: in `?a=1#pwd=…` there is a pair `pwd` |

Pairs in authority are read too: `driverpack://acme;pwd=…/…`, `azure://…;AccountKey=…`. A segment without `=` is
not a pair: `/key/live`, `/pass/stream`, `/pw/1` are routes. `_` does not separate pairs: `/user=admin_password=…` is
one pair `user` with the value `admin_password=…`. Chains through `_` are read only by the `regex` of the manifest (A13).

**A4. The name of a pair** is read the way its recipient will read it:

1. decode `%XX` to a fixed point (`p%2577d` → `p%77d` → `pwd`); the bytes are read as UTF-8; an invalid
   UTF-8 sequence after decoding is read with U+FFFD (the display positions are by the original bytes of the written
   text); a `%` without two hexadecimal characters after it is not decoded, it stays a character and gives no refusal on reading
   (the list of characters of an unparsable url — A2 — is closed; guess of stage C URLC-UTF8-01, the Architect's decision of 2026-10-23);
2. apply NFKC (`ｐｗｄ`, `paſſword`, `𝐩𝐚𝐬𝐬𝐰𝐨𝐫𝐝`, `ⓟⓦⓓ`, `ᵖʷᵈ` → Latin; `proﬁle` → `profile`); NFKC and the lower case
   of step 5 are by the tables of Unicode 15.0.0 (UAX #15, UnicodeData), a character not assigned in this version stays as it is —
   all implementations get one name (log of cammeta-go, lesson 7 № 1);
3. remove the invisible characters U+00AD, U+034F, U+180E, U+200B–U+200F, U+2060–U+2064, U+FEFF;
4. keep the part after the last `.` (`dev.adminPassword` → `adminPassword`);
5. **the whole name** is the result of step 4 in lower case without `_`, `-`, `+` and spaces, digits stay
   (`pass_word` → `password`, `user_name` → `username`, `user_id` → `userid`);
6. **the words**: cut the result of step 4 by `_`, `-`, `+`, a space and by a change of case. A boundary of a change of
   case stands before a capital after a lowercase letter or a digit, and also before the last capital of a run if
   a lowercase letter follows it: `HTTPPort` → `HTTP`, `Port`. Bring each word to lower case and drop the
   trailing digits; drop a word of digits only (`apiKey2`, `api_key_2` → `api`, `key`). **The head** is
   the last word.

**A5. Patterns and the kind of a name.**

| pattern | matches when | matches (table) | does not match |
|---|---|---|---|
| `word` | the whole name equals the word or the head equals the word | `pass_word`, `hot_key`, `bucket_token`, `apiKey2`, `X-Amz-Credential` | `token_bucket`, `hotkey`, `monkey`, `passkey`, `rootpass`, `rtmpstreamkey` |
| `=word` | the whole name equals the word | `auth`, `pin`, `accessKeyId` (`=accesskeyid`) | `rtsp_auth`, `enable_auth`, `x-auth`, `gpio_pin`, `ping` |
| `word*` | some word starts with the word | `pwd_md5`, `passwordHash` | — |
| `*word` | the head ends with the word | `sessiontoken`, `adminPassword`, `userpwd` | `token_bucket` |

A secret — the name matched a pattern of the common vocabulary or a pattern of `param` of the field that is not in `login`.
A login — the name is not a secret and matched a pattern of `login`. Otherwise the pair carries nothing. A secret is checked before
a login: `accessKeyId` is a login, because its head is `id`, not `key`. Why the head and not any word:
`token_bucket` is a bucket, not a token.

**A6. A secret pair and a login pair.** The value of a secret pair is a password, it is masked to the end of the value: `<`, `>`, `\`
and a quote inside the value do not cut it (`pwd=Hun<ter2` → `pwd=***`, not `pwd=***<ter2`) (reconciliation of python and go M10/6–11, S4).
A secret pair with an empty value also gives a refusal, the display stays empty. The value of a login pair is a login, it is shown as written.
The value of a secret ends where its part ends. There is one exception. If `/` stands right after the value,
and further up to the nearest `?`, `#` or the end of the value there is `;` or `&`, the value stretches to this `;` or `&`:
`AccountKey=…/a+b==;EndpointSuffix=…` → `AccountKey=***;EndpointSuffix=…`. Otherwise `/` cuts the value:
`pwd=…/ch/1` → `pwd=***/ch/1`. The reason: a key in base64 contains `/`, and a path after a password does not.

**A7. Hidden by escaping.** The value of a pair with `%` is decoded to a fixed point:
- (a) if it contains `://`, it is a nested address (A8);
- (b) otherwise it is cut into parts by `&` and `;`, and a part with `=` is read as a pair by A5. A secret is found —
  the pair carries a password, its value is masked as a whole (`?user=admin%26pwd%3D…` → `?user=***`). A login is
  found — the pair carries a login.

The name of a pair with `%` which, decoded to a fixed point, contains `=`, `&` or `;` (`?pass%3D…=1`),
is joined in decoded form with `=` and the value of its own pair; the result is cut and read as in (b).
The name is masked together with the value. The reason: the recipient will decode the value and see these pairs.

**A8. A nested address.**
- **Where.** (1) The value of a pair, if the whole name of the pair (A4) is named in `nested` and the decoded value
  contains `://`. Inside a nested address the `nested` of any url field of the catalogue applies. (2) A value by A7(a).
  (3) A segment of authority or path with `%` which, decoded, contains `://` — the whole segment.
  (4) A segment with `%` which, decoded, ends in `:`, if `//` is written after it
  (`/x%3A//admin%3A…%40h/s`) — the path from this segment to `?`.
- **The address.** A nested address is the decoded text, starting from the scheme right before the first `://`. What stands
  before the scheme (`ffmpeg:`, `x;src=`) is dropped.
- **The rule.** A nested address is read by the united rule of the catalogue: the common vocabulary, and also `param`, `login`,
  `regex` and `nested` of all url fields of the loaded manifests — together with the field rule. The own pairs of the outer
  address are read only by the field rule. Therefore at a field whose rule does not name `session`, the pair `?session=abc`
  is accepted, while `session` inside a nested address is a secret if the rule of another url field of the catalogue names it
  (in the vectors [`secret-in`](../vectors/secret-in/README.md) — the fields `rec.volumes.url` and `cam.source` from the file
  [`fields.yaml`](../vectors/secret-in/fields.yaml) of the vectors).
- **Depth.** The outer address is level 0, levels 1–3 are read. An address of level 4 is not read and is counted as
  a password: `?src=http://a/x?src=http://b/y?src=http://c/z?src=http://d/w` → `?src=***`. The reason: about what is not
  read it is unknown that it is clean.
- **Kind.** The whole stretch of a nested address gets the strongest kind found inside; a password is stronger than
  a login.

**A9. An address escaped as a whole.** A value without `://` with `%` which, decoded, contains an address
is read as a nested address of level 1. A password in it masks the whole value. `%40` is not `@`: the value
`/mnt/a%40b` is accepted.

**A10. userinfo.** At each `://` of the value `://<login>:<password>@` is sought.
- The login is characters other than `/`, `@`, `:`, `?`, `#` and a space; the login can be empty (`rtsp://:pw@h`).
- The password stretches to the last `@` of the same word without spaces. `/`, `?`, `#`, `@`, `=`, `+` inside are part
  of the password: `admin:pa/ss?x@h` → `admin:***@h`, `admin:p@pw@h` → `admin:***@h`.
- The password can start with one `/` (a key of an object store: `acc:/K1SZ…==@`), but not with `//`:
  in `s3://https://KEY:SEC@h` the userinfo belongs to the inner address.
- Not userinfo: the password starts with digits up to `/`, `?` or `#`, and further up to `@` stands `=`, `&`, `;` or `://`.
  This is a port and a parameter: `h:8091/x?mail=a@b`.
- An empty password (`admin:@h`) is a password too. The login is shown.

**A11. `@`.**
- **(a) After the first `://`** — in the path, the query and the fragment — each `@` carries a login before it. There is a
  password if in the text before `@`, back to the nearest `/`, `?`, `&`, `;`, `=` or to `://`, there is `:`. Then the password is
  from the first such `:` to `@`: `rtsp://10.0.0.5/admin:x@y` → `admin:***@y`. In
  `driverpack://acme/10.0.0.5:8080/ch/1?mail=a@b` there is only a login: the colon of the port stands before `/` and does not count.
- **(b) In the head** each `@` carries a login. The password is from the last `:` before this `@` to the `@` itself,
  with `/` and other characters: `AKIA:pw@s3…` → `AKIA:***@s3…`, `s3:AKIA:pw/a+b@…` → `s3:AKIA:***@…`,
  `AKIA:pw@https://…` → `AKIA:***@https://…`. Without `:` there is only a login: `/mnt/a@b`, `/mnt/a@https://h/x`.
  An `@` that the value needs is written `%40`. Rule (b) reads only a field value, not free text:
  in text `@` often means mail.

**A12. The port.** The port is sought at each `://` of the value; in `s3://https://h:pw/b` — at both. Authority stretches
to `/`, `?`, `#` or the end of the address. The host is after the last `@`. The port is after the first `:` of the host, at a host `[…]` —
after `]:`. The characters `" ' ( ) < > [ ] { } , . ; :` at the end of the port do not belong to it. A non-empty port not of digits only
is a password in the place of the port: `rtsp://h:pw/` → `h:***/`, `rtsp://admin@h:pw/` → `admin@h:***/`,
`rtsp://admin:pw%40h/s` → `admin:***/s`.

**A13. Spellings of the manifest (`regex`).**
- Each `regex` of the rule reads the parts `in` (A2) of each address of the value if the scheme of the address is in `schemes`.
  An empty `schemes` — any scheme; case does not matter. `^` and `$` are the edges of the part.
- At `decoded: true` (the default) the part is decoded to a fixed point. What is found is masked in the written
  text in the place of the found characters together with their escaping: `acme/admin%3A***%4010.0.0.5`,
  `10.0.0.5%3A***`, `p%2561ssword/***`.
- All matches are taken, not only the first.
- The group `secret` is a password, `login` is a login (shown as written), `name` is a name for the reason of the refusal. An empty
  group finds nothing.
- Only `regex` reads pairs through `_` (`user=admin_password=…`, `?channel=1_pwd=…`), a password as a segment after
  a name (`/password/<password>/`) and a login with a password in the path of `driverpack://` (in the vectors `secret-in` — at `cam.source`). The common rule does
  not know them: these are spellings of devices, not parts of an address.

**A14. The display.** First a nested address with a password (A8, A9) is replaced as a whole by `***`: the value of a pair,
a segment or a path (`?src=rtsp://admin:pw@h/s` → `?src=***`, `/proxy/rtsp%3A…%40h/live` → `/proxy/***/live`).
Then A1–A13 read the value with this mask, and each stretch of a password is replaced by `***` where it stands.
Overlapping and adjacent stretches give one mask. A login is shown as written, an empty value stays
empty. A nested address with a login only is not masked. The reason for this order: otherwise an inner `@`
would stretch the userinfo of the outer address over the nested one.

**A15. The refusal.** The field in the refusal is chosen by all findings together, not by the first one found.
- A password by A6–A13, a url that does not parse (P/02.1 N1.2a; including a character outside the grammar, A2), and nesting deeper than 3
  give a refusal with the field `credentials.secret`. If there is a login next to it, the refusal also names `credentials.login`.
- There is only a login: the refusal names `credentials.login` and does not name the secret field.
- Nothing is found: the value is accepted.

«Does not parse» — by RFC 3986 (a character outside the grammar of A2, a non-numeric port of A12). A refusal of a parsed address by the section
«Schemes» (a scheme not from `schemes`, no host, no path at `host: path`) is not A15: the credentials do not give it, `bad_url` is
the step url of [the row check](row-check.md) (guess of stage C URLC-VECTORS-02, clarification, the Architect's decision of 2026-10-23).

The order of the checks affects only the text of the reason and is left to the implementation. The value and its parts are not repeated
in the reason (P/06.2 N4). The reason: a login found first does not make the password next to it safe —
`?usr=admin&pwd=…` is refused with the password field.

## read_address(value, field rule, catalogue) → display | refusal(field)

```
find(text, rule, level) → findings [(password | login, stretch in the written text)]
1. the head (up to the first ://; without :// — the whole text): each @                     → A11b
2. no :// → text: pairs by A5, A7; an address escaped as a whole                          → A9:
   find(address, rule ∪ catalogue, level + 1), the strongest kind over the whole value; end
3. nested addresses (A8): pairs of nested, values with % (A7a), segments with %;
   level + 1 > 3 → a password over the whole stretch;
   otherwise find(address, rule ∪ catalogue, level + 1) → the strongest kind over the whole stretch
4. userinfo at each ://                                                                   → A10
5. each @ after the first ://                                                             → A11a
6. the port at each ://                                                                   → A12
7. regex of the rule over the parts of each address of the text                           → A13
8. pairs (A3): the kind of the name A5, hidden by escaping A7, the end of a secret value A6

display(value):
1. the stretches of step 3 with a password → *** as a whole (A14)
2. find(the resulting text, field rule, 0): each stretch of a password → ***;
   overlapping and adjacent — one mask; a login as written; empty — empty

refusal(value):
1. the url does not parse (P/02.1)                                     → field credentials.secret
2. all findings of find(value, field rule, 0) together:
   a password → credentials.secret (and credentials.login if there is a login);
   only a login → credentials.login; nothing → accept                  (A15)
3. 400 fault: bad_url; error without the value and its parts, with the names of the credentials fields (P/06.2 N4)
```

**Races** of reading an address. None: it is a function of the value, the field rule and the catalogue loaded in the process. A manifest loaded
later changes only the reading of nested addresses in the following writes.

The refusal is the word `bad_url` and the names of the `credentials` fields (A15): at a door — 400 `fault: bad_url` (P/06.2 N4, P/06.1 N4), at
the customer library — the outcome `refused` ([the row check contract](row-check.md) «Refusals»).

## Vectors

The package [`secret-in`](../vectors/secret-in/README.md) (`cases.tsv`, the field declarations `fields.yaml`); free log text — the package [`log-mask`](../vectors/log-mask/README.md) of [the log mask contract](log-mask.md); the rules of «Schemes» — partly the packages [`group-of`](../vectors/group-of/README.md) and [`row-check`](../vectors/row-check/README.md). (ADR-0083 addendum (32) item 2)
