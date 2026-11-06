# Процесс domain — урок P/08

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом (ADR-0121).

Микромодуль: процесс domain держателя. Что нормирует и откуда — записка модуля `Platform/module-design.md` (для человека, в выгрузку не входит), таблица «Уроки».

Раскладка каталога (ADR-0124: английский источник — на каноническом пути, русский текст для человека — в `ru/`). Урок собран из сторон держателя уроков M11/1–12; стороны агента и
ретранслятора — урок P/09, консоли домена — урок P/10, поздний слой консоли кластера — [глава 6.7](../../06-console/ru/spec/06.7-console.norms.md).
Договора библиотеки у урока нет — это процесс с HTTP-дверью (`SIGNER_URL`). Общие алгоритмы урока — договоры
`common/contracts/` (`keys`, `domain-token`, `domain-envelopes`, `accept`, `may`, `record`, `ask-sig`) и их векторы
`common/vectors/`:

```text
README.md                             этот файл
spec/08.0-domain.norms.md             нормы главы 8.0 — двери процесса: один писатель, приём правок консоли домена, класс signed
spec/08.1-domain.norms.md             нормы главы 8.1 — вид домена и теневой режим
spec/08.2-domain.norms.md             нормы главы 8.2 — корень, набор ключей, ключ приёма книг, смена и отзыв без связи
spec/08.3-domain.norms.md             нормы главы 8.3 — приём отчётов
spec/08.4-domain.norms.md             нормы главы 8.4 — люди и гранты
spec/08.5-domain.norms.md             нормы главы 8.5 — книги и индекс имён
spec/08.6-domain.norms.md             нормы главы 8.6 — назначение и правки
spec/08.7-domain.norms.md             нормы главы 8.7 — выдача токенов воркеров
spec/08.8-domain.norms.md             нормы главы 8.8 — срок, резервная копия, перенос и передача
spec/08.9-domain.norms.md             нормы главы 8.9 — общий документ и история тревог
spec/08.10-domain.norms.md            нормы главы 8.10 — очередь и цена
spec/08-domain.api.openapi.yaml       двери (один контракт урока)
spec/08-domain.README.md              инструкция реализации
lifecycle.md                          флаги, окружение, коды выхода, юниты
data/<семья>.schema.json, .layers.tsv, .outcomes.tsv
                                      семьи данных, которыми урок владеет (JSON Schema 2020-12, ADR-0092; ADR-0088): idem (8.0); view, shadow,
                                      view-rows, member-tables, ref-claims (8.1); keys, root, signer, signer-pending, book-seal, revoked,
                                      issued (8.2); members, member-report, member-report-delta, member-reported, member-ca-certs, topology,
                                      batches, knocks, member-count, relay-members (8.3); users, deleting, disabled, grants, break-glass,
                                      anywhere, groups, roles (8.4); book, names-index, book-all, book-keys, book-part, domain-folders,
                                      domain-memberof, folder-counts, folder-log, folder-rev, folder-units, folder-units-head (8.5);
                                      placement, placement-record, pending, outcomes (8.6); holder, keepers, backups, stranded,
                                      backup-parts, from-nothing, move-ask, partial (8.8); shared, shared-docs, alarm-history (8.9);
                                      signer-turn (8.10)
data/refusal-words.tsv                закрытый перечень слов error по дверям процесса (ADR-0094 B5)
vectors/<алгоритм>/                   векторы: view (8.1), assemble (8.5), issue (8.7)
acceptance/<K>/                       приёмка главы K: 1, 3 … 10 — главы 8.1, 8.3–8.10 (README.md, scenarios.tsv; 3/inputs/);
                                      0/ и 2/ содержат только швы пакета, обычный каталог не изменён (8.2 — векторы общих пакетов, N5 главы)
ru/                                   для человека, в выгрузку не входит — лекция ru/08-domain.md, переводы английского текста тем же путём
```

У главы 8.0 обычного каталога сценариев нет: её исходы проверяют главы 8.3, 8.8 и 8.10 и чтение (N5).

Формы пакета и [швы](forms/README.md#швы-и-этапы), включая новые каталоги только швов acceptance/0 и acceptance/2, помогают разработке. Обычный каталог сценариев не меняется, швы не заменяют исходные обязанности глав и полный стенд.
