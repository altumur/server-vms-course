# Урок 12 — Страница VMS

**Модуль:** М10B — ServerVMS (часть вторая)
**Вы напишете:** `vms/vms.shell.html` — страницу VMS над модулем консоли платформы: значки и метку камеры, редактор её источника, заметки и слова событий, вкладки «Видео» и «Архив», тома под серверами и «Камеру в архив», раздел «Сценарии», домен глазами VMS. Ядро страницы — двери держателей, шкала, куски, живое видео — копия продуктового, сверенная тестом (`tests/test_shell_core.py`). И `vms/console.py` — `make_console`: консоль VMS, в которой своего у VMS нет ни строки.
**Время:** ~90 минут.

## Зачем этот урок

Модуль из [урока 16 М10A](../М10A_Platform/16-HTML.md) умеет всё общее: дерево, карточку единицы, серверы, домен, права, журнал, вход. Камеры он не знает. Оператору VMS нужно больше: картинка, архив, тома, сценарии.

Куда это положить — вопрос урока, и ответ на него задан границей (ADR 0001, 0002). У подсистемы три места, и консоль не из них: спека, воркер, страница. Маршрутов на консоли у VMS нет ни одного. Консоль VMS — это консоль платформы, запущенная с `CONSOLE_ROOT=vms`: она читает спеки VMS и отдаёт то, что они объявили. Всё, что VMS показывает сверх модуля, — страница рядом со спекой. А байты — шкалу, куски архива, живой поток — страница берёт у держателей сама, через двери, которые консоль только называет (ADR 0009, 0015).

Четыре вещи, ради которых урок стоит читать.

**Страница — оболочка.** Она подключает модуль и добавляет своё вызовами его библиотеки. Своего входа, дерева серверов, домена, журнала у неё нет: это модуль, и тест страницы это проверяет.

**Байты — только через двери.** Шкала камеры собирается из дверей её записей и дверей мест, где запись могла оставить кадры. Место, которое никто не держит, названо: его архив недоступен, а не утрачен.

**Ядро — одно с продуктом.** Как страница ходит к дверям, сливает участки, режет куски и открывает живой поток — один код курса и продукта, функция в функцию.

**Ни одного обработчика в разметке.** Консоль пускает только скрипт страницы по его хешу; поэтому всё навешивается кодом, и это же — вторая стена против хранимого XSS.

> **Проверка без железа.** Страница проверяется в jsdom с поддельным API: `Source/tests/console/shell-*.test.js` — `shell-page`, `shell-video`, `shell-archive`, `shell-archive-add`, `shell-volumes`, `shell-camera-state`, `shell-rules`, `shell-domain`, `shell-domain-archives`, `shell-xss-sweep`; их гоняет `tests/run.py`. Ядро сверяет `tests/test_shell_core.py` (с продуктом рядом с курсом). Двери — настоящие: `test_lesson6_controller.py::test_the_console_over_http` (корень отдаёт страницу над модулем; дверь регистратора отдаёт шкалу и кусок MP4), `test_where_volume.py` (запись, переехавшая на другой том, и том, чей регистратор замолчал), `test_where_place.py`, `test_lesson8_live.py::test_the_first_viewer_creates_the_stream_and_the_controller_places_it`.

## Что нужно знать заранее

- **М10A, [урок 16](../М10A_Platform/16-HTML.md)** — модуль консоли, его вызовы, CSP по хешу.
- **М10A, [урок 15](../М10A_Platform/15-SpecConsole.md)** — шаг 12 «Что подсистема объявляет, и дверь держателя» (`/where/<id>`, `/where/<table>/<place>`, токен двери), шаг 14 `Mount`.
- **[Урок 8](08-visibility-retention-timeline.md)** — дверь архива регистратора между процессами, отсечённые эпохи, правило «момент — старшей эпохе».
- **[Урок 10](10-recworker.md)** — регистратор держит один том и объявляет в heartbeat'е `url` и `volume`.
- **[Урок 24](24-an-interval-in-the-browser.md)** — фрагментированный MP4 и куски; **[урок 27](27-volumes.md)** — тома; **[урок 25](25-automation.md)** — сценарии.

## Чему вы научитесь

1. Собирать консоль подсистемы из спек, не написав ей ни одного маршрута.
2. Писать страницу-оболочку над модулем платформы и не повторять платформенного.
3. Ходить за байтами к держателю по двери с короткоживущим токеном и спрашивать её заново, когда токен кончается.
4. Строить одну шкалу из многих дверей и называть те, что не ответили.
5. Держать общий с продуктом код сверенным построчно.
6. Вешать обработчики кодом, чтобы политика содержимого не мешала странице.

---

## Шаг 1 — Консоль VMS — это консоль платформы

```python
def make_console(ctl: VmsController, resource_root: str | None, wall=None, live_ctl: SpecController | None = None,
                 mounts: dict[str, SpecController] | None = None, index=None) -> Mount:
    """One console process for the box: the VMS at `/`, and every other subsystem the console fronts under its name."""
    ctls = {ctl.spec.name: ctl, **({"live": live_ctl} if live_ctl is not None else {}), **(mounts or {})}
    return spec_console(ctls, ctl.spec.name, resource_root, index, wall)
```

Весь `vms/console.py` — эта функция и `serve` вокруг неё; ими его зовут тесты и уроки. Развёрнутая консоль — глагол платформы: `python3 -m w2cplatform console` с `CONSOLE_ROOT=vms` (`deploy/w2c-console.container`, служба `w2c-console.service` — то же имя, что на кластере; ADR 0023), процесс платформы под пользователем `w2c` (ADR 0030). `spec_console` (М10A, урок 15, шаг 14) ставит VMS на корень, остальные спеки — под их именами, с одним журналом и одним слиянием событий на всех.

Что консоль делает для VMS, VMS **объявляет**, а не пишет:

| Что | Где объявлено | Где разобрано |
|---|---|---|
| камеры, записи, потоки — строки, поля, правка | `rows`, `unit.fields` спек | М10A, урок 15 |
| тома и удержания — таблицы `/rec/volumes`, `/rec/keeps` | `tables` спеки `rec` | М10A, урок 15, шаг 12; [урок 27](27-volumes.md) |
| «дозаписать отрезок» — `POST /rec/requests` | `requests` спеки `rec` | М10A, урок 14, шаг 14; [урок 16](16-backfill-from-the-edge.md) |
| дверь регистратора — `timeline`, `segment`, `keeps` | `door: {routes: [timeline, segment, keeps]}` спеки `rec` | этот урок, шаги 5–7; печать метки — [урок 18](18-what-the-archive-gives-up-first.md), шаг 7 |
| дверь шлюза — `whep` | `door: {routes: [whep]}` спеки `live` | этот урок, шаг 9; [урок 13](13-live-video.md) |
| места записи — тома | `placement.places: {table: volumes, …}` спеки `rec` | М10A, урок 15, шаг 12; [урок 27](27-volumes.md) |
| поток заводит зритель по праву `view` | `rights: {routes: {view: [streams]}}` спеки `live` | этот урок, шаг 9 |
| реле и пресет — право на каждую камеру устройства | `rights: {reach: {group: [source, labels], cluster: [ref], requests: [output, preset]}}` спеки `vms` | М10A, урок 15, шаг 12а |
| слова страницы | `display` спек | М10A, урок 16, шаг 3 |

Метки серверов и списание сервера — платформенные двери, у всех подсистем одни (М10A, урок 11, шаг 17; урок 7, шаг 7; ADR 0004, 0026). Пароль в адресе источника — правило секретов платформы, читающее то, что спека VMS сказала о написании логина (М10A, урок 18; [урок 19](19-the-cameras-credential.md)).

