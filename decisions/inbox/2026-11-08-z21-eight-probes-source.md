# З21: Source привязки восьми исполняемых проб

Основание: whole139 task ee13eaf5/authority02a0; дословные находки владельца bbf445f1. Текст Source a08 используется как принятая исходная норма, без повторной проверки Source/32fixtures/архивов.

Новый смысл только для п.5 выбран Архитектором в ADR-0130(2), 4e139168: новая причина отказа второго демона на каталоге живого владельца, общий код старта по форме, отдельная CLI причина локальных операций, журнал с каталогом и отказ до любой записи/готовности. Владение кончается с процессом; ручная уборка после штатного выхода или SIGKILL не нужна. Импорт группы через своего живого лидера не превращается в запрещённый внешний второй процесс.

П.7 — действующий R054 и RFC9112§6.1: корректный HTTP/1.1 CL+TE читается как chunked и закрывается после ответа; это не автоматический400. HTTP/1.0 с TE — ошибочная рамка400/закрытие. П.8 подтверждён Архитектором как чтение R028/copy/R018/R033/H03: unreadable с целой версией включается в backup, index_lost требует журнала/ненулевого backup/сохранения прежнего файла;503 до200 либо неполный обрыв после200 допустимы, завершённая копия с пропуском/выдуманной версией — нет. Import/restore unreadable по N4 — отдельно.

Девять Source носителей: EN/RU нормы01.3, lifecycle и acceptance README1/3, forms/refusals.tsv. Две строки каталога start_data_dir_owned/local_data_dir_owned; флаги/дефолты/HTTP/API/Fault классы/профиль2/assembly1 и прежние cases/expectations/Source/VMS не меняются. Комплект ADR0122 MODIFIED только R006/R029, state review; unmarked Implementation decides/checklist и README представлены в полной raw карте, не приписаны R030.

Внешний пакет z21-eight-probes-source-a08-20261108 содержит83 anchors/14 Source inputs, полную Source-native карту1–8, точные17 groups/11measurement definitions, буквальные находки и отдельные MissingBindings. Исходные карты с прежним вопросом п.5 сохраняются; новое решение перекрывает только этот вопрос. Native executable/profile/fault/clock/storage/capacity не получены — это точные отсутствующие входы, не PASS.

Runner — единственный писатель исполняемых probes. Финальная сверка только его новых literals и конкретных bindings выполняется в этой же задаче; Source/архивы/старые32 не replay. Само наличие Source/registration/контролей не означает кандидата/17groups/production/GATE. Candidate implementation/oracles не читались; Go/HTTP/SUT/Ownertrials/models/work/keys/pins не запускались и не менялись; budgets null/provider UNKNOWN.
