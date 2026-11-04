# VMS module acceptance — the common stand and directives

This English text is the source; the Russian translation `ru/acceptance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

Common to the acceptances of the VMS lessons (`VMS/NN-<имя>/acceptance/K/`). The basis is the [common platform acceptance README](../../../Platform/common/acceptance/README.md)
(the export the module stands on; the dictionary of directives, doors, requests and expectations, the format of `scenarios.tsv`, the section «Стенд»):
the VMS acceptance uses its forms and adds only what is below. The run — after the first stage C generation that has passed
the platform acceptance (ADR-0090 addenda (8), (9)); until then the scenarios are norm text. A lesson README names its stand by a link
here and writes only the differences.

## The VMS stand

The platform processes — per the section «Стенд» of the common README: the store, the cluster console, the controller of each installed
subsystem, the server resource `srv-a` (and `srv-b`, if the lesson README names it). Installed are the VMS manifests that
the lesson README names, from their canon `VMS/<NN-sub>/<sub>.subsystem.yaml` (ADR-0090 addendum (6) item 8) — the bytes as they are.
The console — `CONSOLE_ROOT=<sub>` of the lesson; the other subsystems are mounted (P/06.5 Н1.1). The subsystem files
`/etc/<sub>/<sub>.env` are not set unless the lesson README says otherwise (the subsystem defaults). The keyring is set
(`SECRETS_KEY`): the secrets of rows are sealed.

**The VMS domain stand.** A scenario that needs people with grants (the lesson README names it) runs on the «Стенд домена»
of the common platform README (`@domain`, the doors `holder`, `member <кластер> …`, `@person`): the clusters `hold` and `m1` are prepared
identically, as on the platform (the P/08.3 acceptance README, «Подготовка каждого сценария»), — the VMS stand above with the lesson manifests,
the processes — those the lesson README names, and on top of them — what the platform domain stand requires (the resource of its own server,
the domain and the domain console on `hold`, the agents `hold` and `m1`); `member m1 console` — the console of `m1`, the root — the lesson subsystem, `member m1 console2` — the same console,
the mounted subsystem that the lesson README names (the prefix `/<sub>`, as `console2` below; on the platform
`member … console2` — `/testsub2`). The grants row of `m1` the scenario writes in full (`holder PUT /domain/grants/m1`, with the line
`root`).

**Stand media.** The `MEDIA_DIR` of the stand (V/01.3; the subsystem file of `cam` sets it to a stand directory) contains `door.mp4` — H.264, ≥ 10 s; the camera `driverpack://file/door.mp4` is
a file that behaves like a camera (no host, no device with outputs and archive).

**The frame share on the stand.** The subsystem file of `cam` also sets `SHM_DIR` (V/01.2 Н1.3, Н1.7) — the frame share directory of its own
instance, an absolute path (`{data}/run/cam-shm`), not `/run/vms-cam-shm` of the acceptance machine; the substitution `{shm}` is this
directory. The subscribers (`rec`, `det`) do not configure the directory: they take the exact address from the holder's heartbeat. The share address in
an expectation is `shm://{shm}/…`: the path is absolute, starts with `/`, and `shm://` + the path gives three slashes (`shm:///…`).

