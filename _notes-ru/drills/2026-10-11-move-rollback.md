# Учение переноса домена с резервом, 2026-10-11 (ADR-0066 доп. 2026-10-10 и 2026-10-11)

Стенд vms-macos, продукт `altumur/vmssubsystem`. Девять кластеров: srv, relay-a/b/c/b2, cam-a/b/c, cam-demo.
Переносы — `w2cctl domain move <консоль> recovery/domain-root.json`, передача — `POST /domain/handover {to}`.

## Что увидели (main 1277b1e, term 6 → 8)

1. Выкладка 1277b1e: консоль говорит копию своего кластера. До неё `/api/held` у relay-a отвечал `backup: null`,
   хотя relay-a держал копию term 6 rev 410. Роль console не читала `domain/backup`, и `/api/backup` отвечал
   подписанному члену нулями, то есть «копии нет».
2. Перенос srv → relay-a (term 7): копия соседа дошла, восстановлено из cam-a term 6 rev 501. srv ответил 403.
3. Перенос relay-a → srv (term 8): все восемь соседей ответили srv 403, потому что srv не было ни в одном списке
   членов. В списке relay-a (rev 14) не было srv, в списке srv (rev 15) не было relay-a: держатель не вносил себя,
   а перенос вносил держателя той копии, из которой восстановился, а не того, кого сменил. srv восстановился из
   своей старой копии term 5 rev 7. **Домен откатился молча.** Следом srv отказал relay-a («no key at the domain»):
   в rev 7 нет его ключа. Копии term 8 ушли relay-b и relay-c. Копия term 6 rev 501 осталась только у cam-a.

## Починка (main d1beca0, blocker)

- Копия новее выбранной, которую сосед объявил в `/api/held` и не отдал (403/401/503), — отказ переноса 409
  с перечнем.
- `copy: {term, rev}` и `why` — восстановить ровно эту копию у любого соседа, который её держит. `copy` или
  `stolen` — явное слово, строка журнала `domain.moved`.
- После переноса прежний держатель остаётся членом с ключом из подписанных им копий (`HolderKey`), новый
  держатель вносит себя со своим ключом.

## Восстановление стенда (main d1beca0)

Ручных правок хранилищ не было: только перенос с названной копией и передача по гранту. Спасённая на время копия
rev 501 с открытыми секретами (у srv не было ключа бэкапа) удалена после шага 3.

```
== before (main d1beca0 on the stand)
srv holder srv term 8 copy {'term': 5, 'rev': 7}
cam-a holder srv term 6 copy {'term': 6, 'rev': 501}
cam-b holder srv term 8 copy {'term': 6, 'rev': 474}
cam-c holder srv term 8 copy {'term': 5, 'rev': 7}
cam-demo holder srv term 6 copy {'term': 6, 'rev': 438}
relay-a holder srv term 8 copy {'term': 6, 'rev': 410}
relay-b holder srv term 8 copy {'term': 8, 'rev': 508}
relay-c holder srv term 8 copy {'term': 8, 'rev': 508}
relay-b2 holder srv term 8 copy {'term': 6, 'rev': 484}
== step 2: move to relay-a, copy=6.501
domain move: 200 {'holder': 'relay-a', 'term': 9, 'restored_from': 'cam-a', 'rev': 501, 'ignored': ['cam-b: its copy of the backup: 403 ', 'cam-c: its copy of the backup: 403 ', 'cam-demo: its copy of the backup: 403 ', 'relay-b: its copy of the backup: 403 ', 'relay-c: its copy of the backup: 403 ', 'relay-b2: its copy of the backup: 403 ', 'srv: its copy of the backup: 403 '], 'detail': None, 'error': None}
== after step 2
srv holder relay-a term 9 copy {'term': 5, 'rev': 7}
cam-a holder relay-a term 9 copy {'term': 6, 'rev': 501}
cam-b holder relay-a term 9 copy {'term': 6, 'rev': 474}
cam-c holder relay-a term 9 copy {'term': 5, 'rev': 7}
cam-demo holder srv term 6 copy {'term': 6, 'rev': 438}
relay-a holder relay-a term 9 copy {'term': 6, 'rev': 410}
relay-b holder relay-a term 9 copy {'term': 8, 'rev': 508}
relay-c holder relay-a term 9 copy {'term': 8, 'rev': 508}
relay-b2 holder relay-a term 9 copy {'term': 6, 'rev': 484}
== step 3: planned handover relay-a -> srv (POST /domain/handover {to: srv} at relay-a's console)
{'term': None, 'holder': None, 'restored_from': None, 'rev': 13, 'ignored': None, 'error': None, 'detail': None, 'sentence': 'передача по плану: срок 10 на srv, состояние домена rev 13 с relay-a; ничего не брошено'}
== after step 3
srv holder srv term 10 copy {'term': 9, 'rev': 13}
cam-a holder srv term 10 copy {'term': 6, 'rev': 501}
cam-b holder srv term 10 copy {'term': 6, 'rev': 474}
cam-c holder srv term 10 copy {'term': 9, 'rev': 13}
cam-demo holder srv term 10 copy {'term': 6, 'rev': 438}
relay-a holder srv term 10 copy {'term': 6, 'rev': 410}
relay-b holder srv term 10 copy {'term': 9, 'rev': 13}
relay-c holder srv term 10 copy {'term': 9, 'rev': 11}
relay-b2 holder srv term 10 copy {'term': 6, 'rev': 484}
srv members rev 17 {'cam-a': True, 'cam-b': True, 'cam-c': True, 'cam-demo': True, 'relay-a': True, 'relay-b': True, 'relay-b2': True, 'relay-c': True, 'srv': True}
== saved copy with opened secrets removed: recovery/domain-rev501-2026-10-11 (10:29:18 UTC)
{"by":"the recovery file","copy":{"rev":501,"term":6},"id":"domain-e0-mv3oigq71no-5","kind":"domain.moved","restored_from":"cam-a","restored_rev":501,"restored_term":6,"stolen":false,"t":1791714491.4596732,"target":"domain/relay-a","term":9,"why":"term 8 rolled the domain back to term 5 rev 7 (srv restored its own copy, every neighbour refused it): restore the newest state, term 6 rev 501, kept by cam-a"}
```

Итог: девять членов на term 10 у srv, состояние — rev 501 (term 6) и всё, что после. Список srv (rev 17) — все
члены с ключами, включая relay-a и сам srv. Для курса: тот же сценарий с тремя кластерами — держатель A, перенос
на B, обратно на A — без `copy` должен отказать на возврате, если B объявил копию новее, а A её не прочёл.
