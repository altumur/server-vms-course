# Черновик G06: вариант приёмки 2.5 `v10-worker-domain-reads` — расширения `worker.reads`, источники собираемых книг `domain.books.<книга>.from` и условные чтения `domain/*` у воркера

Норма: `P/02.5` Н1.4 строка `<s>worker` и Н3 шаг 3:
- `domain/placed/<sub>/` в `worker.reads` дополнительно даёт `domain/placement/<sub>/` с сохранением `domain/placed/<sub>/`;
- копия своей книги `domain/<sub>/<книга>` в `worker.reads` (или `secrets.reads`) дополнительно даёт точный ключ `domain/<sub>/<книга>/<CLUSTER>` (по умолчанию `CLUSTER=local`), но не префикс `domain/<sub>/<книга>/*` (`C02-OWN-BOOK-HOLDER-01`);
- воркер получает `write` на источники собираемых книг своего манифеста (`domain.books.<книга>.from`: с `/` на конце → префикс `<s>/<строка>/*`, без `/` → точный ключ `<s>/<строка>`);
- воркер получает `read` на `domain/shared` при `domain.shared` (или `domain.tokens.<вид>.scenario`), на `domain/topology` и `domain/member-topology` при `domain.tokens.<вид>.unit`, на `domain/grants` при `door.routes`.

Файлы варианта:
- `variants/v10-worker-domain-reads/va.subsystem.yaml`
- `variants/v10-worker-domain-reads/vb.subsystem.yaml`
- `variants/v10-worker-domain-reads/expect.tsv`