**psim plugins on the stand** (V/12). The plugin directories `security_controller` and `camera` of psim-sdk `c3d9ebb` — an executable file
built from `psim_plugins/cmd/<плагин>` in advance on the acceptance machine, `plugin.json` and `langs/` as they are, without edits; the substitution
`{psim}` is the directory where they lie (`{psim}/camera`, `{psim}/security_controller`). The stand puts the plugin directory into
`{data}/usr/lib/psim-<id>/` of its own instance instead of `/usr/lib/psim-<id>/` (V/12.4 Н1.1) before each `@psim install`; `<id>` is
`metadata.plugin_id` in lower case, as in the subsystem name (V/12.1 Н1.1); the step argument stays `{psim}/<плагин>`. The adapter is
the program of the implementation of lesson V/12. The canon of `backend` is `VMS/11-backend/backend.subsystem.yaml` of the export; the P/02.4 traversal `add` after `@psim install`, `@psim disable`, `@psim enable`,
`@psim sync` the stand executes by the step `@traverse` with its own processes (the manifest files, the rights, the store and the console when they differ, the controller `psim-<id>`); the traversal set is the stdout of the command; the worker-adapter `psim-<id>` —
by the scenario step `@start worker psim-<id> <имя> on <сервер>`, the program is the key `stand.worker` of the profile `V12-psim`. There are no `backend/instances` rows
and no `backend` worker on the stand (the stand has no V/11 implementation): the assembly waits only for `served` of the manifests, there is no one to wait for
the rise of `backend` — «пульс каждого экземпляра» is empty (V/12.4 Н1.3 step 4). A secret by input (`--secret`) the stand writes to the `stdin`
of the command as a line `<поле>=<значение>` followed by a newline, one line per secret; `<поле>` is the psim parameter name without the suffix
`_secret`; `--secret` does not go into the command arguments (a decision of «Спецификация VMS»).

**The `obsd` engine on the stand.** The part `obsd` (V/02.2) is the binary file of the engine of the version of V/02.2 Н1.4 (ObjectStorage, the tree
`2bbee4a` with the patches 01–07), built in advance on the acceptance machine; the substitution `{obsd}` is the path to it (the engine source is not
exported: the lesson norm is the contract of `obsd`). The stand starts the part with the stand command `obsd` of the implementation profile `rec` — its
part wrapper (`parts.obsd.exec`, V/02.2 Н1.1) — with `{obsd}` (the engine path) in the command template; how the wrapper takes the engine path
from the command — «Решает реализация»; the stand sets in the subsystem file of `rec` (`{data}/etc/rec/rec.env`, `W2C_SUB_ENV` of the part and
of the recorders) `OBSD_SOCKET` — a socket in the directory of its own instance (`{data}/run/rec-obsd/obsd.sock`, shorter than `sun_path`), not `/run/vms-rec-obsd/obsd.sock`
of the acceptance machine: parallel instances do not share the socket and its lock. The volume mount point is `{data}/subsystems/rec/obsd/volumes/<n>`
(below); the share directory of `cam` is `{shm}` (above).

## VMS directives and doors

The VMS dictionary of directives is the table below, on top of the dictionary of the common platform README: a directive that is neither there nor here is an error of the scenario form (check_spec).