Байтовых маршрутов у консоли нет — ни на корне, ни под монтированием: `/timeline/1`, `/rec/timeline/1`, `/segment/…`, `/whep/1`, `/live/whep/1` — 404 (`test_where_volume.py::test_the_console_has_no_byte_routes_of_its_own`).

## Шаг 2 — Страница рядом со спекой

Консоль отдаёт на `/` страницу корня (`page_of`, М10A, урок 16, шаг 1): `<sub>.shell.html` рядом с файлом его спеки. У VMS это `vms/vms.shell.html` рядом с `vms.subsystem.yaml`. Смонтированные `/rec/`, `/live/` своих страниц не отдают: их единицы модуль показывает на этой.

Голова страницы — три строки контракта и одна опция:

```html
<link rel="stylesheet" href="/platform/console.css?v=1">
…
<div id="app"></div>
<script src="/platform/console.js?v=1"></script>
<script>
"use strict";
// The VMS's words (display) and what its subsystems are about (about) the module reads from each one's spec.
const SUBS=["vms","rec","live"];
const pc=PlatformConsole.mount(document.getElementById("app"),{lang:"ru",subsystems:SUBS});
window.platformConsole=pc;
```

`subsystems` сужает дерево до камер, записей и потоков. `rec` и `live` говорят в спеке `about: {sub: vms, field: cam}`, поэтому модуль сам вкладывает записи и потоки камеры под её узел: странице не нужно знать, что записи живут под камерами. Слова — «камера», «Оборудование», подписи полей, блоки формы — приходят из `display` спеки VMS; в странице их нет.

Состояние, которое странице нужно от модуля, она берёт из его событий:

```js
let UNITS={},domView=null;
pc.on("refresh",d=>{if(d&&d.units)UNITS=d.units;if(d&&"domain" in d)domView=d.domain});
const camById=id=>(UNITS.vms||[]).find(u=>String(u.id)===String(id))||null;
…
const recsOfCam=id=>(UNITS.rec||[]).filter(r=>String(r.cam)===String(id));
const isCam=ref=>String(ref).startsWith("unit:vms/");
```

За `/cameras` и `/rec/recordings`-как-единицами страница не ходит: их читает модуль, и каждый опрос отдаёт их ей.

**Чего у страницы нет** — проверено буквально (`shell-page.test.js`): один встроенный скрипт, модуль и его облик по `?v=1`, `mount` один раз с `subsystems:SUBS`; ни своего входа, ни запросов к `/session`, `/servers`, `/domain`, `/policy`, `/drain`, `/mounts`, `/spec`, `/unplaceable`, `/metrics`, `/where/`; в ленте — разделы модуля и «Сценарии» страницы сразу после «Оборудования». Из `/domain` страница берёт только долю VMS: книгу, поля которой показывает спека (`/domain/vms/books/primaries`, ADR-0010), и `where` записи другого кластера через свою консоль (`/domain/at/…`, ADR-0061; шаг 6).

И нет того, чего курс не отдаёт: страница продукта показывает ещё «Записанное сервером», учётки потребителей потока домена, правки домена, «Видеоускоритель», «Опции», вкладку «Детекторы» и мастер устройств. Мёртвых кнопок под маршруты, которых нет, страница курса не рисует.

## Шаг 3 — Ни одного обработчика в разметке

Консоль отдаёт страницу с политикой `script-src 'self' 'sha256-…'` (`page_csp`, М10A, урок 16, шаг 8): выполняется встроенный скрипт страницы по хешу и модуль со своего источника. `onclick="…"` в разметке — код без хеша, и браузер его не выполнит. Поэтому страница навешивает всё сама:

```js
// A click (a change, for a field) on the page's own markup is wired here, never in an attribute: the console's CSP
// runs no inline handler. `data-act` names the handler; the element and its dataset are what it gets.
function wire(host,acts){
  host.querySelectorAll("[data-act]").forEach(el=>{const f=acts[el.dataset.act];if(!f)return;
    if(/^(SELECT|INPUT|TEXTAREA)$/.test(el.tagName))el.onchange=e=>f(el,e);
    else el.onclick=e=>{e.preventDefault();e.stopPropagation();f(el,e)}});
}
```

Разметка называет действие (`data-act="toggle"`), данные — в `data-*` (`data-rec="${esc(r.id)}"`), а код получает элемент и читает `el.dataset`. Значение никогда не попадает в текст кода: шаблон `onclick="f('${esc(x)}')"` экранирование не спасает — браузер раскодирует `&#39;` в кавычку до того, как выполнит атрибут.

Всё, что страница рисует из данных, идёт через `esc` — имя камеры, заметка события, адрес тома:

```js
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
```

`shell-xss-sweep.test.js` проверяет страницу и модуль вместе: каждое строковое поле каждого ответа — вредная строка, трижды разная (выход из атрибута с `<img onerror>`, выход из строки внутри обработчика, `<script>` в заметке). Обход — обе раскладки панели, каждая строка дерева, каждая вкладка, всё, что нажимается, разделы и меню. Код из данных не выполняется ни разу, чужих элементов в разметке нет, данные видны текстом. Тест страницы отдельно проверяет, что в исходнике нет `on…=` и в нарисованном нет `[onclick]`, `[onchange]` и прочих.

## Шаг 4 — Камера: значок, адрес, источник, заметки, события

Шесть вызовов, и каждый добавляет то, чего спека сказать не может.

```js
pc.addIcons({
  camera:`<path fill="currentColor" d="M1.4 3.6h7.6c…"/>…`,
  storage:`<path fill="currentColor" d="M2 2.4h12c…"/>…`
});
…
pc.addDecor("unit",(ref,u)=>isCam(ref)?{icon:"camera",badge:u?parseSource(u.source).host:""}:{});
```

Значки — код страницы, не данные. Камера в дереве и в заголовке карточки — со своим знаком и адресом меткой.

Источник камеры — единственное в ней, что не следует из типов полей: `driverpack://<производитель>/<адрес>/ch/<канал>` или любой другой URL. Общая форма модуля нарисовала бы строку; страница даёт свой редактор этого одного поля:

```js
pc.addFieldEditor("unit","source",(host,ref,obj,value,set)=>{
  host.innerHTML=`<div class="g"><div><label>Источник</label><input class="vms-src" value="${esc(value)}" autocomplete="off"></div><span class="vms-src-parts" style="display:contents"></span></div>`;
  const inp=host.querySelector(".vms-src"),parts=host.querySelector(".vms-src-parts");
  const show=v=>{const s2=parseSource(v);parts.innerHTML=fldRo("Адрес",s2.host)+fldRo("Производитель",s2.vendor)+fldRo("Канал",s2.channel)};
  show(value);
  if(!pc.may("edit",ref))inp.disabled=true;
  inp.oninput=()=>{set(inp.value);show(inp.value)};
});
```

Редактор показывает, что говорит адрес, и отдаёт значение форме через `set`. Отправляет форма модуля: тем же `api()`, с той же проверкой `bound_to` — сменили источник, впишите пароль заново (М10A, урок 18).

Заметки — слова о камере, за которыми логика:

```js
pc.addNote("unit",(ref,u)=>{
  if(!isCam(ref)||!u)return"";
  if(u.device_state==="opening")return"Устройство ещё открывается — если это не проходит, открытие не завершается: проверьте адрес, сеть и учётные данные камеры.";
  if(u.phase==="failed")return`Хост драйверов: сбой устройства${u.why?" — "+u.why:""}.`;
  return"";
});
```

