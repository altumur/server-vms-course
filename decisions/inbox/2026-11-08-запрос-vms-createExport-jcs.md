# Исполнение отдельного поручения: хеш тела createExport, ADR-0119 (3) п.3

Автор: «Спецификация VMS». Ветка `vms/export-body-jcs-20261108`.
База: `d4d758d567bc7f7f977d29cf18350796f7fc75c9`.
Основание: прежнее прямое уточнение Архитектора о точном JCS-хеше и двух исключаемых
полях, отдельно от repin; слово владельца 8 ноября о продолжении сохранённых поручений.
Работа до результата по ADR-0083 (139). Это авторская правка, не запуск VMS-review.

## Происхождение и правило

В базе d4d758d56 пункт ADR-0119 (3) п.3 остаётся НЕТ НОРМЫ. V/11.4 Н1.4 определяет
body как SHA-256 байтов запроса, V/11.20 Н1.2 отсылает к этому правилу без исключения
двух парольных полей. Следовательно, пробелы и пароли могли менять вход сравнения,
а дайджест мог стать проверочным значением пароля. Пробел нормы был в базе;
его причинность более ранним коммитам здесь не приписывается.

В V/11.20 Н1.2 записано уже решённое правило: только createExport получает
lowercase hex SHA-256 от UTF-8 JCS копии разобранного тела после удаления ровно
password и supervisor.password. Отсутствующие поля ничего не добавляют и не удаляют;
другие поля, объект supervisor и порядок массивов сохраняются. Оригинальное тело
продолжает использоваться проверками и выгрузкой. JCS — RFC8785 целиком, как у платформы.
В V/11.4 Н1.4 добавлена только ссылка на специальный случай createExport; определение
дайджеста других операций, ключ h, срок памяти, CAS, коды и повтор результата сохранены.

Изменены оба источника и их ru-зеркала, пункт V/11.20-02 и ссылка Н5 на новые векторы.
Адреса норм и checklist ids сохраняются. Строка НЕТ НОРМЫ закрыта точной записью
«решение Архитектора по ADR-0119 (хеш тела createExport)»; norms_to и прочие счётчики
pipeline не продвигаются. Журнал приёмки главы4 отмечает добавление векторов.

## Векторы и связанные места

Новый пакет VMS/11-backend/vectors/export-repeat-digest содержит cases.tsv из16 строк
и инструкцию с производным ru-зеркалом. Колонки raw/canonical/sha256 задают точные
байты;15 связей same/different дополнительно фиксируют результат сравнения.

Проверены смена каждого пароля отдельно и обоих вместе, отсутствие root password,
перестановка ключей и пробелы, Unicode escapes, равнозначная числовая запись;
различия имени, supervisor.login, значения и порядка камер, границы периода,
комментария с password-подобным словом. При отсутствии обоих путей тело используется
как есть; отсутствующий supervisor не создаётся. Все пароли — синтетические строки.

Область связанных изменений: repeats/body и ветка createExport — изменены;
request/body, ExportCreate, права и надзор, срок памяти и гонки — согласованы без
изменения; данные исходной приёмки45-export и её методы — прежние. Другие операции
повторов не переводились на JCS этой правкой. Новых дверей, CLI, схем, конфигураций,
форм генераторов или поведения ошибок не вводилось.

Контракт consolem.openapi.json, backend.shell.html, манифест backend, остальные
подсистемы, id-map, Source, Platform, tools и skills сохранены. Перепин6dcc,
нормы9f95, учёт0d467 и уже принятый English16 не смешаны с этой веткой.

## Авторские проверки и пределы

Основание проверок — новые байты нормы и нового набора данных. Прежние квитанции,
архивы и завершённые прогоны для входа не повторялись.

- Три затронутые пары en/ru — en_mirror без ошибок.
- Python:16 деревьев после удаления полей совпали с canonical, все UTF-8 SHA-256
  совпали с sha256 таблицы;16 исходных JSON соответствуют закреплённой ExportCreate.
- Отдельная проверка Node стандартными JSON/crypto:16 canonical/hash,15 отношений;
  восемь намеренно неверных вариантов обработки отвергнуты этими данными. Это
  контроль покрытия эталонов, не мутанты реализации backend или существующего судьи.
- Проверены12 новых локальных ссылок, ровно11 разрешённых файлов, неизменность остальных
  исходных байтов и16 digest по прежнему полю манифеста с pattern ^[0-9a-f]{64}$.
  Диффы четырёх норм сведены обратно к базе удалением только заявленных вставок;
  ledger меняет ровно одну строку, журнал только дополняется. Staged boundary и
  diff --check PASS; range/pre-push выполняются обычным порядком без обхода.

Локальная копия новой проверки: cammeta-status/spec-vms-export-body-jcs-20261108/,
check-vectors.js, vectors.log и RESULT.json. Точная программа и stdout ниже входят
в опубликованный Git-отчёт: для приёмки CT103 доступ к маку не требуется. Эталоны на текущем подмножестве входов независимо
сверены ECMAScript- и Python-сериализацией/хешированием; полного повторного прогона
общего пакета RFC8785 не было, его прежние доказательства не переоцениваются.

Backend/SUT, модель, кластер, VMS-review, Owner-only trials и полный курс не запускались.
Новый авторский источник не означает принятия V/11, готовности всей VMS или общего GATE.
По (139) источник передаётся одному принимающему coord103-src; Диспетчеру — итог и
зависимости. Новый смысл уже не требуется: применено прежнее точное решение Архитектора.

## Приложение: новая авторская проверка данных

Это программа проверки эталонов, не код реализации backend и не новый судья курса.
Параметр — путь vectors/export-repeat-digest/cases.tsv от корня V/11.

