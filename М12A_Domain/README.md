# Модуль 12A — остатки о VMS к М12 и М13

Домен платформы переведён в нормативный модуль [М11 «Домен»](../Platform/README.md) (ныне уроки P/08–P/10 «Платформы»): уроки 1–12, у каждого —
нормы, контракт, инструкция и приёмка. Прежние уроки этого модуля сняты в тех коммитах, где их содержание перенесено
(ADR-0003: двух версий одной нормы нет). Основание «у домена нет базы» — [`where-the-database-lives.md`](../where-the-database-lives.md).

Здесь остаются только части о видеопродукте, на которые ссылается [М12B](../М12B_DomainVMS/README.md), и урок, который
переводится в М13. Каждый остаток помечен и снимается тогда, когда его переведут — вместе со слоем VMS после стадии C
(ADR-0080 доп. (20)). До перевода тексты не правятся: платформенное в них — устаревший пересказ, действующее — P/02.4
и уроки P/08–P/10; лицензия — дело продукта (там же), строки `domain/licence` у платформы нет.

| № | Остаток | К чему | Платформенное — нормативно |
|---|---|---|---|
| 3 | [Шлюз живого видео и одна подписка](03-the-api-and-what-it-refuses.md) | М12 | [P/08.1](../Platform/08-domain/spec/08.1-domain.norms.md), [P/10](../Platform/10-domain-console/spec/10-domain-console.norms.md), [P/08.3](../Platform/08-domain/spec/08.3-domain.norms.md), [P/09.1](../Platform/09-agent/spec/09.1-agent.norms.md), [P/08.6](../Platform/08-domain/spec/08.6-domain.norms.md), [P/06.7](../Platform/06-console/spec/06.7-console.norms.md) |
| 5 | [Упаковка, обновления и лицензия](05-packaging-updates-and-the-licence.md) | М13 (ADR-0080 доп. 4) | — |
| 10 | [Камера как кластер из одного](10-a-cluster-of-one.md) | М12 | [P/02.4 Н1.10](../Platform/02-installer/spec/02.4-installer.norms.md), [P/08.10](../Platform/08-domain/spec/08.10-domain.norms.md), [P/09.1 Н1.11](../Platform/09-agent/spec/09.1-agent.norms.md) |
| 12 | [Сценарии между камерами](12-shared-settings-without-a-database.md) | М12 | [P/08.9](../Platform/08-domain/spec/08.9-domain.norms.md), [P/06.7 Н1.14](../Platform/06-console/spec/06.7-console.norms.md) |
| 13 | [Свидетель молчания у VMS](13-alarms-from-every-member.md) | М12 | [P/09.1 Н1.10](../Platform/09-agent/spec/09.1-agent.norms.md), [P/10 Н1.8](../Platform/10-domain-console/spec/10-domain-console.norms.md), [P/08.9 Н1.9](../Platform/08-domain/spec/08.9-domain.norms.md) |

Размещение по достижимости (шаги 4–5 прежнего урока 1) — долг урока М11/6 в `ХОД-Спецификация.md`.