Модуль показывает их предупреждением под «Размещением» (`shell-camera-state.test.js`).

Меню камеры в дереве — «Смотреть видео» и «Архив»: выбрать камеру и открыть вкладку (`addMenu("unit")`).

События VMS — словами везде, где модуль показывает события, включая «Журнал»:

```js
let inNote=false;
pc.addEventNote(e=>{if(inNote||!/^(camera\.|card\.|volume\.|archive\.)/.test(e.kind||""))return"";inNote=true;try{return evNoteRu(e)}finally{inNote=false}});
function evNoteRu(e){
  const k=e.kind||"";
  if(k==="volume.missing")return[`том ${e.volume??"?"}`,e.server?"на "+e.server:"",e.recorder?"держал "+e.recorder:"",e.detail||"","записи ушли на другие тома"].filter(Boolean).join(" · ");
  if(k==="archive.volume.shrunk")return`том ${e.volume??"?"}${e.was!=null?": "+gbytes(+e.was)+" → "+gbytes(+e.quota_bytes):""} — самое старое отдано первым`;
  …
  return pc.eventNote(e);   // the platform's own events the module describes
}
```

Вид события («часы камеры скакнули вперёд») — из `display.kinds` спеки. Описание — суммы, причины, тома — из полей события, и это логика страницы: `volume.missing`, `archive.volume.shrunk`, `archive.footage.dropped`, `camera.footage.lost`, `camera.uplink.short`, `card.prebuffer.short`, `card.failing`, `archive.backfill.refused`. `inNote` — защита от петли: неописанное событие страница отдаёт обратно модулю, а модуль снова зовёт страницу. Виды семейства просьб, `command` и `command.failed`, страница не описывает и `display.kinds` спеки не называет: это слова модуля, как `server.*` и `worker.*`, — исход по `outcome`, `action`, кто просил, «поздно», ответ цели из `reply` (контракт модуля, §5; ADR 0013).

## Шаг 5 — Двери: ядро, скопированное со сверкой

Отсюда начинается ядро — между двумя строками-метками страницы:

```js
// ── core: COPY WITH A CHECK — the product's vms/vms.shell.html (main), function by function; test_shell_core.py ──
…
// ── end of core ──────────────────────────────────────────────────────────────────────────────────────────────────
```

```python
CORE = ("whereAt", "doorOf", "doorFetch", "yieldCut", "loadTimeline", "segmentURL", "play", "playNext",
        "negotiateLive", "stopLive")
PRODUCT = "vmsworker/vms/vms.shell.html"
```

`test_the_core_of_the_course_page_is_the_products_but_for_the_debt` сравнивает каждую из десяти функций с той же функцией страницы продукта на его `main`; `test_the_core_functions_stand_in_the_marked_block_of_the_course_page` — что они стоят между метками. Разница — только долг `testdata/shell_core_debt.txt`, и он только сокращается (`W2C_SHELL_CORE_SHRINK=1`); сегодня он пуст. Остальная страница — курса: её пишут уроки. А то, как страница доходит до байтов, — один код. Ошибка в повторе по 401 или в слиянии участков иначе жила бы в двух местах и чинилась бы в одном.

Первые три функции ядра — дверь:

```js
async function whereAt(url){
  try{const r=await fetch(url);let d={};try{d=await r.json()}catch(e){}
    return{status:r.status,door:d&&d.door&&d.door.url?d.door:null,missing:r.headers.get("X-Unreachable")||(d&&d.unreachable)||"",error:d&&d.error||""}}
  catch(e){return{status:0,door:null,missing:"",error:String(e)}}
}
async function doorOf(where,fresh){
  const d=DOORS[where];
  if(!fresh&&d&&d.expires-Date.now()/1000>20)return d;
  const w=await whereAt(where);
  DOORS[where]=w.door?{url:String(w.door.url).replace(/\/+$/,""),token:w.door.token||"",expires:+w.door.expires||0}:null;
  return DOORS[where];
}
async function doorFetch(where,path,init={}){
  let d=await doorOf(where);if(!d)return null;
  const go=()=>fetch(d.url+path,{...init,headers:{...(init.headers||{}),Authorization:"Bearer "+d.token}});
  let r=await go();
  if(r.status===401){d=await doorOf(where,true);if(!d)return null;r=await go()}   // its token would not do: where again, once
  return r;
}
```

`/where` консоли (М10A, урок 15, шаг 12) отвечает `door: {url, token, expires, routes}`: адрес, который держатель объявил в heartbeat'е, и токен `door1.<kid>.<payload>.<signature>` на эту единицу, этого держателя и маршруты спеки, на `TTL` — 120 с (`w2cplatform/door.py`). Консоль подписывает, держатель только проверяет; ключа, которым выдают токены, у держателя нет.

Три правила, и все в этих строках:

- **токен спрашивается заново за 20 секунд до конца**, а не после отказа: кусок, начатый с токеном на последней секунде, не должен упасть посредине;
- **401 — `where` заново, один раз.** Держатель отказывает одним словом (`reason`: `expired`, `holder`, `unit`, `route`…). Камера переехала — другой держатель, и старый токен не его; `/where` даст новый. Второй 401 подряд — уже не устаревший токен, и страница не крутится в цикле;
- **заголовок там, где его можно поставить** (`Authorization: Bearer` у `fetch`), `?t=` там, где нельзя: `<video src>` заголовков не шлёт. Токен в адресе держатель маскирует везде, где пишет путь в лог.

Cookie консоли к держателю не идёт никогда: дверь отвечает только на токен, и CORS разрешён только источникам консолей (`DOOR_ORIGINS`).

## Шаг 6 — Шкала: каждая запись и каждое место

