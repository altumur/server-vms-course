# Переподписание записей домена каноном RFC 8785, 2026-10-11 (ADR-0072)

Стенд vms-macos, продукт main afbd6fb (канон подписей — JCS, trust/jcs.go; таблица testdata/canonical_json.tsv).
Выкладка, затем две плановые передачи срока — каждая подписывает запись держателя, набор ключей и копии новым
каноном: srv (срок 10) → relay-a (11) → srv (12). Проверка: все девять членов на сроке 12 читают запись держателя
(`/api/held`), агенты следуют за ним без отказов подписи.

```
== stand afbd6fb (JCS): srv term 10 → relay-a term 11 → srv term 12, planned handovers
handover 1: передача по плану: срок 11 на relay-a, состояние домена rev 515 с srv; ничего не брошено
handover 2: передача по плану: срок 12 на srv, состояние домена rev 15 с relay-a; ничего не брошено
srv term 12 holder srv copy {'term': 11, 'rev': 15}
cam-a term 12 holder srv copy {'term': 10, 'rev': 515}
cam-b term 12 holder srv copy {'term': 6, 'rev': 474}
cam-c term 12 holder srv copy {'term': 9, 'rev': 13}
cam-demo term 12 holder srv copy {'term': 6, 'rev': 438}
relay-a term 12 holder srv copy {'term': 10, 'rev': 515}
relay-b term 12 holder srv copy {'term': 12, 'rev': 516}
relay-c term 12 holder srv copy {'term': 12, 'rev': 516}
relay-b2 term 12 holder srv copy {'term': 6, 'rev': 484}
```
