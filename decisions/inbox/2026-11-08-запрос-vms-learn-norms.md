# Учебная ветвь V11: только текст норм ADR-VMS-0004

Автор — «Спецификация VMS». Ветка `vms/v11-learn-norms-20261108`, полная база `c8eafc05626112db4c2003b416f762055deaef65`; дерево `/Users/murat/w2c/wt-vms-v11-learn-norms-20261108`. Прежняя ветка V11 English/history и её дерево заморожены и не менялись. Это следующая отдельно порученная владельцем доля, не продолжение правок c8.

## Основание и граница

Утверждённый ADR-VMS-0004 через дополнения(1),(2), источник — main `4ac4d1ece95be7324d5ce727ef775e60c92ad8b1`, exact snapshot `/Users/murat/w2c/cammeta-status/spec-vms-learn-20261108/ADR-VMS-0004-at-4ac4d1ece.md`. В базеc8 самого решения ещё нет; из норм на него дана текстовая ссылка, без несуществующего Markdown target. Правила полностью изложены в нормах и не требуют от реализации читать историю решений. Прямое новое поручение владельца открыло текст норм сейчас, не входы приёмки/пакет/включение обучения шага5.

Платформа — только неизменённый `VMS/PLATFORM_PIN` `3d8b6a3a74bfa359d362c691bd645fe4c132eaad`. Consolem — прежний `cb728a42cf2708bae186c95607d8edfcda6462fc`, API/shell/manifest/served set и `--without-learn` не изменены.

## Нормативная доля

- V/11.1 N1.4a: каталог с турами в одном источнике, устойчивые topic/chapter IDs, версия/отпечаток, язык/название/цель/набор/доступность в сборке; никаких выдуманных значений/нового формата. Поставку закрывают согласование договора, разрешённый перепин, manifest/SHA и проверенные вход/CSP/файлы/изоляция.
- V/11.1 N1.4 и N1.4a заменяют прежнее требование отдельной вкладки согласно доп.(1): кнопка в той же вкладке, до запуска предупреждение об отсутствии рабочих тревог и учебных данных, во время — постоянная полоса Training data/«Учебные данные». Выход возвращает рабочий режим с обычным входом без потери входа. Нет нового механизма входа/анонимного обхода. Параметры рабочего адреса не наследуются. Внешняя служба запрещена из параметров, meta и публичной метки по умолчанию. Нет рабочего API/черновиков/истории/секретов; сбой server/CSP/storage isolation даёт отказ показа без перехода в рабочий режим.
- V/11.7 N1.6/N1.10: шестой внутренний тип learn, запросы «как…», «покажи как…», «научи…»; «где…», «есть ли…», «какие…» о живых объектах — explain с прежними правами. Каталог может дополнить живой explain проверенной учебной ссылкой, не заменить живой ответ. Выбор учебной ветви идёт до рабочего обзора; в неё не передаётся рабочая переписка.
- V/11.9 N1.7 и V/11.10 N1.7: собственный prompt с каталогом первым, ровно open_chapter {chapter: enum catalogue ID}, no_chapter, ask_admin и tool_choice: required. Модель возвращает только chapter ID, не URL/HTML/JS/селектор. V11 проверяет ID и версию актуального каталога независимо от грамматики модели. Unknown ID/foreign version ничего не запускают, предлагается ручной каталог. Обычный ask_admin/question/context продолжен без второго рабочего протокола; admission/view на строке модели, очередь, лимиты и V10 прежние. Learn не получает working overview/read/schema/plan/apply, secrets/history; рестарт восстанавливает только собственный учебный разговор. Рабочие nine tools и V11.11–13 прежние.
- V/11.12 N1.5: учебная ссылка не план, не событие plan и не рабочее Apply. Подготовленные учебные ответы/заглушки явно подписаны; завершённый урок не измеряет живую модель или проверку рабочего плана. Без модели — ручной каталог/поиск при наличии поставки; без обучения урок не обещается. При английском UI честно указан русский язык нынешних туров. Порогов качества/задержки по черновым замерам не вводится.

### Зависимость договора

`answer.learn` — согласованное логическое направление расширения, которого НЕТ в нынешней закрытой схеме cb728a4. Подробная JSON wire shape и имена её внутренних полей не выдумывались. Это текст следующего поддержанного договора: «Консоль» готовит fork/contract patch, требуется согласование владельца договора, затем разрешённый перепин и условия поставки. Нынешние OpenAPI, AssistTurnRequest, AssistEvent, shell, manifest и static files не менялись. Нового HTTP kind, SSE learn event, флага запроса, публичной опции демона или языка данных нет. Существующие router/harness fixtures описывают нынешний рабочий набор; их учебное расширение не записано обходом запрета входов.

Входов приёмки обучения, новых сценариев, vectors, harness/system/tools fixtures, форм/stages/lifecycle, catalogue assets, туров, dataset packs и кода нет. Новые чеклисты проверяются чтением, не притворяются исполненными. Ни models/Quint/SUT/backend/browser, ни генераторы/судьи/пробы не запускались. READY/nrev/quint/global flags не продвигались. Нового вопроса о смысле/владении нет; остаются известный договор Console и отдельно открываемый шаг5.

