// Страница VMS курса — оболочка над модулем платформы (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §10): подключает модуль и его вид по
// /platform/console.js|css?v=1, монтирует его один раз и не дублирует платформенного — своего входа, своего дерева
// серверов, своего домена, своего журнала у неё нет, за /session, /servers, /domain она не ходит. Один встроенный
// скрипт и ни одного обработчика в атрибуте — ни в разметке, ни в том, что она рисует: CSP консоли (page_csp) пускает
// только скрипт страницы по хешу и файлы своего источника. Разделы ленты — модуля и «Сценарии» страницы.
const fs=require("fs"),path=require("path");
const PAGE=fs.readFileSync(path.join(__dirname,"..","..","vms","vms.shell.html"),"utf8");
const b=require("./boot");
const out={};
const inline=[...PAGE.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
out.oneInlineScript=inline.length===1;
out.moduleAndLook=PAGE.includes('<script src="/platform/console.js?v=1"></script>')&&PAGE.includes('<link rel="stylesheet" href="/platform/console.css?v=1">');
out.mountedOnce=(inline[0].match(/PlatformConsole\.mount\(/g)||[]).length===1&&/subsystems:SUBS/.test(inline[0])&&/const SUBS=\["vms","rec","live"\]/.test(inline[0]);
// no handler in an attribute: none in the markup, none in what the script writes
out.noInlineHandlerInSource=!/\son[a-z]+\s*=\s*["'`$]/i.test(PAGE.replace(/<!--[\s\S]*?-->/g,""));
// the platform's parts are the module's: the page reads none of their routes and draws none of them
const code=inline[0].replace(/^\s*\/\/.*$/gm,"");
out.noPlatformRoutes=!/["'`]\/(session|servers|domain|policy|drain|mounts|spec|unplaceable|metrics)["'`?\/]/.test(code)&&!/["'`]\/where\//.test(code);
out.noOwnLogin=!/type="password" name="password"|signin|break-glass/.test(PAGE);
(async()=>{
const w=b.boot();const errs=[];w.addEventListener("error",e=>errs.push(String(e.error||e.message)));
await b.ready(700);await w.platformConsole.ready;
const d=w.document;
out.version=w.platformConsole.version===1;
const rail=[...d.querySelectorAll(".pc-rail [data-s]")].map(x=>x.dataset.s);
out.rail=rail.includes("units")&&rail.includes("rules")&&rail.includes("journal")&&rail.indexOf("rules")===rail.indexOf("units")+1;
out.noHandlerAttributesDrawn=!d.querySelector("[onclick],[onchange],[oninput],[onsubmit],[onload],[onerror]");
out.oneApp=d.querySelectorAll(".pc").length===1;
out.errors=errs;
b.report(out,["errors"]);
process.exit(0);
})();