| Form | Meaning | Lessons |
|---|---|---|
| `@start worker <sub> <имя> on <сервер>` | start a worker of the VMS subsystem `<sub>` with the slot `<имя>` (`<prefix>-<сервер>-<n>`, P/02.4 Н1.1) on a stand server — by the «Стенд» command of the subsystem implementation (its description names the command; the section «Решает реализация» of the lesson instruction); the expectation is `ok` once the process has captured the slot | V/01 (chapters 2, 4), V/04 (chapter 4) |
| `@start worker <sub> <имя> on <сервер> labels=<метки>` | the same, with server labels: the worker gets the environment `LABELS=<метки>` as is (the form `labels=` of the common platform README) | V/10 (chapter 2) |
| `@start worker <sub> <имя> on <сервер> labels=<метки> <ИМЯ>=<значение>` | the same, with a worker environment variable as is (the form `[<ИМЯ>=<значение>…]` of the common platform README) | V/10 (chapter 2) |
| `@start resource` | as in the common platform README: the server resource process | V/04 (chapter 1) |
| `@psim install <каталог>` | the installation step of lesson V/12 (V/12.4 Н1.2) — by the «Стенд» command of the lesson implementation, as the stand administrator; the directory is `{psim}/<плагин>`; the expectation `ok` is code 0 | V/12 (chapter 4) |
| `@psim install <каталог> --values <файл>` | the same with a file of initial values (the path is relative to the lesson acceptance directory) | V/12 (chapter 4) |
| `@psim install <каталог> --owner <выбор>` | the same with the owner choice `<T>=<id>` | V/12 (chapter 4) |
| `@psim install <каталог> --secret <ввод>` | the same, a secret by input `<поле>=<значение>` — instead of the stand terminal | V/12 (chapter 4) |
| `@psim finish <каталог>` | the installation phase after the traversal (V/12.4 Н1.2); the expectation `ok` | V/12 (chapter 4) |
| `@psim finish <каталог> --values <файл>` | the same with a file of initial values | V/12 (chapter 4) |
| `@traverse` | the P/02.4 Н1.7 traversal `add` for the single stand server by the traversal set of the last `@psim` (V/12.4 Н1.2; ADR-0115 addendum (24)): the runner drives the stand processes, therefore the stand does not call the implementation's `w2cctl rollout` (it is judged by the system sc. 09 of P/02.4) and executes the traversal steps itself: (1) each word of the set — the files in `{manifest}` per P/02.4 Н1.9 `manifest get` (ADR-0115 addendum (26)): all files that the row `platform/manifest/<sub>` names (the bytes `yaml`, `shell`, the files `files`) — to temporary names; a check of the `sha256` and of the size of each and of the row hash against the hash of the word; then an atomic replacement of the previous files of the same names (`backend`, the dependents and the owners have them since the stand start); a mismatch, an unreadable row or part — a failure with the subsystem name, nothing is replaced; the files the row does not name are not touched; (2) the rights file by the rights derivation command (`{manifests}` = `{manifest}`): equal to the file the store runs with — the store is not restarted (ADR-0115 addendum (25) item 3), otherwise — a restart of the store with the new file; the barrier — always, also without a restart (addendum (27) item 1): `GET /v1/rights` of `admin.sock` is equal in meaning to the file, `GET /v1/status` of `admin.sock` — `state` `Leader` and `applied` ≥ `commit` (there is one member — itself the leader; P/02.4 Н1.9 `barrier`); (3) the console: for each word `GET /manifest/<sub>/source` already gives `sha256` equal to the hash and `served` equal to the `rev` of the row `platform/manifest/<sub>` of the store (P/02.4 Н1.9 `barrier`; ADR-0115 addenda (27), (28) item 3) — it is not restarted, otherwise — a restart of the console and the same barrier; the barriers — no longer than 300 s (`ROLLOUT_WAIT` P/02.4 Н1.9), polling once per 1 s, not waited out — a failure naming the unfulfilled part; (4) the controller of each subsystem of the set that does not have one — the «Стенд» controller command with its name, as for `backend` (P/02.4 Н1.7 `add` step 2). The set is the words of the stdout of the last `@psim` with code 0 (stderr is the step log); each word is `<sub>=<sha256>`: `<sub>` per the grammar of P/02.1 `name`, `<sha256>` — 64 lowercase hex digits; any other word and a repeated `<sub>` — a failure of `@traverse` with this word (as with `rollout`); no set or an empty one — does nothing; the expectation `ok` | V/12 (chapter 4) |
| `@psim enable <id>` | enabling (V/12.4 Н1.5); the expectation `ok` | V/12 (chapter 4) |
| `@psim disable <id>` | disabling (V/12.4 Н1.5); the expectation `ok` | V/12 (chapter 4) |
| `@psim sync` | the assembly (V/12.4 Н1.3); the expectation `ok` | V/12 (chapter 4) |
| `@psim-fail <код> install <каталог> --values <файл>` | the installation step ended with the code `<код>` and wrote nothing: the listing of the whole store `/v1/list` without `prefix` (P/01.1 Н2.1 — all rows) before and after the step matches by keys and `index`, except the noise — the rows of the background writers of the platform, which the installation step does not write: heartbeats (a key with the segment `heartbeats` before the last one — `<sub>/heartbeats/<имя>`, or with the last segment `heartbeat` — `platform/resources/<server>/heartbeat`, `domain/<sub>/heartbeat`), the server door row `platform/doors/<сервер>` (the resource, `at` every `ALIVE_EVERY`, P/05 Н1.4), the store door row `platform/configstore-doors/<id>` (P/01.3), the sweep list `<sub>/sweep` — a key of two segments (the console, once per 60 s, P/06.1 Н1.5); any other difference — a failure naming the key; the expectation `ok` | V/12 (chapter 4) |
| `@until <секунды> <запрос>` | as in the common README: repeat the read until it matches | V/01 |
| `@manual <текст>` | as in the common README: the runner prints the text and does not execute it, `expect` is `manual`; a step on a live driver, client or double that the stand does not have | V/01, V/03, V/11 |
| `console <МЕТОД> <путь>` (or a path without a door) | the cluster console, the root is the lesson subsystem (`/cameras`, `/devices`, `/requests`) | V/01 |
| `console2 <запрос>` | the same console, the mounted subsystem that the lesson README names: the request path gets its prefix `/<sub>` (`console2 POST /cameras {…}` → `/cam/cameras`) | V/02 (chapter 4) |
| `holder <воркер> <МЕТОД> <путь>` | the camera holder door (V/01.5) of the worker `<воркер>`: the stand sets in `/etc/cam/cam.env` `PLAYBACK_PORT={hport}` (its own port per worker), without a kit — `http://127.0.0.1:{hport}` | V/01 (chapter 5) |
| `archive <воркер> <МЕТОД> <путь>` | the recorder archive door (V/02.5) of the worker `<воркер>`: the address is the field `url` of its heartbeat; without a kit — `http://127.0.0.1:<порт>` | V/02 (chapter 5) |
| `resource GET /v1/objects/<ключ>` | the door of the server resource `srv-a` (P/05 Н2): the subsystem objects — request labels `<sub>/commands/<rid>`, heartbeats `<sub>/heartbeats/<воркер>` | V/01 (chapter 4) |
| `@domain <кластер>` | the VMS domain stand («The VMS domain stand» above): `@domain` of the common platform README with one member | V/03 (chapter 1) |
| `@person <имя> <пароль>` | as in the common platform README; the password of the people of the VMS scenarios has no spaces | V/03 (chapter 1) |
| `@person -` | as in the common platform README: from here on without a token | V/11 (chapter 4) |
| `@person root w2c test root password` | as in the common platform README: return as the person `root` of the domain stand, the password of the directive `@install domain` | V/11 (chapter 4) |
| `@sigkill <имя>` | as in the common platform README | V/11 (chapter 4) |
| `@stream-open <метка> <запрос>` | as in the common platform README; the request — the door `member <кластер> console` or `console2`, `@header Last-Event-ID` is allowed; the expectation — the code of the headers, `2xx` | V/11 (chapter 4) |
| `@stream-wait <метка> <с>` | as in the common platform README: a JSON subset from `data:`, the expectation `ok <JSON>` | V/11 (chapter 4) |
| `@stream-none <метка> <с> ~<текст>` | as in the common platform README; the timeout counts as a sleep, the lesson README names the reason | V/11 (chapter 4) |
| `@stream-close <метка>` | as in the common platform README | V/11 (chapter 4) |
| `@on <кластер> <запрос>` | as in the common platform README: the directive on this cluster | V/11 (chapter 4) |
| `@cut-route <от> <к> console` | as in the common platform README: the runner's intermediary breaks the directed console road `<от>` → `<к>` and accepts no new connections; the expectation — `ok` | V/11 (chapter 4) |
| `@mend-route <от> <к> console` | as in the common platform README: the road accepts connections again; the expectation — `ok` | V/11 (chapter 4) |
| `member <кластер> store <запрос>` | as in the common platform README: the store door of a member cluster through `admin.sock`; writing a row that a worker would leave behind on a break | V/11 (chapter 4) |
| `holder <запрос>` | on the VMS domain stand — the domain console (the door `holder` of the common platform README); it differs from the camera holder door `holder <воркер> <МЕТОД> <путь>` above by the second word: here it is the method; the first scenario that needs both on the domain stand gives the domain door its own word | V/03 (chapter 1) |
| `member <кластер> console <запрос>` | the console of a member cluster, the root is the lesson subsystem; carries the token of the person of `@person` | V/03 (chapter 1) |
| `member <кластер> console2 <запрос>` | the same console, the mounted subsystem that the lesson README names (the prefix `/<sub>`) | V/03 (chapter 1) |
| `door <единица> <запрос>` | the holder door of the unit `<единица>` (`<sub>/<id>`) with a door token: the stand takes `GET /where/<id>` of the console (the root is the subsystem of the unit; otherwise `/<sub>/where/<id>`) with the loopback identity and sends the request (`<МЕТОД> <путь> [тело]`, JSON — `Content-Type: application/json`) to `door.url` with `Authorization: Bearer <door.token>`; the token is fresh for each request | V/10 (chapter 2) |
| `door <единица> bare <запрос>` | the same door without `Authorization` (a token refusal) | V/10 (chapter 2) |
| `member <кластер> door <единица> <запрос>` | the unit holder door on the VMS domain stand: `where` — through the console of the member cluster with the token of the person of `@person`, then as `door` above | V/10 (chapter 2) |

