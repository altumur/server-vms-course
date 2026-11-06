# Одноразовый начальный долг 38 файлов — Codex

Основание: прямое поручение coord103 со словом Архитектора, ADR-0083 доп. (114).
База кода: `8818e415d4c739c564ca338e2fb4d9190f2d3e0c`. Отдельный коммит поверх неё; история 8818 не меняется.

Реестр: `skills/lesson-spec/cyrillic-debt.tsv`. Добавлены ровно **38** ранее не учтённых файлов, **13843** буквы.
Старые **671** записи и **590257** букв сохранены: удаление новых строк восстанавливает прежний файл побайтно.
Итог: **709 записей / 604100 букв / ready 0**. Других изменений реестра нет.

- SHA256 реестра до: `b72ec020bc6da490fbc6a5f15021ab139babc6a85a3030864503c91d738e6d91`.
- SHA256 реестра после: `29e6ab81a1781f7ba76c85c354d0c0b9b7dbf8e361e0882f79f8f8df4c8f1073`.
- SHA256 точного roster TSV: `8e18950b9f79143a832d02dd7146a26bf88d92fb832c70cc93db9681af83b76d`.

Для воспроизведения roster TSV: заголовок `path<TAB>letters<TAB>sha256`, затем строки таблицы ниже в этом порядке,
поля разделены TAB, LF после каждой строки, UTF-8 без BOM. SHA256 третьего столбца — от полных исходных байтов файла.
Все 38 файлов побайтно совпали с Git-источниками `8818e415d`, `0c9787bee` и `ae526056c`.
Число букв независимо пересчитано по Script=Cyrillic, General_Category=L* Unicode 17.0.0:
449 символов из Scripts.txt с SHA256 `9f5e50d3abaee7d6ce09480f325c706f485ae3240912527e651954d2d6b035bf`.
Набор совпал с 38 прежними ошибками GATE, множества новых и старых записей не пересекаются.

## Точный roster

