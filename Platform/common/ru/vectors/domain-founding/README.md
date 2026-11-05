# Векторы: основание домена

Текст производный от `vectors/domain-founding/README.md`, руками не правится: источник — английский [`vectors/domain-founding/README.md`](../../../vectors/domain-founding/README.md), правка идёт в него, русский пересобирается переводом (ADR-0121; ADR-0124 доп. (1) п. 4).

Владелец — [договор основания домена](../../contracts/domain-founding.md) (находка «Спецификации» I02-FOUND, решение
«Архитектора» 2026-10-23). Участники — установщик (P/02.4 Н3 «установка домена», команды смен) и процесс `domain`
держателя (запись срока 1). Ключи порождены из постоянных байтов (`sha256("w2c test <слово>")`); байты пишет «Спецификация».

UTF-8, LF, поля через TAB; строки с `#` и пустые пропускаются; первая непропущенная — заголовок `case<TAB>…<TAB>expect<TAB>note`.

| Файл | Вход → ожидание |
|---|---|
| [`recovery.tsv`](../../../vectors/domain-founding/recovery.tsv) | `input` — `{file, mode}`: содержимое файла восстановления JSON и его режим (восьмеричный, строкой) → `{domain, root_pub, fingerprint}` прочитанного файла или `@refuse` — файл не читается, ничего не меняется |
| [`book-seal.tsv`](../../../vectors/domain-founding/book-seal.tsv) | `seed_secret` hex 32 байт → `book_seal` = X25519(seed, 9) hex |
| [`claim.tsv`](../../../vectors/domain-founding/claim.tsv) | `input` — `{issuing_key_secret, domain, holder, url, at}` → строка `domain/holder` `{doc}`, где `doc` — текст JCS документа записи срока 1 с `issuer`, `kid`, `sig` (Ed25519 детерминирован, RFC 8032) |

Кто исполняет: `recovery.tsv` и `book-seal.tsv` — установщик (`02-installer`, команды установки и смен); `claim.tsv` —
процесс `domain` держателя (`08-domain`): запись срока 1 пишет только он (ACC-VECTORS-CONNECT-02, решение «Архитектора» 2026-10-26).

Сторона вычисляет своим кодом и сравнивает: `recovery.tsv` и `claim.tsv` — JSON по значению (`doc` — байт в байт), `book-seal.tsv` — строку.

## Провод векторов

Провод таблиц `book-seal.tsv`, `recovery.tsv` задают строки `common/domain-founding` в [единой форме](../../../vectors/wire.tsv); [грамматика](../wire.md). Форма — источник шапки, выбранных входов, фикстур, нативного исхода и сравнения. Смысл алгоритма и обязанность потребителя остаются здесь.

`claim.tsv` не входит в этот срез формы: её нативный исход остаётся объектом строки `domain/holder` по общему договору Vectors.
