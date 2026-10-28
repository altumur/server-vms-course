# Процесс domain — урок P/08

Микромодуль: процесс domain держателя. Что нормирует и откуда — [записка модуля](../module-design.md), таблица «Уроки».

Раскладка каталога (после переноса, стадия B). Урок собран из сторон держателя уроков М11/1–12; стороны агента и
ретранслятора — урок P/09, консоли домена — урок P/10, поздний слой консоли кластера — [глава 6.7](../06-console/spec/06.7-console.norms.md).
Договора библиотеки у урока нет — это процесс с HTTP-дверью (`SIGNER_URL`). Общие алгоритмы урока — договоры
`common/contracts/` (`keys`, `domain-token`, `domain-envelopes`, `accept`, `may`, `record`, `ask-sig`) и их векторы
`common/vectors/`:

```text
08-domain.md                          лекция
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
data/<семья>.schema.json, .outcomes.tsv схемы семей (JSON Schema, ADR-0092; ADR-0088): view, shadow (8.1); keys, root, signer,
                                      signer-pending, book-seal, revoked (8.2); members, member-report,
                                      member-report-delta, member-reported, member-ca-certs, topology (8.3); users,
                                      deleting, disabled, grants, break-glass (8.4); book, names-index (8.5); placement,
                                      placement-record, pending, outcomes (8.6); holder, keepers, backups, stranded (8.8);
                                      shared, shared-docs, alarm-history (8.9); signer-turn (8.10)
vectors/<алгоритм>/                   векторы: view (8.1), assemble (8.5), issue (8.7)
acceptance/1/, 3/ … 10/               приёмка глав 8.1, 8.3–8.10 (README, scenarios.tsv, corrections.tsv; 3/inputs/);
                                      у глав 8.0 и 8.2 каталога нет (8.2 — векторы общих пакетов, Н5 главы)
```

У главы 8.0 каталога приёмки нет: её исходы проверяют сценарии глав 8.3, 8.8 и 8.10 и чтение (Н5 главы).