## Проверки

Evidence физически вне source: `/Users/murat/w2c/cammeta-status/spec-vms-learn-20261108/proof/`. Итоговые команды, фактические exit codes, диагностика и roster добавляются ниже после проверки конечных байтов.

### Итог на конечных байтах

- `en_mirror.compare`:7 изменённых EN/RU пар,0 сообщений, exit0.
- `en_mirror.strict(..., count_steps=True)`: все разделы тех же7 пар,0 сообщений, exit0. Прежние заголовки/якоря/IDs сохранены; добавлены V/11.1-08…10, V/11.7-10, V/11.9-06, V/11.10-06, V/11.12-04 без перенумерации.
- Ссылки/якоря:159 неплатформенных локальных целей,0 ошибок, exit0. Платформенные ссылки проверены полным check_spec только по PIN3d8.
- Scope/byte audit:14 ожидаемых VMS текстовых файлов;18 protected paths unchanged, exit0. V10, V11.11–13, API/shell/manifest/data/harness/vectors/acceptance, Source/Platform/tools/skills байтами прежние. Все старые fenced blocks11.9/10, семь working answer steps11.9, nine-tool set и read-tool definitions11.10 сохранены;11.12 вне нового раздела/checklist идентична. Числовые уставки и working wire не менялись.
- `git diff --check`, cached check и staged boundary — exit0 перед фиксацией; hooks/range/pre-push выполняются штатно, без обхода.

Полная команда (Python3.12.15, pinned uv requirements):

```sh
uv run --no-project --python 3.12 --with-requirements skills/lesson-spec/scripts/requirements.txt python -B skills/lesson-spec/scripts/check_spec.py --strict-coverage --vms-evidence /Users/murat/w2c/cammeta-status/spec-vms-learn-20261108/proof/final-vms
```

Фактически exit1: **100 ERROR /62 EXC**, ровно итог c8. Доказательство c8 (`spec-vms-cb728a4-20261108/english-proof/final2-check.log`) переиспользовано как baseline того же checker, вместо повтора старых архивов/векторов. SHA checker ниже совпадает с c8. Все97 PLATFORM_CURRENT diagnostics byte-identical. Три прежних VMS reader-gap diagnostics те же; при сравнении нормализован только физический абсолютный prefix retained-view внутри FileNotFound, не относительный путь/смысл сообщения. Added0, removed0:

```
ERROR VMS_CANONICAL VMS/11-backend/journal/corrections-4.tsv: [Errno 2] No such file or directory: 'PINNED_VMS_VIEW/VMS/11-backend/journal/corrections-4.tsv'
ERROR VMS_CANONICAL VMS/11-backend/journal/corrections-8.tsv: [Errno 2] No such file or directory: 'PINNED_VMS_VIEW/VMS/11-backend/journal/corrections-8.tsv'
ERROR VMS_CANONICAL VMS/common/id-map.tsv: missing (ADR-0090 доп. (1), «Условия старта»)
```

Эти gaps уже направлены владельцем Архитектору→coord103-tools после приёма c8: VMS_IDMAP/history, journals без V11 exclusion и named Cyrillic exceptions. Повторный запрос не создавался, инструменты/исключения/бюджеты не правились. Красная проверка остаётся красной; общего normative READY/GATE и sourceReady эта авторская доля не заявляет.

Новая кириллица источника — ровно31 буква в шести требуемых лексических подсказках маршрута из ADR-VMS-0004(2): «как…», «покажи как…», «научи…», «где…», «есть ли…», «какие…». Это намеренные lexical operands, не необъяснённая owned prose. V11.7:333→364; в остальных изменённых EN файлах счёт прежний (README166 — прежние literal examples; нормы1/9/10/12 и specREADME0). Реестр исключений не менялся; остальная inventory c8 сохранена.

### Точный roster