Шкала камеры — это шкала её записей. Своей двери у держателя камеры для страницы нет (`vms.subsystem.yaml`: *the scale is built from the camera's recordings*):

```js
async function loadTimeline(id){
  const [from,to]=winRange();
  …
  const recs=recsOfCam(id).concat(farRecsOfCam(id));
  // the places a recording may lie on: the rows of the table rec's spec names (spec.places), not a name written here
  const T=((pc.spec("rec")||{}).places||{}).table||"";
  let places=[];
  if(T){try{const d=await (await fetch(`/rec/${encodeURIComponent(T)}`)).json();places=d[T]||[]}catch(e){places=[]}}
  const asks=[],missing=new Set(),refused=new Map(),seen=new Set(),spans=[];
  // a recording on a backup volume: what it has yields to the primary's, and its remainder is «only in the backup»;
  // another cluster's recording says it itself (its volumes are that cluster's)
  const backupRec=rec=>{if(rec.cluster)return!!rec.backup;const v=places.find(x=>x.name===rec.home);return!!v&&v.kind===VOL_BACKUP};
  const take=(rec,where,list)=>{const bk=backupRec(rec);for(const x of list||[]){
    const k=[rec.cluster||"",rec.id,x.start_ms,x.end_ms,x.epoch,x.source||""].join("|");if(seen.has(k))continue;seen.add(k);
    spans.push({start:x.start_ms/1000,end:x.end_ms/1000,epoch:x.epoch,fenced:!!x.fenced,events:0,source:x.source||"",recording:rec.id,where,media:true,yields:!!x.yields||bk,backupOnly:bk})}};
  const ask=async(rec,where,place)=>{
    const w=await whereAt(where);
    // another cluster's answer, in words: its gate does not know you (403), its console is not reached (502), it is not
    // a member this console can reach (404 from the hop), the members' list does not read here (503)
    if(!w.door&&rec.cluster&&!place&&[403,404,502,503].includes(w.status)){refused.set(rec.cluster,w.status);return null}
    if(!w.door){if(place&&w.status===404&&w.missing)missing.add(w.missing);return null}   // «no such place»: nothing to say
    try{const r=await doorFetch(where,`/timeline/${encodeURIComponent(rec.id)}?from=${from}&to=${to}`);
      if(!r||!r.ok){missing.add(place||rec.id);return null}
      const m=r.headers.get("X-Unreachable");if(m)missing.add(m);
      return await r.json()}
    catch(e){missing.add(place||rec.id);return null}
  };
  // the recordings' own doors first (theirs win a twin), then the volumes'
  const own=await Promise.all(recs.map(rec=>ask(rec,recWhere(rec),"")));
  recs.forEach((rec,i)=>take(rec,recWhere(rec),own[i]));
  // the places: this cluster's table for its own recordings; another cluster's recording, its home there
  for(const rec of recs)for(const name of rec.cluster?(rec.home&&!refused.has(rec.cluster)?[rec.home]:[]):places.map(v=>v.name))
    asks.push((async()=>{const where=placeWhere(rec,T||"volumes",name);take(rec,where,await ask(rec,where,name))})());
  await Promise.all(asks);
  …
```

Разберём по шагам, потому что каждый закрывает один случай.

**Каждая запись — своей дверью.** У камеры может быть несколько записей: на дисках сервера, в сетевом томе, резервная. `GET /rec/where/<запись>` даёт дверь регистратора, который держит запись сейчас.

**Каждое место — дверью своего держателя.** Запись переезжает: регистратор умер, запись взял другой на другом сервере. То, что она записала на прежнем томе, осталось там, и читается это у того, кто держит **тот** том: `GET /rec/where/volumes/<том>?unit=rec/<запись>` (М10A, урок 15, шаг 12; ADR 0009). Токен этой двери — на эту запись и этого держателя: токен, выданный двери записи, дверь тома не откроет (`test_where_volume.py::test_a_recording_moved_to_another_volume_shows_what_it_left_on_the_first_at_that_volumes_holders_door`).

**Имя таблицы мест — не в коде.** Места — строки таблицы, которую спека `rec` называет в `placement.places` (`spec.places.table` в `/spec`), прочитанные по `/rec/<таблица>`. Слово `volumes` в ядре — только запасное имя для места записи другого кластера, когда своя спека таблицы не называет; места своих записей — всегда по спеке, у курса и у продукта.

**Близнецы сливаются, своя дверь впереди.** Двери записи и тома могут сказать одни и те же минуты. Ключ — запись, начало, конец, эпоха, источник; первым побеждает ответ двери самой записи.

**Недоступно — не значит потеряно.** Место, которое сейчас никто не держит, консоль называет: `/where/<table>/<place>` отвечает 404, `door: null` и `X-Unreachable: <том>@<сервер>`. «Такого места нет» — 404 без `X-Unreachable` — страница пропускает молча. Названное идёт в подпись над шкалой:

```js
  const unr=[...missing];
  const WHY={403:c=>`на ${c} вас не знают: его архив не показан`,502:c=>`консоль ${c} не видна по сети: его архив смотрится только там, где её видно`,404:c=>`консоль ${c} отсюда не известна: его архив не показан`,503:c=>`список членов домена здесь не читается: архив ${c} не показан`};
  V.note=(unr.length?`Недоступн${unr.length>1?"ы":"о"}: ${unr.join(", ")} — ${unr.length>1?"их архивы недоступны":"его архив недоступен"}, а не утрачен${unr.length>1?"ы":""}; лента может быть неполной.`:"")
    +[...refused].map(([c,st])=>" "+WHY[st](c)+".").join("");V.note=V.note.trim();
  V.spans=yieldCut(spans).sort((a,b)=>a.start-b.start);
```

Без этого страница нарисовала бы дыру там, где лежит видео выключенного сервера, и оператор искал бы запись на карте камеры или списал бы её как потерянную. Тест: регистратор тома `old` замолчал — место отвечает 404 с `X-Unreachable: old@srv-1`, на шкале минуты `new`, а `old@srv-1` назван рядом с `gone@srv-3` (`test_where_volume.py::test_a_volume_whose_recorder_went_silent_is_named_and_its_minutes_are_missing_not_drawn`).

**Запись в другом кластере домена — тоже на шкале.** Камеру этого кластера может писать другой (пересечение, [М12B](../М12B_DomainVMS/README.md)). Тогда её минуты лежат там, и дверь к ним выдаёт консоль **того** кластера своим ключом (ADR-0015). Страница узнаёт такие записи из книги primaries, которую домен приносит в кластер камеры: `GET /domain/vms/books/primaries` отдаёт по `ref` камеры только поля, которые спека разрешает показать (`primaries: {show: [recorded_by, recording]}`; ADR-0010), без токенов дорог. `where` страница спрашивает у своей консоли, а та передаёт его консоли того кластера ровно один раз (`member_forward`, ADR-0061):

```js
function farRecsOfCam(id){
  const c=camById(id),ref=c&&c.ref;if(!ref)return[];
  const p=PRIMARIES&&PRIMARIES[ref];
  // a recording this cluster holds itself is one of its own already (the book names this cluster too, then)
  if(!p||!p.recorded_by||!p.recording||recsOfCam(id).some(r=>String(r.id)===String(p.recording)))return[];
  return[{id:String(p.recording),cluster:String(p.recorded_by),home:"",backup:false,cam:String(id)}];
}
// where a recording's door is asked: its own cluster's console, or another's through this one (ADR-0061)
const recWhere=rec=>(rec.cluster?`/domain/at/${encodeURIComponent(rec.cluster)}`:"")+"/rec/where/"+encodeURIComponent(rec.id);
```

`farRecsOfCam`, `recWhere` и `placeWhere` стоят вне ядра. Продукт у кластера держателя домена берёт записи сначала из состояния VMS в домене (`/domain/vms/state`). В курсе такого маршрута нет, и книга — источник для обоих. Близнецов ключ различает по кластеру. Отказ того кластера — не «недоступно», а слова о том, почему: 403 — его привратник вас не знает, 502 — его консоль не видна по сети, 404 — такого члена отсюда не видно, 503 — список членов здесь не читается. Кусок идёт прямо с двери держателя, мимо обеих консолей (`shell-far-recordings.test.js`).

**Что отвечает дверь.** На стороне регистратора `/timeline/<запись>` — `footage_routes` в `vms/footage.py`:

```python
    def timeline(unit: str, q: dict):
        …
        ours, unreachable = [], []
        # Fenced against the RECORDING's epoch, which the store holds — a door knows only its own recorder's, and the
        # zombie's stream may be in another volume than the survivor's. A copy (`e0`, a keep's) is never fenced.
        cur = _rec_epoch(vars_, unit)
        for name, url, hb in recorder_doors(objects, wall(), eyes=eyes):
            try:
                got, said_whole = door_timeline(name, url, unit, t0, min(t1, 1e11))
            except (OSError, ValueError):
                unreachable.append(name)
                continue
            …
            for sp in got:
                fenced = bool(sp.get("fenced")) or (cur is not None and 0 < sp["epoch"] < cur)
                ours.append({"start_ms": int(round(sp["start"] * 1000)), "end_ms": int(round(sp["end"] * 1000)),
                             "epoch": sp["epoch"], **({"source": "backfill"} if sp["source"] == "backfill" else {}),
                             **({"fenced": True} if fenced else {})})
        dev = device_coverage(unit)
        if dev is not None:
            …
                ours.append({"start_ms": int(round(lo * 1000)), "end_ms": int(round(hi * 1000)), "epoch": 0,
                             "source": "device", "yields": True})
        …
        return 200, spans, headers
```

Дверь спрашивает двери архива **всех** живых регистраторов (`/spans/<запись>` между процессами, [урок 8](08-visibility-retention-timeline.md)): каждый держит один том, а запись за свою жизнь бывает в нескольких. Дверь, которая не ответила за `DOOR_TIMEOUT` (5 с), названа в `X-Unreachable` — и её имя попадает в ту же подпись страницы. Отсечение — по строке эпохи **записи** в хранилище (`rec/epoch/<запись>`): дверь архива знает только эпоху своего регистратора, а поток зомби может лежать в другом томе, чем поток выжившего. Копия удержания (`e0`) не отсекается. Ответ сырой — `[{start_ms, end_ms, epoch, source?, fenced?, yields?}]`, в продуктовой форме.

**Что уступает.** Участок с `yields` — то, что камера держит сама (её карта, диски регистратора; [урок 15](15-the-archive-we-did-not-write.md)), — рисуется только там, где нет участка регистратора (ADR 0016). Так же страница обращается с записью на резервном томе:

```js
function yieldCut(spans){
  const solid=spans.filter(s=>!s.yields);
  const holes=(a,b)=>{const out=[];let at=a;
    for(const o of solid.filter(o=>o.end>a&&o.start<b).sort((x,y)=>x.start-y.start)){if(o.start>at)out.push([at,Math.min(o.start,b)]);at=Math.max(at,o.end)}
    if(at<b)out.push([at,b]);return out};
  return[...solid,...spans.filter(s=>s.yields).flatMap(s=>holes(s.start,s.end).map(([a,b])=>({...s,start:a,end:b})))];
}
```

Остаток резервной записи — то, чего в основной нет. Шкала рисует его штриховкой, а под шкалой — «только в резервном» и кнопку «Закрепить»: склеенные интервалы уходят заявками основной записи, `POST /rec/requests {unit: rec/<запись>, from, to}` через `pc.api` (спека `rec`, `requests`; [урок 16](16-backfill-from-the-edge.md)). Регистратор основной записи заберёт их из резервной.

## Шаг 7 — Куски, каждый момент один раз

Участок на шкале не называет файла. Он называет дверь, запись и эпоху; минуты к ним добавляет страница:

```js
async function segmentURL(s,p){
  const d=await doorOf(s.where);if(!d)return"";
  return `${d.url}/segment/${encodeURIComponent(s.recording)}/e${s.epoch}/${Math.round(p.start*1000)}-${Math.round(p.end*1000)}${s.source?"."+s.source:""}.mp4?t=${encodeURIComponent(d.token)}`;
}
```

Кусок — `GET <дверь>/segment/<запись>/e<эпоха>/<fromMs>-<toMs>[.<source>].mp4?t=<токен>`: поток одной эпохи, границы в пути, `.backfill.mp4` — дозаписанное, `.device.mp4` — байты самой камеры. Та же дверь, с которой пришёл участок (`s.where`), и токен свежий: `doorOf` спросит `where` заново, если старому осталось меньше 20 секунд.

Режет страница по минуте, как консоль продукта:

```js
const PIECE=60;
function piecesFrom(i,t){
  const out=[];let until=-Infinity;
  V.spans.forEach((s,j)=>{
    if(j<i||!s.media||(s.fenced&&j!==i))return;
    for(let a=Math.max(s.start,until);a<s.end;a+=PIECE){
      const p={i:j,start:a,end:Math.min(s.end,a+PIECE),off:0};
      if(t&&p.end<=t)continue;
      if(t&&!out.length&&t>p.start)p.off=t-p.start;
      out.push(p);
    }
    until=Math.max(until,s.end);
  });
  return out;
}
```

**Каждый момент — один раз.** Участки перекрываются: отсечённая эпоха и следующая над одними минутами, два тома одной записи, копия удержания. Очередь по всем участкам подряд сыграла бы такие минуты дважды. Поэтому отсечённый участок играется, только если щёлкнули по нему самому, а `until` помнит конец уже поставленного: следующий участок встаёт в очередь с этого места, а не со своего начала. С момента `t` (клик по событию, `seek`) очередь начинается с куска, в котором он лежит, и плеер встаёт на смещение `off` по `loadedmetadata`. `piecesFrom` — курса, не ядра; `play`, `playNext` и `segmentURL` — ядро.

`playNext` ставит следующий кусок по `ended` плеера и подписывает его: «<с> – <по> · эпоха N», «из резервного архива», «дозаписано из резервного». Шов на границе кусков виден — и честно показывает, где кончился один ответ двери и начался другой. Устройство файла и почему он фрагментированный — [урок 24](24-an-interval-in-the-browser.md).

На стороне двери кусок — экспорт (`footage_routes`, `export`): поток одной эпохи — живой или его дозапись, — интервал не длиннее `EXPORT_MAX` (час), каждый отрезок у той двери архива, что его держит, кадры по минуте (`EXPORT_PIECE`); не больше `EXPORTS_AT_ONCE` (2) экспортов на дверь и `EXPORTS_PER_USER` (1) на человека. Дверь архива, не ответившая до первого байта, названа в `X-Unreachable`; отказавшая после — обрыв, видный по отсутствию последнего куска chunked. И каждый отданный кусок — строка `archive.read` в журнале **регистратора** (`audit/door-<регистратор>`): кто — имя, которому консоль выдала токен, — какой кусок, сколько байт, sha256 целого. Консоль байтов не видит и о них не пишет; она пишет `door.issued` — кому, на какую единицу и до какого времени выдала дверь.

## Шаг 8 — События на шкале

```js
async function fetchEvents(id,from,to){
  …
    const r=await fetch(`/events?from=${from}&to=${to}&unit=${encodeURIComponent("vms/"+id)}`);
    // Past the console's norm the answer is `groups`, not `events` — read both, and say why the list changed shape.
    if(r.ok){const d=await r.json();
      V.events=d.events||[];V.groups=d.groups||[];V.evstate=d.state||"";
      V.aggregated=!!d.aggregated;V.truncated=!!d.truncated;V.rate=+d.rate_per_minute||0;V.norm=+d.per_minute||0}
```

События камеры — одним запросом из слияния (М10A, урок 15, шаг 7): `unit=vms/<id>` отдаёт и строки о камере от подсистем, которые про неё (`of`). На шкале событие стоит там, где **произошло** (`occurred`), а не где записано (`t`); опоздавшее подписано «записано в …». Цвет подсистемы назначается при первой встрече (`subColor`): реестра подсистем у страницы нет. Поля события выводятся вычитанием: известные — на своих местах, остальные `ключ=значение`, и новое поле детектора появляется на экране в тот же день. `state`, отличный от `live`, красится: список событий короче правды, потому что какой-то ресурс не ответил. За нормативом потока (`per_minute`) ответ — `groups`, и страница показывает счёт, а не строки, и говорит почему.

Отметка оператора — `POST /marks {unit: "vms/<id>", note}` через `pc.api`: тот же ключ на отправку, что у всех записей.

## Шаг 9 — Живое видео

```js
async function negotiateLive(id){
  let pc;
  try{pc=new RTCPeerConnection()}catch(e){setCap("браузер не умеет WebRTC");return}
  pc.addTransceiver("video",{direction:"recvonly"});
  …
  const offer=await pc.createOffer();
  await pc.setLocalDescription({type:"offer",sdp:h265Dynamic(offer.sdp)});
  // The first viewer makes the stream (POST /live/streams {cam}; «exists» — somebody watches already), then the
  // offer goes to its gateway's door: 404/503 — not placed yet, again in 1.5 s, up to 8 times; 401 — where again, once.
  try{await window.platformConsole.api("POST","/live/streams",{cam:String(id)})}
  catch(e){if(!(e.status===409&&e.body&&e.body.error==="exists")){setCap("живое отклонено: "+e.message);pc.close();return}}
  const where="/live/where/"+encodeURIComponent(id);
  let r=null,tries=0;
  for(;;){
    try{r=await doorFetch(where,`/whep/${encodeURIComponent(id)}`,{method:"POST",headers:{"Content-Type":"application/sdp"},body:pc.localDescription.sdp})}
    catch(e){r=null}
    if(r&&![404,503].includes(r.status))break;
    if(++tries>8)break;
    setCap(`живое: ждём шлюз… (${tries})`);
    await new Promise(res=>setTimeout(res,1500));
  }
  …
```

**Поток заводит первый зритель — строкой.** Единица живого вещания появляется по спросу: `POST /live/streams {cam}` создаёт `live/streams/<камера>`, и право на это — `view` на камеру (`rights: {routes: {view: [streams]}}` спеки `live`; смотреть — не менять). Второй зритель получает 409 `exists` — и это нормальный исход: поток есть, чего и добивались.

**Предложение — шлюзу, а не консоли.** `/live/where/<камера>` даёт дверь шлюза, на котором контроллер разместил поток, и предложение уходит туда: `POST <дверь>/whep/<камера>` с токеном в `Authorization`. Пока поток не размещён или шлюз ещё не подписался, ответ — 404 или 503, и страница повторяет каждые полторы секунды до восьми раз — двенадцать секунд, заведомо больше прохода контроллера — и **пишет, чего ждёт**. Двери нет вовсе (`/where` ответил `door: null`) — тот же повтор: `doorFetch` вернул `null`. На 401 — `where` заново, один раз. RTP идёт шлюз → браузер: ни консоль, ни воркер камеры медиа не несут (ADR 0015; [урок 13](13-live-video.md)).

**H.265 в предложении.** Chrome нумерует H.265 ниже 96, а упаковщик GStreamer берёт только 96–127; шлюз отвечает номерами предложения. `h265Dynamic` переносит номера H.265 (и их `rtx`, `apt=`) на свободные в 96–127 до отправки.

**Трубку кладёт зритель.** `stopLive` шлёт `DELETE` на `Location` ответа (`/whep/session/<id>`) у той же двери, со свежим токеном — без него шлюз держал бы соединение до таймаута, а последний ушедший зритель не освободил бы единицу вещания. Выбор другого объекта и закрытие вкладки (`beforeunload`) кладут трубку тоже. Шлюз, сам положивший трубку — камера переехала, поток оборвался, — даёт `failed`, и страница переподключается сама, после случайной паузы, чтобы пятьдесят зрителей одной камеры не пришли в один миг.

**Пока смотрят — не перерисовывать.** Вкладка «Видео» говорит модулю `busy: () => playingNow()`: пока идёт живой поток, согласование или выбран кусок, опрос не перерисовывает карточку и не обрывает просмотр. Рядом с картинкой — живая лента событий камеры раз в 3 с, последние тридцать: картинка от шлюза, события с ресурсов, и страница соединяет их только по времени.

## Шаг 10 — «Архив»: записи и удержания

Вкладка «Архив» камеры — её записи из `/rec/recordings` и удержания из `/rec/keeps`. Запись — единица `rec`: у камеры их может быть несколько, по одной на том; `cam` говорит, чью она пишет, `home` — на каком томе.

```js
function recState(r){
  if(r.enabled===false)return{label:"Выключена",bad:true};
  const w=r.row;
  if(!w)return{label:"Не размещена",bad:true};
  if(w.worker_state==="stale")return{label:"Регистратор молчит",bad:true};
  if(w.phase==="running")return{label:"Пишет",bad:false};
  if(w.phase==="standby")return{label:"Ждёт: основная запись идёт",bad:false};
  if(w.phase==="waiting")return{label:"Ждёт том",bad:true};
  if(w.phase==="failed")return{label:"Ошибка",bad:true};
  return{label:w.phase||"—",bad:false};
}
```

Три разных «не пишет» — выключена, не размещена, регистратор молчит — и у каждого своё действие. «Ждёт: основная запись идёт» — резервная запись, которая пишет, только пока основная не пишется, и держит последние секунды в памяти ([урок 26](26-a-backup-archive-of-our-own.md)).

**Переключатель — действие, а не поле черновика.** Включить, выключить, сменить том, срок, «когда писать» — каждое сразу записью: `PUT /rec/recordings/<имя>` через `pc.api`, затем перечитать. «Когда писать» есть только у записи на резервном томе. Удаление — после подтверждения, и подтверждение говорит то, чего оператор не знает: записанное видео остаётся в томе до истечения срока хранения. «＋ Запись» — диалог модуля (`pc.dialog`).

**Удержание** — отрезок, который не уходит по сроку хранения: `POST /rec/keeps {cam, from, to, note}` (с — по — зачем), «Снять» — `DELETE` после подтверждения. «Удержать показанное» на вкладке «Видео» подставляет видимое окно шкалы. Том вида «инциденты» никто не обслуживает — карточка предупреждает: удержанное держится, только пока его хранит архив записи (`shell-archive.test.js`).

**Что с удержанием сейчас** — слова регистраторов в их биении. Спека `rec` называет в `servers.status` поля с `of: keeps` (ADR-0064): `keeps`, `incidents_lost`, `incidents_at_risk`. Регистраторы — воркеры `rec`, а не корня, поэтому их строки страница читает у `rec`, вместе с остальным (`loadRec`):

```js
    try{REC_SERVERS=(await getJSON("/rec/servers")).servers||{}}catch(e){REC_SERVERS={}}
```

Корневой `/servers`, который читает модуль, знает только воркеров корня: строка воркера VMS, сказавшая `keeps`, страницей не читается. `/rec/servers` кладёт поля в `status` строки регистратора как есть, а страница сопоставляет ключи карты и элементы списка со строками `rec/keeps` по имени удержания (`keepSaid`). Каждый регистратор говорит своё, и страница показывает слово каждого — сначала держателя, потом записи по имени. Пишущий запись (с `recording`): `here` — «в архиве записи», с секундами и «кольцо заберёт через …» (`leaves_in_s`); `pushing` — «копируется в архив инцидентов»; `pushed` — «скопировано»; `at risk` — «под угрозой» и почему (`why`); `lost` — «потеряно N с» (`lost_seconds`) и почему. Держатель тома инцидентов: `kept` — «в архиве инцидентов», с секундами; `released` — «отпущено» и почему; `garbled` — «не читается». `incidents_lost` — «архив инцидентов потерял N с из удержанного», `incidents_at_risk` — «под угрозой: кольцо записи заберёт раньше, чем скопирует». Запись без кадров в отрезке (`keeps.<имя>.empty` у держателя) — «в отрезке нет кадров у … — запечатывать нечего». Чего спека не назвала, страница не читает (`shell-keep-states.test.js`). «Проверить» сверяет печать у двери держателя тома инцидентов ([урок 18](18-what-the-archive-gives-up-first.md)): по запросу на запись, `POST <дверь>/keeps/<имя>/verify?recording=<запись>`, с жетоном места этой записи. Кнопка есть, только если спека открывает `keeps` на двери. Ответ `result: empty` — не провал и не ожидание, о нём сказано отдельно: «в этом отрезке у … нет кадров — запечатывать нечего» (`shell-keep-verify.test.js`). Эти слова — слова регистратора продукта (`recproc/keeper.go`); страница взяла их у продукта вместе с его регистратором. Регистратор курса пока пишет в `keeps` только `copied`, `missing`, `from`, `to`, `sha256` и `whole` ([урок 18](18-what-the-archive-gives-up-first.md)). `state`, `empty`, `incidents_lost` и `incidents_at_risk` он не говорит, и `result: empty` сверка у него не отвечает. Поэтому на стенде курса строка удержания молчит о состоянии, а не выдумывает его. Без `rec` в консоли — карточка «подсистема записи не подключена», без кнопок.

## Шаг 11 — Тома и «Камеру в архив»

Тома — строки таблицы мест `rec`, прочитанные по `/rec/<таблица>`; модулю они не единицы, поэтому в дерево их ставит страница:

```js
pc.addTreeNodes("server",ref=>recOn?serverVolumes(ref.slice(7)).map(v=>({ref:"vol:"+v.name,label:v.name,icon:"storage",badge:volKind(v,true),off:!v.enabled})):[]);
pc.addTreeNodes("servers",()=>recOn?[{ref:"netvols",label:"Сетевые архивы",icon:"storage",count:networkVolumes().length,
  kids:networkVolumes().map(v=>({ref:"vol:"+v.name,label:v.name,icon:"storage",badge:volKind(v,true),off:!v.enabled}))}]:[]);
pc.addCard("vol",(host,ref)=>{CARD_HOST=host;volumeCard(host,ref.slice(4))});
pc.addCard("netvols",host=>{CARD_HOST=host;netVolumesCard(host)});
pc.addBlock("server",{id:"vols",covers:"rec/volumes",render:(host,ref)=>{ … }});
```

Под сервером — его тома, сетевые — отдельным узлом «Сетевые архивы» на верхнем уровне: их может обслужить любой сервер. Блок «Архивы сервера» на обзоре сервера закрывает таблицу `servers.show` спеки `rec` (`covers: "rec/volumes"`): модуль её для этого места не рисует (М10A, урок 16, шаг 7).

Над блоком — тома этого сервера, у которых пропал каталог: регистратор говорит имя такого тома в биении (`volume_missing`, [урок 27](27-volumes.md)), страница берёт его из строк регистраторов этого сервера в `/rec/servers` (те же `REC_SERVERS`) — «Пропал каталог тома: <том>. Записи ушли на другие тома.», имя ведёт к карточке тома (`shell-volumes.test.js`):

```js
  const miss=[...new Set(recWorkers().filter(x=>x.server===name).map(x=>x.status.volume_missing).filter(Boolean))];
```

**Объявлен и обслуживается — разные вещи.** Карточка тома говорит «Обслуживается: <held_by>» или «Никто не обслуживает»: объявление тома не запускает процесса, место существует, потому что его кто-то держит ([урок 27](27-volumes.md)). Объявить — строка целиком, `POST /rec/<таблица>`; меньшая квота у тома, который уже есть, стирает самое старое, поэтому уходит только после вопроса и с `shrink_confirmed`, равным ей. Отозвать — `DELETE` после вопроса, и вопрос говорит: записанное видео не удаляется. Пустой секрет ключа сетевого тома — «оставить текущий»; это единственный секрет, который страница рисует сама, и он — поле пароля без значения (`test_credentials.py::test_the_page_asks_a_secret_in_a_password_field_and_never_fills_it_with_the_mask`).

**«Камеру в архив»** — запись камеры на томе: из блока сервера, из шапки его карточки (`addAction`), из меню сервера и тома (`addMenu`), с карточки тома и со вкладки «Архив». В выборе — только тома этого сервера и сетевые, и только камеры, которых там ещё нет:

```js
  const taken=new Set(recs.map(r=>r.id));
  const name=!taken.has(v.cam)?v.cam:v.home?`${v.cam}-${v.home}`:v.cam;
  if(taken.has(name)){pc.toast(`Запись «${name}» уже есть`);return}
  try{await pc.api("POST","/rec/recordings",{name,cam:v.cam,retention_days:days,...(v.home?{home:v.home}:{})});await reloadRec();pc.toast("Запись создана")}
```

Имя записи — номер камеры, а если оно занято — `<номер>-<том>`: записи камеры по одной на том, и имя — их ключ (их эпоха, их потоки; [урок 10](10-recworker.md)).

## Шаг 12 — «Сценарии»

```js
pc.addSection({id:"rules",label:"Сценарии",icon:"bolt",after:"units",render:host=>{RULES_HOST=host;loadAuto().then(renderRules)}});
```

Свой раздел ленты, сразу после «Оборудования». Сценарий — единица `auto`: «когда случилось это — попросить сделать то». Вычислитель читает тот же журнал, что раздел «Журнал», и подаёт заявку тому, кто держит устройство; консоль ничего не выполняет сама ([урок 25](25-automation.md)).

```js
const RACTIONS=[
  {sub:"vms",action:"output",label:"Щёлкнуть реле",fields:[{id:"unit",label:"Устройство"},{id:"port",label:"Реле №"},{id:"state",label:"Состояние",opt:true},{id:"pulse_ms",label:"Импульс, мс",opt:true}]},
  {sub:"vms",action:"preset",label:"Встать в пресет",fields:[{id:"unit",label:"Камера"},{id:"n",label:"Пресет №"}]},
  {sub:"rec",action:"record",label:"Записывать",fields:[{id:"cam",label:"Камера"},{id:"minutes",label:"Минут"},{id:"archive",label:"Архив",opt:true}]},
  …
```

Действия — ровно то, под что написан исполнитель: `then` спеки `auto`, каждый его вариант с обязательными полями. `test_auto_spec.py::test_the_pages_scenario_form_offers_exactly_the_actions_the_auto_spec_accepts` держит их вместе: оператор не может попросить того, чего никто не выполнит. Действия детекторов предлагаются, только когда консоль монтирует `det` (страница спрашивает `/det/spec`). События в «если» — со словами из `display.kinds` спеки VMS, уточнения — `ключ=значение`. Отказы — до отправки и теми же словами, что у сервера (`ruleProblem`): экран, который принимает то, что подсистема откажет, врёт дважды. Новый сценарий — `POST /auto/scenarios`, существующий — `PUT` без имени. Отказ вычислителя (`unfit` в статусе) — красной строкой «Вычислитель отказал: …». Последние срабатывания — события `fired` сценария за сутки (`shell-rules.test.js`).

## Шаг 13 — Домен глазами VMS

Модуль рисует платформенную часть домена: члены, топология, тревоги, ключи. Камеры и архивы членов — это VMS, и их страница берёт из того же вида держателя (`GET /domain`, который модуль отдаёт ей в `refresh`): `units` — единицы членов с кластером, сервером, воркером и состоянием, `tables` — таблицы домена, которые служат спеки (`vms/crossings`: для камеры одного кластера — кластер, который её пишет; [урок 3 М12B](../М12B_DomainVMS/03-a-camera-nobody-can-reach.md)).

```js
pc.addTreeNodes("member",ref=>{
  const name=ref.slice(7),cams=domUnits("vms",name),arcs=domUnits("rec",name);
  …
  if(cams.length===1)return[{...cam(cams[0]),replaces:true,title:"Сервер-камера "+name,open:arcs.length>0,kids:arcs.map(arc)}];
  return cams.map(cam).concat(arcs.map(u=>({...arc(u),after:true})));
});
```

Член с одной камерой — сервер-камера — стоит в дереве своей камерой (`replaces`), его архивы под ней, раскрыты с первого показа. У члена с несколькими камерами — камеры, затем архивы. Карточки камеры и архива члена (`addCard("dc"|"da")`), блок члена «Камеры» и «Архивы» (`addBlock("member")`), «Пересечения» на «Обзоре» домена (`addBlock("domain")`). Только чтение: срок, том и включение записи задаются в самом кластере, правки домена идут его дверью (`shell-domain.test.js`, `shell-domain-archives.test.js`).

## Результат

```
GET  /                                  → vms/vms.shell.html над /platform/console.js (CSP: 'self' и хеш её скрипта)
GET  /rec/where/7                       → {worker, server, door: {url, token: "door1.…", expires, routes: [timeline, segment, keeps]}}
GET  /rec/where/volumes/old?unit=rec/7  → дверь держателя тома для записи 7
                                          или 404, door: null, X-Unreachable: old@srv-1
GET  /domain/vms/books/primaries        → {<ref>: {recorded_by, recording}} — кто пишет камеру в другом кластере
GET  /domain/at/east/rec/where/SN-7     → дверь записи кластера east, выданная его консолью (ADR-0061);
                                          403/404/502/503 — словами в подписи шкалы
GET  <door>/timeline/7?from&to          → [{start_ms, end_ms, epoch, source?, fenced?, yields?}]   (Bearer)
GET  <door>/segment/7/e3/<a>-<b>.mp4?t= → кусок одной эпохи, video/mp4
POST <door>/keeps/<метка>/verify?recording=7 → печать метки сверена с копией (у держателя тома incidents, урок 18)
POST /live/streams {cam: "7"}           → 201, или 409 exists — поток уже смотрят
GET  /live/where/7                      → дверь шлюза, routes: [whep]
POST <door>/whep/7                      → 201 + SDP, Location: /whep/session/<id>; 404/503 — ещё не размещён
POST /rec/requests, /rec/recordings, /rec/<таблица мест>, /rec/keeps, /auto/scenarios, /marks   → через pc.api
GET  /timeline/7, /segment/…, /whep/7  → 404: у консоли байтовых маршрутов нет
```

Одна страница, один модуль, байты мимо консоли — и все подсистемы VMS в одном дереве.

## Что может пойти не так

- **Маршрут VMS на консоли.** Одна «маленькая» дверь `/timeline/<cam>` — и консоль снова носит байты, а платформа знает, что такое камера. Место байтов — дверь держателя, объявленная в спеке.
- **Обработчик в атрибуте.** `onclick="f('${esc(x)}')"` не выполнится под CSP, а без CSP станет XSS: `&#39;` браузер раскодирует до выполнения. `data-act` и `wire`.
- **Своё платформенное на странице.** Свой вход, своё дерево серверов, свой `api()` — два правила там, где должно быть одно.
- **Токен до отказа.** Без запаса в 20 секунд кусок, начатый на последней секунде токена, падает посредине.
- **401 по кругу.** Повтор без предела на отказ двери — запросы без конца к держателю, который не возьмёт этот токен никогда.
- **Только дверь записи.** Минуты, оставленные записью на прежнем томе, пропадут со шкалы — молча.
- **Место без держателя — дырой.** Оператор будет искать на карте камеры или списывать как потерянное видео, которое лежит на выключенном сервере.
- **Очередь по всем участкам подряд.** Минуты двух эпох, двух томов и копии удержания играются по два раза.
- **Имя таблицы мест в коде.** Страница перестанет совпадать с продуктом и со спекой, которая назовёт таблицу иначе.
- **404 шлюза как отказ.** Первое нажатие «Живое» всегда попадает в окно между размещением и подпиской шлюза; страница, не повторяющая на 404, заставит нажимать дважды.
- **Перерисовка во время просмотра.** Опрос, пересобирающий карточку, обрывает живой поток каждые пять секунд. `busy()`.
- **Ядро, поправленное только у себя.** Через месяц у курса и продукта разные правила повтора; тест сверки упадёт — и правильно.

## Итог

- Консоль VMS — консоль платформы с `CONSOLE_ROOT=vms`: `make_console` — это `spec_console` над спеками VMS, и маршрутов у VMS на ней нет. Что ей нужно, VMS объявляет: таблицы, заявки, двери, места, права, слова.
- Страница VMS — `vms/vms.shell.html` рядом со спекой, оболочка над модулем: `mount` с `subsystems: ["vms", "rec", "live"]`, своё — вызовами библиотеки, платформенного — ничего.
- Под CSP ни одного обработчика в разметке: `data-act` и `wire`; всё из данных — через `esc`.
- Ядро — двери, шкала, куски, живое — копия продуктового, сверенная по функциям; долг пуст.
- Дверь — `{url, token, expires}`: токен `door1.` на единицу и держателя, Bearer для `fetch`, `?t=` для плеера, заново за 20 с до конца и один раз на 401.
- Шкала — двери каждой записи и каждого места, близнецы сливаются, своя дверь впереди; место без держателя названо по `X-Unreachable`: недоступно, не утрачено. Участки с `yields` и резервные уступают основным. Запись камеры в другом кластере домена — из книги primaries, её `where` через свою консоль (`/domain/at/…`, ADR-0061), отказ того кластера — словами.
- Куски по 60 с с той же двери, каждый момент один раз; чтение — строка `archive.read` в журнале регистратора, консоль пишет только `door.issued`.
- Живое: первый зритель заводит поток строкой, предложение — на дверь шлюза, повтор на 404 и 503, трубка — `DELETE` со свежим токеном.
- «Архив», тома, «Камеру в архив», «Сценарии», домен глазами VMS — каждое через `pc.api` и вызовы модуля.

## Упражнения

1. Уберите из `loadTimeline` двери мест и оставьте только двери записей. Перенесите запись на другой том и посмотрите на шкалу за последний час. Какой тест `test_where_volume.py` упадёт?
2. Уберите в `doorOf` запас в 20 секунд. Поставьте `TTL` в 30 с и играйте кусок за куском. Где и как сломается?
3. Сделайте в `doorFetch` повтор на 401 без предела. Остановите держателя и пересадите запись на другой — сколько запросов уйдёт к старому?
4. Замените в одной кнопке «Архива» `data-act` на `onclick="recWrite('${esc(r.id)}', …)"`. Что покажет консоль браузера под CSP консоли — и что сделает `shell-xss-sweep.test.js`?
5. Уберите `(s.fenced&&j!==i)` из `piecesFrom`. Возьмите запись, у которой две эпохи над одними минутами, и кликните по первому участку. Что сыграется дважды?
6. Отвечайте в `negotiateLive` на 404 как на отказ. Нажмите «Живое» у камеры, которую никто не смотрит. Что увидит оператор?
7. Впишите имя `volumes` прямо в `loadTimeline` вместо `spec.places.table`. Запустите `test_shell_core.py` с продуктом рядом. Что он скажет?
8. Уберите `busy` у вкладки «Видео». Откройте живой поток и подождите опроса.

## Что дальше

Дверь шлюза страница уже зовёт, а за ней пока никого: `live/streams/<cam>` — строка в подсистеме, которой ещё не существует.

> **Ещё одна оговорка.** Шкала уже рисует то, что камера держит сама, — участком с `yields` от двери записи, и кусок `.device.mp4` с той же двери. Откуда эти байты берутся у держателя камеры — [урок 15](15-the-archive-we-did-not-write.md).

[**Урок 13**](13-live-video.md) пишет `live.subsystem.yaml`, `LiveWorker` и `webrtc.py`: подсистему, чья единица — раздача камеры, чья ёмкость измеряется в зрителях, и чьи единицы создаются спросом и уходят вместе с ним.
