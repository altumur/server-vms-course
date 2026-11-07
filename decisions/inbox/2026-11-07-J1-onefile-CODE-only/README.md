# J-P07-01: запись одного тестового файла без исполнения

Rootless guard Source0d сдан отдельно. READONLY child01f8 перепривязал прежний план к модулю155b; в предложенном тесте изменилась только ожидаемая SHA. Primary проверил один before-файл, пять literal замен, полный after5469 и сохранение остальных байтов.

Отдельный `APPROVAL.json` разрешает spec103 через coord103-src записать только Source/tests/console/holder-page.test.js нормальным дочерним коммитом от0d. Пять блоков исправляют local canonical loading, прежнюю positive pending-array запись и ожидание счётчика, добавляют current-format positive и включают его результат в прежний отчёт. Остальные проверки и error accounting сохраняются.

Проверка сейчас только raw/Git: exactbefore/after, mode/blob, inverse/outside и onepath diff. Node, parser, jsdom и запуск не разрешены. Ограничение сохраняет различие между сданными байтами и проверенным поведением: даже после freeze нельзя заявить ready/PASS. После сдачи нужен отдельный точный допуск на исполнение.
