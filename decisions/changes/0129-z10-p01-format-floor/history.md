# Historical source replaced by Z10 source A

This history is not an active compatibility obligation or an implementation input. Base `d034aa09e6dcad450cd4e0942457f430dda43ece`; authority ADR-0129 (23). The earlier read-only plan, all original reports/receipts and f935 expected bytes remain immutable; the final three presentation edits are separately authorized by de4ba859. No old programme is re-executed here.

## Former block 1: `Platform/01-store/spec/01.3-store.norms.md`

Former source UTF8 span 7345..8172; sha256 `c5de90f9dc2792baa0b2befedb980bd5cef87c3c7f13ce404e49c5014d86768b`.

````text
format:    in -dir — the file FORMAT, a JSON object {format, version, impl} (string, integer, string): format and version — the on-disk format
           of this implementation, impl — the name of the implementation, only for the log; the daemon writes it first into an empty directory
           (tmp + rename), before any other write; start: the directory is empty → write FORMAT; format and version are those that
           this build reads → start; otherwise (the directory is not empty but there is no FORMAT; foreign format or version; FORMAT out of
           form) → start refusal, code 2, the log names the directory and the mark found; nothing is written to or
           removed from the directory. A change of implementation — only by a copy (copy below) into a fresh directory (the store pilot, A1)
````

## Former block 2: `Platform/01-store/spec/01.3-store.norms.md`

Former source UTF8 span 44591..44849; sha256 `58e8162b19c115f006a7439aad7a2d125860c205bc1cb35d6e8920fb269e5f86`.

````text
- `start_format`: the data directory is not empty but there is no mark `FORMAT`; foreign `format` or `version`; `FORMAT` out of form (N1.3 `format`). Caller action: take a copy with the former implementation (`backup`) and restore it into a fresh directory.
````

## Former block 3: `Platform/01-store/spec/01.3-store.norms.md`

Former source UTF8 span 56469..56824; sha256 `6be3db87dcf097b7d0aed2a3887ed6532463d9193dfac14af25bbb23365be84f`.

````text
5. **the format mark and the profile `file://`**: the values `format` and `version` of its mark `FORMAT` and which versions of its format the build reads (N1.3 `format`); the on-disk format of the profile `file://`; the command by which a copy of N1.3 `copy` is taken from a store `file://` (the form of the copy is a norm) (the store pilot, A1, A2, A9).
````

## Former block 4: `Platform/01-store/spec/01.3-store.norms.md`

Former source UTF8 span 30564..30735; sha256 `2ae841a823cd1987154a507618ce342e4a4251f4db8288b05c493c3452329d73`.

````text
| `floor` | integer; ≥ 0; ≤ 9007199254740991; the whole sign for the reader too (x-whole) | required |  | the lower bound of issue after a restore; generation << 32 |
````

## Former block 5: `Platform/01-store/ru/spec/01.3-store.norms.md`

Former source UTF8 span 9182..10253; sha256 `8e80a788e9950ca771bf558d06d26fd13387ff139a226d140d769717725554b1`.

````text
format:    в -dir — файл FORMAT, JSON-объект {format, version, impl} (строка, целое, строка): format и version — формат
           на диске этой реализации, impl — имя реализации, только для лога; демон пишет его первым в пустой каталог
           (tmp + rename), до любой другой записи; старт: каталог пуст → записать FORMAT; format и version — те, что
           читает эта сборка → старт; иначе (каталог не пуст, а FORMAT нет; чужие format или version; FORMAT не по
           форме) → отказ старта, код 2, лог называет каталог и найденную метку; в каталоге ничего не пишется и не
           удаляется. Смена реализации — только копией (copy ниже) в свежий каталог (пилот хранилища, A1)
````

## Former block 6: `Platform/01-store/ru/spec/01.3-store.norms.md`

Former source UTF8 span 58664..59013; sha256 `08ca039a0caf1331dbf1d211dfa47fbd7660744d53139879d86677d545288bea`.

````text
- `start_format`: каталог данных не пуст, а метки `FORMAT` нет; чужие `format` или `version`; `FORMAT` не по форме (N1.3 `format`). Действие вызывающего: снять копию прежней реализацией (`backup`) и восстановить в свежий каталог.
````

## Former block 7: `Platform/01-store/ru/spec/01.3-store.norms.md`

Former source UTF8 span 74634..75108; sha256 `ffa634563b5658b1503a0e56061791b882a4e91ced0ae503d92771cddbed35d4`.

````text
5. **метку формата и профиль `file://`**: значения `format` и `version` своей метки `FORMAT` и какие версии своего формата читает сборка (N1.3 `format`); формат на диске профиля `file://`; команду, которой с хранилища `file://` снимается копия N1.3 `copy` (форма копии — норма) (пилот хранилища, A1, A2, A9).
````

## Former block 8: `Platform/01-store/ru/spec/01.3-store.norms.md`

Former source UTF8 span 39950..40145; sha256 `d33b9e553c74e3a0270d5460807e07572cf0adf9a510444e582677de217d5bef`.

````text
| `floor` | целое; ≥ 0; ≤ 9007199254740991; целый знак и у читателя (x-whole) | обязателен |  | the lower bound of issue after a restore; generation << 32 |
````

## Former block 9: `Platform/01-store/acceptance/3/README.md`

Former source UTF8 span 5062..5157; sha256 `f747147adaea08d60452866c97393b6aa26668fe71ede02f498301f1821a4daa`.

````text
| `bad-floor.jsonl` | the floor row with a non-decimal `floor` `12.5` (sc. 12 steps 25–26) |
````

## Former block 10: `Platform/01-store/ru/acceptance/3/README.md`

Former source UTF8 span 6506..6623; sha256 `d2c0933f6fd803aacc065c8c70c452287cc03a0cb1fe0a83f793ddf5952f333a`.

````text
| `bad-floor.jsonl` | строка пола с недесятичным `floor` `12.5` (сц. 12 шаги 25–26) |
````