| path | letters | sha256 |
|---|---:|---|
| `CONSOLE-MODULE.md` | 944 | `e5314bee344edc182fa58f7838ac49cd9ecaa5a7dabbdf43c0d725c9476196f3` |
| `Source/tests/testdata/spec_load_debt.txt` | 72 | `fc3196063bcba60da618ddcd8f44540321f940da5b8c7df7545dc6868a5a9e80` |
| `Source/tests/testdata/spec_parity_debt.txt` | 511 | `48be2ca5995e8ee1a38e51d14c41baa8fb2d657386433e9bb6be3136c72dc575` |
| `Source/tests/testdata/spec_verdicts.tsv` | 39 | `1387f4679153363157a8ebfd2321c959ca4dcc8be5eb62cdb2da0a880667e39e` |
| `Source/tests/testdata/spec_verdicts/about_field_not_fixed_nowitness.subsystem.yaml` | 372 | `67b328d970925e75fee6c11ca98a3eea3d4ebe4bc20c3016dabd73f65c156ad0` |
| `Source/tests/testdata/spec_verdicts/bound_to_string.subsystem.yaml` | 372 | `9c78f8558c3fc284095a7126cb093f0c0436eb9993b03b8a6763773334afe1bb` |
| `Source/tests/testdata/spec_verdicts/capacity_default_float.subsystem.yaml` | 372 | `c0edf0a5c305241b93696593a49a9589c62ca6d22b3edda2a1aed30911791384` |
| `Source/tests/testdata/spec_verdicts/capacity_default_string.subsystem.yaml` | 372 | `4f9642cc5a7c2981f40f45ea7d42768d22033ee0ffcb6add43be76e2f2ee79ac` |
| `Source/tests/testdata/spec_verdicts/capacity_default_true.subsystem.yaml` | 372 | `bdd6e7b7b6f73d30edf86b1543f1778e5af0f286dbee84378a3af40528fa599b` |
| `Source/tests/testdata/spec_verdicts/dead_band_word.subsystem.yaml` | 372 | `518d61f13b854a36006a4b845f737327c451c130cd463ad1a43afeaf3d3b653e` |
| `Source/tests/testdata/spec_verdicts/default_map_string.subsystem.yaml` | 372 | `e87e1a393b6da256ba26d59a2b434c05623c904738e772745bf0c3f42044f491` |
| `Source/tests/testdata/spec_verdicts/display_events_word.subsystem.yaml` | 372 | `5719689c2be724e308a5cd015c275606715bec3eb365490b896a23a0a332ffdf` |
| `Source/tests/testdata/spec_verdicts/door_routes_dup.subsystem.yaml` | 372 | `fc60d9af0e727ee8b21a5a1f97360faca054f87976171b97b2689b354195339f` |
| `Source/tests/testdata/spec_verdicts/enum_on_list.subsystem.yaml` | 372 | `600de78fe2901cc327dbeb24cc117f005883166840ed0ba693d7d4f878720105` |
| `Source/tests/testdata/spec_verdicts/hb_worker.subsystem.yaml` | 372 | `521c29d7aeb3177d94b194121017645461168e09d979627a2159b8388b9f79a3` |
| `Source/tests/testdata/spec_verdicts/inherit_map_string.subsystem.yaml` | 372 | `ef32f027700f79af7c2795a56ba98779d0fa3a942a3c3589c5680f6c0332668a` |
| `Source/tests/testdata/spec_verdicts/objects_rows_heartbeats.subsystem.yaml` | 372 | `bdc7d9f36414078164c8504a5af3ccdac078265003784c0cb9bc4c5e424836eb` |
| `Source/tests/testdata/spec_verdicts/required_true_string.subsystem.yaml` | 372 | `8f78365e9612096480af6cb680431f0697e120ac53bf92d7f64a23f8d4e0dc6c` |
| `Source/tests/testdata/spec_verdicts/required_yes.subsystem.yaml` | 372 | `a6cb9779713e82bcbb5d6596f65b03a867f24f4787f4948c8577158aaa33af39` |
| `Source/tests/testdata/spec_verdicts/requires_nothing.subsystem.yaml` | 372 | `116207e88e00d62fec0864f4928d381a13d284044d5474bc38ec303fba5ffe1a` |
| `Source/tests/testdata/spec_verdicts/rows_servers.subsystem.yaml` | 372 | `f883baf4c95f71a1734c5d1bb7112ae80a87d0b53a7fdc6db10d95467cc43bec` |
| `Source/tests/testdata/spec_verdicts/rows_where.subsystem.yaml` | 372 | `04f2a18f67efc70cb5885985b8a51b162e72eefecb799b7c4ba14e5041d8c973` |
| `Source/tests/testdata/spec_verdicts/secrets_reader_domainconsole.subsystem.yaml` | 372 | `27123cc0789239a5c34ceef0e1f2c7bc6c3e9f7f3c4348e3643d6b382a3ce468` |
| `Source/tests/testdata/spec_verdicts/servers_both.subsystem.yaml` | 372 | `03519d689d6fc5bac014097113d2f4eb4aba9e75c13daa35c937b26de3d89865` |
| `Source/tests/testdata/spec_verdicts/slot_prefix_digit.subsystem.yaml` | 372 | `5185948f8b61ac9c0a43fea33121a3871b44dc3471b1368526d07d0b52371b55` |
| `Source/tests/testdata/spec_verdicts/slot_prefix_long.subsystem.yaml` | 372 | `54b3d742c0c51960ab949939451cfe241a93fcd5fb4325d96e251fcb69a3509f` |
| `Source/tests/testdata/spec_verdicts/status_worker.subsystem.yaml` | 372 | `a60249514604e0ce941a9ee5e9af65b6e83ad120a066e7448c1eaf360dcd9bfc` |
| `Source/tests/testdata/spec_verdicts/table_events_shadow.subsystem.yaml` | 372 | `792e8ca89f0e30a25c61766703bc3f422afabee87b38bafdff245d96c9c25fe9` |
| `Source/tests/testdata/spec_verdicts/table_field_fixed.subsystem.yaml` | 372 | `9f1dc832b7845d764619eb3d9b94b5e355906f68298389f732ce66ddbdd895e1` |
| `Source/tests/testdata/spec_verdicts/table_field_inherit.subsystem.yaml` | 372 | `82aba1063625a05cb2126102ccd70910ef5a17c2973ac45609c929dea2d0a7f5` |
| `Source/tests/testdata/spec_verdicts/table_marks.subsystem.yaml` | 372 | `8eddbeacdb55fcee9b9538aed9fb436ed6b87b2babc5365e7a646aa25212a6ee` |
| `Source/tests/testdata/spec_verdicts/table_metrics_shadow.subsystem.yaml` | 372 | `4401b1d132d8df93e562d9b59dfeb4e6a69b887b41e668a6812fc58bc6fa849e` |
| `Source/tests/testdata/spec_verdicts/table_servers.subsystem.yaml` | 372 | `1fcda9976255ad7136dca60d79aa5a2b993da51c23e9d5c6e8c06fcc61cd49c3` |
| `Source/tests/testdata/spec_verdicts/tie_break_random.subsystem.yaml` | 372 | `013eff6ea086192aa4c9689af7be043e300acddda7eaf9431270e70da9af8e02` |
| `Source/tests/testdata/spec_verdicts/type_text.subsystem.yaml` | 372 | `f75ed87c8b122c3c902abed9324e1564c2bcfb28ca9fd618e9bf29165e0d5abd` |
| `Source/tests/testdata/spec_verdicts/unit_id_nosuch.subsystem.yaml` | 372 | `2ab27a0002e6783d38a5a500e5758367d36f61c6835d9e1ce64d5c1b546141f5` |
| `Source/tests/testdata/spec_verdicts/worker_reads_bare.subsystem.yaml` | 372 | `6455e049f0d9167e9ab58237fdf542bbe74ef5ee72fd97af3f53df939f31fff5` |
| `Source/tests/testdata/testsub.subsystem.yaml` | 1 | `7e6118cea2d639e11e894208d5f5be1d82cd1ec385cac0231fe7449305e5430a` |

