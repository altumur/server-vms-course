# Модуль 12A — остатки о VMS к М12 и М13

Домен платформы переведён в нормативный модуль [М11 «Домен»](../М11_Domain/module-design.md): уроки 1–12, у каждого —
нормы, контракт, инструкция и приёмка. Прежние уроки этого модуля сняты в тех коммитах, где их содержание перенесено
(ADR-0003: двух версий одной нормы нет). Основание «у домена нет базы» — [`where-the-database-lives.md`](../М11_Domain/where-the-database-lives.md).

Здесь остаются только части о видеопродукте, на которые ссылается [М12B](../М12B_DomainVMS/README.md), и урок, который
переводится в М13. Каждый остаток помечен и снимается тогда, когда его переведут.

| № | Остаток | К чему | Платформенное — нормативно |
|---|---|---|---|
| 3 | [Шлюз живого видео и одна подписка](03-the-api-and-what-it-refuses.md) | М12 | [М11/1](../М11_Domain/01-what-a-cluster-cannot-know.md), [М11/3](../М11_Domain/03-agent-and-reports.md), [P/08.6](../Platform/08-domain/spec/08.6-domain.norms.md), [М11/8](../М11_Domain/08-doors-between-clusters.md) |
| 5 | [Упаковка, обновления и лицензия](05-packaging-updates-and-the-licence.md) | М13 (ADR-0080 доп. 4) | — |
| 10 | [Камера как кластер из одного](10-a-cluster-of-one.md) | М12 | [P/02.4 Н1.10](../Platform/02-installer/spec/02.4-installer.norms.md), [P/08.10](../Platform/08-domain/spec/08.10-domain.norms.md), [P/09.1 Н1.11](../Platform/09-agent/spec/09.1-agent.norms.md), [М11/3](../М11_Domain/03-agent-and-reports.md) |
| 12 | [Сценарии между камерами](12-shared-settings-without-a-database.md) | М12 | [М11/11](../М11_Domain/11-shared-settings-and-alarms.md) |
| 13 | [Свидетель молчания у VMS](13-alarms-from-every-member.md) | М12 | [М11/11](../М11_Domain/11-shared-settings-and-alarms.md) |

Размещение по достижимости (шаги 4–5 прежнего урока 1) — долг урока М11/6 в `ХОД-Спецификация.md`.