```javascript
const fs = require('node:fs');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const path = process.argv[2];
const lines = fs.readFileSync(path, 'utf8').trimEnd().split('\n');
assert.equal(lines.shift(), 'case\traw\tcanonical\tsha256\trelation\tnote');
const rows = lines.map(line => {const a=line.split('\t');assert.equal(a.length,6);return {id:a[0],raw:a[1],expected:a[2],sha:a[3],relation:a[4]};});
// This independent data check uses ECMAScript scalar serialization and UTF-16 property ordering.
function jcs(v) {
  if (Array.isArray(v)) return '['+v.map(jcs).join(',')+']';
  if (v !== null && typeof v==='object') return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+jcs(v[k])).join(',')+'}';
  return JSON.stringify(v);
}
function remove(v) { delete v.password; if(v.supervisor && typeof v.supervisor==='object' && !Array.isArray(v.supervisor)) delete v.supervisor.password; return v; }
const hash = s=>crypto.createHash('sha256').update(Buffer.from(s,'utf8')).digest('hex');
const results=new Map();
for(const row of rows) {
  assert(!results.has(row.id));
  const input=JSON.parse(row.raw); const projected=remove(JSON.parse(row.raw));
  const canonical=jcs(projected);assert.equal(canonical,row.expected,row.id+' canonical');
  assert.equal(hash(canonical),row.sha,row.id+' SHA');assert.match(row.sha,/^[0-9a-f]{64}$/);
  assert(!Object.hasOwn(projected,'password'));
  assert(!projected.supervisor || !Object.hasOwn(projected.supervisor,'password'));
  assert.equal(JSON.stringify(input),JSON.stringify(JSON.parse(row.raw)));
  results.set(row.id,row.sha);
  console.log('PASS',row.id,Buffer.byteLength(canonical,'utf8'),row.sha);
}
for(const row of rows) if(row.relation!=='-') {
  const [relation,id]=row.relation.split(':');assert(results.has(id));
  if(relation==='same')assert.equal(row.sha,results.get(id),row.id+' relation');
  else {assert.equal(relation,'different');assert.notEqual(row.sha,results.get(id),row.id+' relation');}
}
const mutations={
  rawBytes:r=>hash(r.raw),
  noRemoval:r=>hash(jcs(JSON.parse(r.raw))),
  rootOnly:r=>{const v=JSON.parse(r.raw);delete v.password;return hash(jcs(v));},
  nestedOnly:r=>{const v=JSON.parse(r.raw);if(v.supervisor)delete v.supervisor.password;return hash(jcs(v));},
  dropSupervisor:r=>{const v=remove(JSON.parse(r.raw));delete v.supervisor;return hash(jcs(v));},
  sortCameras:r=>{const v=remove(JSON.parse(r.raw));v.cameras.sort((a,b)=>a.uid.localeCompare(b.uid));return hash(jcs(v));},
  introduceSupervisor:r=>{const v=remove(JSON.parse(r.raw));if(!v.supervisor)v.supervisor={};return hash(jcs(v));},
  erasePasswordWord:r=>{const v=remove(JSON.parse(r.raw));if(v.comment && /password/i.test(v.comment))delete v.comment;return hash(jcs(v));}
};
for(const [id,mutate] of Object.entries(mutations)) {
 const witness=rows.find(r=>mutate(r)!==r.sha);assert(witness,id+' survives data vectors');
 console.log('DATA_VARIANT_REJECTED',id,'witness',witness.id);
}
console.log('PASS rows='+rows.length+' relations='+rows.filter(r=>r.relation!=='-').length+' incorrect-data-variants='+Object.keys(mutations).length+'; no backend/SUT executed');
```

Фактический stdout, exit0:

```text
PASS base 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS root-password 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS supervisor-password 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS both-passwords 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS root-password-absent 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS key-order-spaces 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS escaped-unicode 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS number-spelling 403 c489988da2c5d5b3e777694a9ef014e0d109001ef568c2a941c25e41e13862d4
PASS name-change 408 0db57b3b523e55376f65012ae2304eca6cb4e72e3d220a74b61486426847c7c9
PASS supervisor-login 408 cae7f54e54ec0c986a50cdae1a6db3096a6a4900d3b5773eeae7b7ca0b9620f7
PASS camera-order 403 df0afe49e0c993e4180d7543c271bbf5a3e609f0bc9015a0a5ca8c99e6bd6877
PASS camera-value 403 d2737003f718cf4357eb685386f8ccb6e2cf37a9ad0a01f6162f5e759dcf24be
PASS period-value 403 68677bcd05678c4070e90ff764b20096477edb71319cdc9adaed6631d4fdc70e
PASS comment-value 384 69be7cd83ec3c2cb16b66a6bbb349029d801effad416990ac61209b4e9af6b8f
PASS no-password-fields 362 d81a2d1e8585360afb4523dd68c0682783e301a3da4f21ad72f3432e53481587
PASS password-no-supervisor 362 d81a2d1e8585360afb4523dd68c0682783e301a3da4f21ad72f3432e53481587
DATA_VARIANT_REJECTED rawBytes witness base
DATA_VARIANT_REJECTED noRemoval witness base
DATA_VARIANT_REJECTED rootOnly witness base
DATA_VARIANT_REJECTED nestedOnly witness base
DATA_VARIANT_REJECTED dropSupervisor witness base
DATA_VARIANT_REJECTED sortCameras witness camera-order
DATA_VARIANT_REJECTED introduceSupervisor witness no-password-fields
DATA_VARIANT_REJECTED erasePasswordWord witness base
PASS rows=16 relations=15 incorrect-data-variants=8; no backend/SUT executed
```