- `VMS/11-backend/README.md` — SHA256 `bdcdc26457b7e01a22f3e260be61933b9b80dfe45f8f31b5f56e33baa481b91c`
- `VMS/11-backend/ru/README.md` — SHA256 `5cd3ee5d9000f4c7ae4b6cc3c2004fe491a9efd7c33d29a9a31bf2755da149bd`
- `VMS/11-backend/ru/spec/11-backend.README.md` — SHA256 `ecbde43e6668b5967b613e15c5fb17d963e11021cb86c7981c82ba10b7c44022`
- `VMS/11-backend/ru/spec/11.1-backend.norms.md` — SHA256 `1bf55ac0da669cabb9fad836e9477239b8ca921424034201f600884f900dcd92`
- `VMS/11-backend/ru/spec/11.10-backend.norms.md` — SHA256 `fccf6f0cc05c97559583dda44ee40746f7cc1c4090fe7e31adab269a5ba103f1`
- `VMS/11-backend/ru/spec/11.12-backend.norms.md` — SHA256 `18a02f43572f447a3e625acfd3abc11a56068ada6b8325a09118219d8bf1ecb3`
- `VMS/11-backend/ru/spec/11.7-backend.norms.md` — SHA256 `0e6d1303deb7cf80c86744671120e0085748015ffcdfba192e12296b41200980`
- `VMS/11-backend/ru/spec/11.9-backend.norms.md` — SHA256 `13b01f70092e112e20bb1d7a878893eaeb49c5aa9492dc6d384627a3a4e32f5a`
- `VMS/11-backend/spec/11-backend.README.md` — SHA256 `8b834691219d3bbea1e7206ab0c35d0aae9e04c52ae67bf834c19a60c8d20c61`
- `VMS/11-backend/spec/11.1-backend.norms.md` — SHA256 `07230077a74b5552813061672d276ea284f315de1bff872c79c9168c7db9ac27`
- `VMS/11-backend/spec/11.10-backend.norms.md` — SHA256 `cb7cded9ef6fef301b608d73a44a1ed9f417baa0d7950e4d3b098a633e7bb974`
- `VMS/11-backend/spec/11.12-backend.norms.md` — SHA256 `6f0c4dc2b691e62d49f9cbb05aa6651cbab7c9c43fc4269cda734f8e25882d4f`
- `VMS/11-backend/spec/11.7-backend.norms.md` — SHA256 `bfe95b2d1435aa127667bdf524ef848085c21c84e61f36c1cdb54cc566e4844b`
- `VMS/11-backend/spec/11.9-backend.norms.md` — SHA256 `216b53ab1c3c7fa106699dadacb9e1ab55e5031e30f378d1207f6804f71d3754`

Плюс только этот отчёт и собственная строка `ХОД-Спецификация-VMS.md`.

### Evidence identity

Authority snapshot SHA256 `3352ee131b9485b5ab20c1bfd414f93ba595a80c7e860ad87ee3e4718ef79943`; checker SHA256 `62659d79a0697fe282c7213c22861df68741147181deb63c00ab34c0dda4ff03`.

- `VMS/PLATFORM_PIN`: 41 bytes, SHA256 `e9c460aa593eb2a4e6fd6226e498cc9b91327137b56c394056a0eea273e591d2`
- `VMS/11-backend/consolem.openapi.json`: 632630 bytes, SHA256 `200d203d4197776892e66a32126998bc8cf0b79a9986ef7ac144c6af230f7124`
- `VMS/11-backend/backend.shell.html`: 11462 bytes, SHA256 `90e9cd59cb70207a785e23da943fb0785c9f80d382afecfae4d94a0bce9a05ff`
- `VMS/11-backend/backend.subsystem.yaml`: 22825 bytes, SHA256 `e0b3ea881dd08c584139cd722b8b2a66c8fdfc2355555dd8069952e7bea96504`

| Proof | SHA256 |
|---|---|
| `targeted-text-checks-final.json` | `6b7db84c7f20c3120a5c2036b5d00ad5d89a822d67369392b819f2001fba172f` |
| `diagnostic-comparison.json` | `12ec2e91c89cdaeb19880400ad922094122826250948a46972c6c23c7be97736` |
| `final-check.log` | `2d662b8dc8720867ecfa3079a02ef77c7c05070f885a7855bdc34d037c5db3d9` |
| `preservation.json` | `944b7310a185ea90c4b6e8583352e800695425b648612b6b1d69f0642c12f1dc` |
| `source-roster.json` | `6cabf714c7ea11ddb2bc7689ba1f367c327e1bc26289d278422d70e20ff76456` |
| `cyrillic-new-cues.json` | `90c37e6e83ee3af59a2fad1d18488daae61df1ec9baaa5af598109b0151e662a` |
| `ui-en-mirror.json` | `9b165e8c47f1e2b645d29049ea857a46827370908209038ae8ab26e227327b5e` |
| `ui-scope-audit.json` | `0d95f07684dd766af8ddb5985248c775b2eaba30017a08ebc8136e203a626739` |
| `ui-change-map.json` | `9c610fd13a5454531c7e06aa3b854857d14640a20a0fdd45546fa6a36dacf464` |
| `loop-tools-verification.json` | `cc09e82ddbd654393f4d63332bdc82c8e7b54ba598186f0a200f4c543270f434` |
| `loop-tools-author-report.json` | `cf270235e25bb62eb867c56f05ac80c2df836c8fd6c2ebd05619a030a4af221c` |
| `router-change-map.json` | `60e115de2f29f6860d86603841a6f6a2160e914ce83dd1add0c4464ac107359c` |

### Что дальше

«Консоль» — согласовать fork/contract patch со стабильным каталогом и typed answer.learn; после этого отдельный разрешённый перепин. Входы приёмки/пакеты/включение обучения — только отдельно открытый шаг5 ADR-VMS-0004 и ADR-VMS-0003. Старое обязательство отдельной вкладки заменено утверждённым same-tab правилом в этой норм-доле. Туры/подготовленные главы об ассистенте — у «Консоли», не написаны обходом scope. Независимого нормативного ревью, runtime/SUT/model/генерационных запусков здесь нет; авторские структурные проверки не доказывают исполнимость будущего договора или изоляцию браузера.
