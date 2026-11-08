# Формы входа функций may и covers

Этот русский текст — производный от `contracts/may-input.md`, руками не правится (ADR-0121).

Это прежние формы входа общих функций [may](may.md#функция-may) и [covers](gate-and-pass.md). Они задают вход функции и смысл кодов выхода, не новый маршрут продукта, поле profile или команду. Значения случаев и ожидаемые ответы остаются у судьи.

## may

Вход — один объект JSON. Шаги функции и вывод задаёт [договор права](may.md#функция-may); доверенная строка выдачи и Time строки остаются у прежних владельцев. Вся форма входа проверяется до шагов функции.

```yaml
input:     объект JSON; обязательны восемь полей grants, as_of, disabled, user, glass, cap, unit, now; необязательны sub, roles,
           unread, iat, anywhere, as_role (ADR-0097–ADR-0100, ADR-0105, ADR-0110; поля нет — null, у unread — []); поля сверх них не читаются (не отказ)
grants:    null | ровно {lines: [line…]}
line:      ровно {subject, cap, sub?, scope, until, by} — доверенный вход (копия, уже разобранная по P/08.4 N1.3): строка не по
           форме — вход не по форме, код 2, не пропуск
  subject: по форме P/08.4 doc.lines[].subject — непустая, 1–64 знака без пробельных (White_Space Unicode 15.0.0),
           управляющих и : | ( ) " /, не break-glass; subject "" — вход не по форме, код 2 (догадка стадии C MAY-G03, решение «Архитектора» 2026-10-23);
           либо role: и имя той же грамматики, кроме admin (ADR-0098 §2, ADR-0100 §1)
  cap:     none | view | edit | admin; none — только у строки роли (ADR-0099 §1)
  sub:     имя манифеста [a-z][a-z0-9_-]{0,31} (P/02.1); platform проходит ту же грамматику
  scope:   "*" | "unit:<sub>/<id>" | "labels:<метка>[,<метка>…]" | "folder:<id>"; у строки роли labels: не по форме (ADR-0099 §1);
           <id> папки — 32 строчные hex-цифры (P/06.8 N1.1); <sub> — имя манифеста [a-z][a-z0-9_-]{0,31} (P/02.1),
           <id> — по договору проверки строки «Идентификатор и ограничения полей» named (`unit:testsub/a,b` — 2),
           метка — по договору азбуки меток
  until:   время — 0 или неотрицательное число JSON по нынешнему читателю P/01.1 N0 «Время в строке», с тем же пределом трёх дробных цифр, что у писателя;
           без округления или усечения читателем; значение конечно в
           binary64, как now и as_of: не помещается — вход не по форме, код 2, раньше разбора glass (MAY-UNTIL-D8-01, решение «Архитектора» 2026-10-25)
  by:      строка
as_of:     null | конечное число JSON
disabled:  [строка…]
user:      строка без одиночных суррогатов; "" — по форме (шаг 8: deny no_grant, код 0)
glass:     true | false
cap:       view | edit | admin
unit:      null | "*" | "any" | ровно {sub, id, labels, about?, chains?}: sub, id — строки (id единицы двери грамматикой не проверяется:
           `"a,b"` — код 0), labels — [строка…]; about — ровно {sub, id, labels, chains?} той же формы или "unknown"
chains:    [[строка…]…] | "unknown"; поля нет — то же, что "unknown"
now:       конечное число JSON
sub:       строка по грамматике имени манифеста | null
roles:     null | "unreadable" | {<имя>: [ровно {role, until, at}…]}: role — строка; until и at — время, как until строки
unread:    "all" | [ровно {role, sub?}…]: role и sub — строки
iat:       конечное число JSON | null
repeats:   повторы в disabled, labels, lines и в метках области labels: — не ошибка формы
order:     вся форма проверяется до шагов 1–2 (glass, disabled): вход не по форме — код 2 и при glass: true
exit:      0 — вычислено (вывод — договор права output); 2 — вход не по форме (P/08.4 N5 exit)
```

## covers

Покрывает ли одна область гранта единицу двери, задают [договор сторожевой](gate-and-pass.md) `scope` и шаг 7 may.

```yaml
input:   {scope, ref, row}
  scope: "*" | "unit:<sub>/<id>" | "labels:<метка>[,<метка>…]" | "folder:<id>" — грамматика строки гранта (выше); иначе — код 2
  ref:   ровно {sub, id} — единица, названная в пути или ?unit=; папка как объект записи — {sub: platform, id: <id папки>}
  row:   ровно {labels: [<метка>…], about?: {sub, id, labels, chains?}, chains?} — строка единицы, как прочитана (labels — поле,
         объявленное в unit.fields; нет — []); chains — как у входа may; "@unreadable" — строка нечитаема или чтение не подтверждено
output:  true | false (stdout JSON); код 2 — вход не по форме
rule:    "*" — true; unit:<s>/<i> = ref — true по имени, строку не читая; иначе unit:<s>/<i> — true, когда row читается и
         row.about = (s, i); labels:L — true, когда row читается и все метки L — у about, если about есть, иначе у row;
         folder:<id> — true, когда row читается, chains известны и id есть в цепочке row или row.about;
         row "@unreadable" и chains "unknown" — грант по меткам, на about-единицу и folder: не покрывает (не 503);
         ref.sub = platform — unit: и labels: не покрывают
```