## Граница изменения

Это историческое свидетельство одной разрешённой фиксации, не второй рабочий реестр и не режим программы.
Общий bootstrap/reset CLI не вводится: код checker и его мутантов остаётся побайтно как в 8818.
Дальнейшие изменения долга — только снижение/удаление через `--shrink`; новые файлы и рост — FAIL.
Будущие переносы console/localization, Source testsub/spec_verdicts, корневых договоров и COURSE_COMMIT
по ADR-0083 (115), (116) и ADR-0121 (10) этим checkpoint не активируются; их делает review103 после joint.
Исходные данные, нормы, console-свидетель, runtime, экспортёр и пины не менялись.
Прогон joint с author translation 638 этим отчётом не удостоверяется.

## Повторная проверка

На исходном срезе этого checkpoint полный `check_spec` дал **PASS with 62 exceptions**:
`cyrillic_debt_files=709`, `cyrillic_debt_letters=604100`, `cyrillic_ready=0`.
`test_check_spec`: **163**, OK с одним прежним пропуском снятого диалекта P/02.1.
`test_check_forms`: модулем **89/89**, 182.774 s; файлом **89/89**, 183.320 s.

Дополнительно проверены **15 контролей** на отдельной полной копии судимых домов,
с тем же 709-строчным реестром. Это временная тестовая копия, не Source 638 и не
генерация/перевод исходных данных; канонический реестр и данные не менялись.

| Контроль | Ожидаемый и полученный исход |
|---|---|
| Исходные 709 / 604100 | PASS |
| Рост на одну букву старой записи corrections-1.tsv | FAIL; shrink также FAIL, реестр не записан |
| Рост на одну букву новой записи CONSOLE-MODULE.md | FAIL; shrink также FAIL, реестр не записан |
| Рост на одну букву новой записи spec_verdicts.tsv | FAIL; shrink также FAIL, реестр не записан |
| Новый after-bootstrap.txt с буквой | FAIL; shrink также FAIL, реестр не записан |
| Снижение CONSOLE-MODULE.md с 944 до 943 | Обычная проверка FAIL с требованием shrink; shrink PASS, итог 709 / 604099; старые 671 записи прежние |
| Удалены буквы ровно в новых 38 файлах копии | Обычная проверка FAIL; shrink PASS, итог 671 / 590257, прежний файл реестра восстановлен побайтно |
| Флаги --bootstrap и --reset | Каждый отвергнут парсером, exit 2; реестр не меняется |

В таблице 13 запусков checker и два отказа CLI. Наличие разового добавления не
открыло дальнейшего роста или автоматического начального долга.
