# Задачи adr-0110-folders

ADR-0110 разбор, шаг 6, Д-5; ADR-0111 п. 13. Реализацией не прогнано. Сценарии стенда — шаг 11 разбора. Отказ V/11 `422` со словом — дело Спецификации VMS, платформа отдаёт 503 пересылки.

| Код | Что менять | Спец. | Go | Python |
|---|---|---|---|---|
| C08-SHARED-FOLDERS-01 | семьи `domain/folders/<id>`, `domain/memberof/…`, `domain/folder-rev`, двери, права | [x] | [ ] | [ ] |
| C08-SHARED-FOLDERS-01 | `carry.folders`, копия агента, `domain/folders-state`, `gone`, `own`, `scope` | [x] | [ ] | [ ] |
| C08-SHARED-FOLDERS-01 | консоль члена: запись папок 409 `folders are the domain's`, запрет строк в пакете, без жнеца, `platform/memberof-gone` | [x] | [ ] | [ ] |
| C08-SHARED-FOLDERS-01 | перенос: три семьи в `state`, `folder-rev` парой {term, rev}, `own` с подъёмом до `carry.folders` | [x] | [ ] | [ ] |

Вливание стопки связано с шагом 8: папки V/11 пишут `POST /folders` и `folderId` в пакете, у члена домена это 409 и `badkey`.