**Substitution of `$имя` inside an expectation string** (VMS scenarios, on top of the string `$имя` of the common platform README, where only the whole value is
bound and compared). In a JSON string of an expectation that is not equal to `$имя` as a whole, each occurrence of `$` followed by
`[A-Za-z0-9_]+` — the name up to the first character not of this class — is replaced by the value of the bound name of the scenario, then the string
is compared as a whole: `"cam-$c1-card"` with `$c1` = `7` — `"cam-7-card"`, `"folder:$fid"` — `"folder:<id папки>"`. There is no binding inside
a string: the name MUST be bound earlier by a step with `$имя` as a whole; an unbound name is a mismatch of the step. The forms `@not($имя)`,
`@spoil($имя)` — per the platform dictionary, as before (a decision of «Спецификация VMS» on a question of the runner, V/02.4 `06-edge`, V/11 acceptance 8). There is no escaping: `$` before a letter, a digit or `_` in a VMS expectation is always a name; there is no real `$` sign before them in
the VMS expectations (checked over all `scenarios.tsv` on 2026-11-03). Should it be needed, the rule `$$` is introduced then, together with the runner dictionary.

**The subsystem file on the stand.** The keys of the subsystem file (`/etc/<sub>/<sub>.env`) that the lesson README names (per scenario as
well) the stand writes into the file `{data}/etc/<sub>/<sub>.env` of its own instance and gives the subsystem worker its path in
`W2C_SUB_ENV` (P/02.4 Н1.2; [the environment file contract](../../../Platform/common/contracts/env-file.md)) — before `@start
worker`; the file is its own per scenario. VMS substitutions beyond the common README: `{model_stub}` — the runner program `model-stub`
(the model stub, V/10.2 Н5); `{spec}` — the specification root (the directory with `Platform/` and `VMS/`); `{hport}` — the port of the camera
holder door (above); `{obsd}` — the binary file of the `obsd` engine (above).
The stand substitutions also apply in the requests and expectations of the VMS `scenarios.tsv`: the path
`/data/platform` of the norms (`PLATFORM_DIR`, P/02.4 Н1.2) on the stand is `{data}` of its own instance, and the scenario writes `{data}`
(`file://{data}/subsystems/rec/obsd/volumes/1`), not the literal path of the acceptance machine; `{shm}` — the frame share directory (above).

Binding of `$имя` is within a scenario (the common README); a scenario that needs a camera creates it itself. Each
scenario runs on a clean instance unless the lesson README says otherwise; a repeated and a parallel run — their own instances.
The stand does not yet have a double of a device with outputs, presets and archive: the norms that need it are checked by reading
(the lesson README names them).
