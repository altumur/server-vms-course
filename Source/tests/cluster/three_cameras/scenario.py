"""«Три камеры» на стенде М11 (без оркестратора): сцены для записок `_notes-ru/three-cameras/`, каждая — настоящий
прогон контроллера, воркеров и консоли курса через стенд `М11_ClusterVMS/clustervms/tests/stand.py`, трасса —
вывод `TraceLog.render()`.

    python scenario.py            # напечатать все сцены
    python scenario.py --write    # пересоздать traces/*.txt рядом с этим файлом
    python scenario.py 04 08-6    # только сцены, в имени которых есть эти строки

Файлы курса не меняются. Что добавлено здесь поверх стенда:
  * `S` — стенд (`Stand`) с тремя серверами, у всех метка `vlan:cctv` (стенд курса даёт cctv-a / cctv-b);
  * `Console` — настоящая консоль курса (`cluster.console.make_console`) на 127.0.0.1, к которой ходят по HTTP;
    её обмен записывается в тот же `TraceLog` строкой вида `Call(kind="http")` ПЕРЕД запросами к хранилищу,
    которые этот HTTP-запрос вызвал (ответ консоли печатается сразу под запросом);
  * `controller_pass` — один проход контроллера, как его крутит юнит (`cluster/__main__._placement_pass`):
    `with one_pass(): pass_once(1); publish_snapshot()`.
"""
from __future__ import annotations

import json
import math
import re
import os
import sys
import time
import urllib.error
import urllib.request

CV = "/Users/murat/w2c/server-vms-course/М11_ClusterVMS/clustervms"
os.chdir(CV)
sys.path.insert(0, ".")

import logging  # noqa: E402
logging.disable(logging.CRITICAL)        # журнал процессов курса не нужен в трассах

from tests import stand  # noqa: E402
from tests.conftest import Cluster, StandPeers, host as stand_host  # noqa: E402
from tests.trace import Call, TraceLog  # noqa: E402

# МАШИНА СЕРВЕРА. Воркер, которому имя занято, смотрит отметку претендента `vms/contenders/<имя>/<машина>`; машина —
# BOX_ID из юнита, иначе /etc/machine-id, иначе имя хоста (`runtime.box`). У юнита vms-vmsworker BOX_ID нет (он есть у
# регистратора, `BOX_ID=%m`), значит на сервере это /etc/machine-id. Стенд — один процесс на одной машине, и там в
# трассу попадало имя хоста того, кто снимает. Здесь машина каждого сервера — постоянная строка `machine-id-<сервер>`,
# как если бы у srv-a, srv-b, srv-c были свои /etc/machine-id.
from w2cplatform import contract as _contract, runtime as _runtime  # noqa: E402


def _stand_box(self) -> str:
    return _runtime.box_of(self.instance) or f"machine-id-{self.server}"


_contract.Worker._box = _stand_box

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "traces")

THREE = (("srv-a", "vlan:cctv"), ("srv-b", "vlan:cctv"), ("srv-c", "vlan:cctv"))
CAMS = [("Ворота", "driverpack://acme/10.2.0.11"),
        ("Парковка", "driverpack://acme/10.2.0.12"),
        ("Склад", "driverpack://acme/10.2.0.13")]


def cam(i: int, labels=("vlan:cctv",)) -> dict:
    name, src = CAMS[i - 1]
    return {"name": name, "source": src, "labels": list(labels)}


class S(stand.Stand):
    """`Stand` курса, но серверы — наши: srv-a, srv-b, srv-c, у всех `vlan:cctv` (LABELS в окружении юнитов)."""

    def __init__(self, servers=THREE, objects: bool = True):
        log = TraceLog()
        Cluster.__init__(self, servers=servers, log=log)
        log.roots = {self.root: "/data"}
        self.log = log
        self.store.machine.members = {n: {"raft": f"{stand.ADDRESSES[n]}:8301",
                                          "api": f"{n}@{stand.ADDRESSES[n]}:8300"} for n in self.servers}
        self.log.calls.clear()
        self.log.objects = objects

    def worker(self, server: str, capacity: int = 50, actuator=None, name: str | None = None, spare_for=None,
               instance: str | None = None, tag: str = "", **kw):
        """`Cluster.worker` курса; `tag` дописывается к имени в трассе (две копии одного воркера различимы)."""
        if not tag:
            return super().worker(server, capacity, actuator, name, spare_for, instance, **kw)
        from cluster.__main__ import make_worker            # как юнит: построен и зарегистрирован у ресурса
        from vms.worker import FakeActuator
        name = None if spare_for is not None else (name or f"w-{server}-1")
        env = self.env(server, name, **({"SPARE_FOR": spare_for} if spare_for is not None else {}))
        if instance:
            env["INSTANCE_ID"] = instance
        who = f"vmsworker {name or 'spare'} on {server} {tag}"
        v = self.door("vmsworker", who)
        return make_worker(v, self.objects_on(server, v, who), actuator or FakeActuator(), env=env,
                           clock=self.clock, wall=self.wall, capacity=capacity, **kw)

    def counts(self, since: int, until: int | None = None, who: str | None = None) -> dict:
        cs = [c for c in self.log.calls[since:until] if who is None or c.who.startswith(who)]
        return {"store_reads": sum(1 for c in cs if c.kind == "store" and not c.write),
                "store_writes": sum(1 for c in cs if c.kind == "store" and c.write),
                "object_requests": sum(1 for c in cs if c.kind == "objects"),
                "object_files_written": sum(1 for c in cs if c.kind == "file")}

    def view(self, since: int = 0, keep=None, gate: bool = False) -> "View":
        """Подмножество вызовов — тот же TraceLog, тот же render(). `gate=False`: чтения консолью ключей
        `domain/*` (проверка доступа: ключи домена, гранты, отзыв — по 6 на проверку, на каждом HTTP-запросе)
        выброшены, и в конце сказано, сколько их было."""
        cs = [c for c in self.log.calls[since:] if keep is None or keep(c)]
        dropped = 0
        if not gate:
            kept = [c for c in cs if not (c.kind == "store" and c.target.startswith("/v1/get?key=domain"))]
            dropped, cs = len(cs) - len(kept), kept
        return View(roots=self.log.roots, calls=cs, dropped=dropped)


class View(TraceLog):
    def __init__(self, roots, calls, dropped=0):
        super().__init__(roots=roots, calls=calls)
        self.dropped = dropped

    def render(self, *a, **kw) -> str:
        out = super().render(*a, **kw)
        if self.dropped:
            out += (f"\n# … и {self.dropped} чтений domain/* (консоль проверяет доступ: domain/keys, member, root, grants, "
                    f"revoked, break_glass) — опущены\n")
        return out


def writes_only(c) -> bool:
    return c.write or c.kind in ("http", "file", "join")


def controller_pass(ctl) -> dict:
    """Один проход юнита w2c-controller@vms: размещение и снапшот в одном one_pass. В возвращённом отчёте нет
    `seconds` (время прохода по часам машины — в трассе оно менялось бы от прогона к прогону)."""
    with ctl.one_pass():
        rep = ctl.pass_once(1)
        ctl.publish_snapshot()
    return {k: v for k, v in rep.items() if k != "seconds"}


class Console:
    """`vms-console` на сервере: настоящий make_console курса, к нему — HTTP, как из браузера оператора."""

    def __init__(self, s: S, server: str = "srv-a"):
        from cluster.console import make_console
        self.s, self.server = s, server
        self.ctl = s.console(server)
        self.http = make_console(self.ctl).serve("127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.http.server_address[1]}"

    def call(self, method: str, path: str, body=None, key: str | None = None, user: str = "anna"):
        log = self.s.log
        mark = log.mark()
        headers = {"X-User": user}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if key:
            headers["Idempotency-Key"] = key
        req = urllib.request.Request(self.base + path, data=json.dumps(body, ensure_ascii=False).encode()
                                     if body is not None else None, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                status, raw, ctype = r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            status, raw, ctype = e.code, e.read(), e.headers.get("Content-Type", "")
        self._settle()
        if "json" in ctype:
            answer = json.loads(raw)
        else:
            answer = {"Content-Type": ctype, "bytes": len(raw)}
        door = f"console on {self.server}, http://{self.server}:8080" + (f" (Idempotency-Key: {key})" if key else "")
        log.calls.insert(mark, Call(f"operator {user}'s browser", door, method, path, body, status, answer, kind="http"))
        return status, (answer if "json" in ctype else raw.decode())

    def _settle(self):
        """Обработчик консоли мог ещё дописывать после ответа: ждём, пока трасса перестанет расти."""
        n, still = -1, 0
        while still < 3:
            time.sleep(0.02)
            m = len(self.s.log.calls)
            still = still + 1 if m == n else 0
            n = m

    def close(self):
        self.http.shutdown()
        self.http.server_close()


def obj_text(store, key: str) -> str:
    raw = store.local.get(key)
    return raw.decode() if raw else "(нет)"


def comment(text: str) -> str:
    return "\n".join("# " + l if l else "#" for l in text.splitlines()) + "\n"


STAND_ARCHIVE = re.compile(r"/[^\"]*/clustervms-[^/\"]+/(srv-[a-z])/archive")


def pretty_obj(store, key: str) -> str:
    """Объект как он лежит в файле. Путь дерева ресурса на стенде — временный каталог, разный в каждом прогоне;
    показан тем, что юнит берёт из /etc/w2c/w2c.env (ARCHIVE=/data/platform/events). Размер — как на стенде."""
    raw = store.local.get(key)
    if not raw:
        return f"# {key}: нет\n"
    text = json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    shown = STAND_ARCHIVE.sub("/data/platform/events", text)
    if shown == text:
        return comment(f"{key} ({len(raw)} байт) =\n" + shown)
    return comment(f"{key} ({unit_size(raw)} байт в юните; на стенде {len(raw)} — путь archive длиннее) =\n" + shown +
                   "\n(archive: на стенде — временный каталог сервера; здесь — путь юнита, ARCHIVE из /etc/w2c/w2c.env)")


def unit_size(raw: bytes) -> int:
    """Размер объекта, каким он был бы в юните: путь дерева ресурса — /data/platform/events, а не каталог стенда."""
    return len(STAND_ARCHIVE.sub("/data/platform/events", raw.decode()).encode())


# ---------------------------------------------------------------------------------------------------------------------
# общие начала

def boot(s: S, servers=("srv-a", "srv-b", "srv-c"), capacity: int = 50):
    """Юниты стартуют: воркер на каждом сервере берёт имя и регистрируется у ресурса своего сервера (make_worker →
    Worker.present, как в юните), ресурс отчитывается, воркер — первый heartbeat."""
    ws = {}
    for n in servers:
        ws[n] = s.worker(n, capacity=capacity)
    for w in ws.values():
        w.heartbeat_once()
    s.resources_up()
    return ws


def running(s: S, capacity: int = 50, cams=(1, 2, 3)):
    """Три камеры созданы, размещены, запущены, все отчитались — исходное состояние сцен 06–08."""
    ws = boot(s, capacity=capacity)
    con = s.console("srv-a")
    for i in cams:
        con.create_camera(cam(i))
    ctl = s.controller("srv-a")
    controller_pass(ctl)
    for w in ws.values():
        w.reconcile_once()
        w.heartbeat_once()
    return ws, ctl


def beat_all(s: S, ws, skip=(), resources_skip=()):
    for n, w in ws.items():
        if n in skip:
            continue
        w.lease_pass()
        w.heartbeat_once()
    for n, srv in s.servers.items():
        if n not in resources_skip and not srv.down:
            srv.res.heartbeat()


# ---------------------------------------------------------------------------------------------------------------------
# 02 — до первой камеры

def s02_1_start() -> str:
    s = S()
    out = ["# 02-1. Старт кластера до первой камеры (часть 02-before-first-camera): юниты vms-vmsworker на srv-a/b/c",
           "# берут имена (слоты vms/slots/w-srv-X-1), пишут первый heartbeat — ФАЙЛ на своём сервере, не строку;",
           "# ресурс каждого сервера пишет свой heartbeat (тоже файл); контроллер на srv-a делает проход по пустому",
           "# кластеру и публикует снапшот. objects=True: видны файлы и запросы к ресурсу (/v1/objects).",
           "# Стенд: wall = 1757500000.0; ёмкость воркеров 50; LABELS=vlan:cctv на всех трёх серверах. Каждый воркер",
           "# строится make_worker, как в юните, и регистрируется у ресурса своего сервера (Worker.present). Машина",
           "# сервера в ключе vms/contenders/<имя>/<машина> — machine-id-<сервер> (на сервере — /etc/machine-id).",
           "# Heartbeat воркера несёт archive — путь дерева ресурса; на стенде это временный каталог, и размеры heartbeat'а",
           "# в ответах ресурса (bytes, size) на ~60 байт больше, чем в юните (ARCHIVE=/data/platform/events).", ""]
    mark = s.log.mark()
    ws = {n: s.worker(n, capacity=50) for n in ("srv-a", "srv-b", "srv-c")}
    out += ["# ---- 1. три процесса стартуют: каждый берёт своё имя (слот) ----", s.view(mark).render()]
    mark = s.log.mark()
    for w in ws.values():
        w.heartbeat_once()
    out += ["# ---- 2. первый heartbeat каждого воркера: файл на своём сервере ----", s.view(mark).render()]
    out.append(pretty_obj(ws["srv-a"].objects, "vms/heartbeats/w-srv-a-1"))
    mark = s.log.mark()
    s.resources_up()
    out += ["# ---- 3. ресурс каждого сервера отчитывается (platform/resources/<server>/heartbeat — файл) ----",
            s.view(mark).render()]
    out.append(pretty_obj(s.servers["srv-a"].res.objects if hasattr(s.servers["srv-a"].res, "objects") else ws["srv-a"].objects,
                          "platform/resources/srv-a/heartbeat"))
    ctl = s.controller("srv-a")
    mark = s.log.mark()
    rep = controller_pass(ctl)
    out += ["# ---- 4. проход контроллера на srv-a по пустому кластеру (pass_once + publish_snapshot) ----",
            s.view(mark).render(),
            f"# за проход: {s.counts(mark)}",
            f"# отчёт прохода (vms/controller/pass, файл на srv-a): {json.dumps(rep, ensure_ascii=False)}"]
    return "\n".join(out) + "\n"


def s02_2_store() -> str:
    s = S()
    boot(s)
    controller_pass(s.controller("srv-a"))
    out = ["# 02-2. Что лежит в хранилище ключей (configstore) и в объектах перед приходом оператора",
           "# (часть 02-before-first-camera). Читает root через admin-сокет: весь список ключей, потом каждый ключ.",
           "# Объекты (heartbeat'ы, отчёт прохода, снапшот) — НЕ в хранилище: это файлы на серверах, их список",
           "# спрашивается у ресурса srv-a с scope=cluster.", ""]
    v = s.door("admin", "root on srv-a")
    mark = s.log.mark()
    keys = v.list("")
    for k in sorted(keys):
        v.get(k)
    objs = s.objects_on("srv-a", v, "root on srv-a")
    objs.list("")
    out.append(s.view(mark).render())
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------------------------------
# 03 — консоль создаёт камеры

def s03_create() -> str:
    s = S()
    boot(s)
    controller_pass(s.controller("srv-a"))
    con = Console(s, "srv-a")
    try:
        out = ["# 03. Оператор anna создаёт камеры через консоль на srv-a (часть 03-creating-a-camera).",
               "# Строка `operator … browser → console …` — HTTP-обмен с консолью курса (make_console, по-настоящему по",
               "# HTTP на 127.0.0.1); запрос и ответ консоли печатаются вместе, а ПОД ними — все запросы консоли к",
               "# хранилищу и объектам, сделанные ради этого HTTP-запроса. Ключ идемпотентности — заголовок",
               "# Idempotency-Key (страница консоли шлёт свежий на каждый POST; здесь — читаемые постоянные ключи).", ""]
        mark = s.log.mark()
        con.call("POST", "/cameras", cam(1), key="k-anna-0001")
        out += ["# ---- камера 1 «Ворота»: весь путь (с проверкой доступа консолью) ----", s.view(mark, gate=True).render(), f"# итого: {s.counts(mark)}", ""]
        for i in (2, 3):
            mark = s.log.mark()
            con.call("POST", "/cameras", cam(i), key=f"k-anna-000{i}")
            out += [f"# ---- камера {i} «{CAMS[i - 1][0]}»: коротко — только HTTP и записи; чтений: {s.counts(mark)['store_reads']} ----",
                    s.view(mark, writes_only).render()]
        return "\n".join(out) + "\n"
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------------------------------
# 04 — проход контроллера, который размещает три камеры

def s04_place() -> str:
    s = S()
    boot(s)
    ctl = s.controller("srv-a")
    controller_pass(ctl)
    con = s.console("srv-a")
    for i in (1, 2, 3):
        con.create_camera(cam(i))
    ctl = s.controller("srv-a")                  # свежий процесс: ничего не помнит с прошлого прохода
    mark = s.log.mark()
    rep = controller_pass(ctl)
    c = s.counts(mark)
    lists = sum(1 for x in s.log.calls[mark:] if x.kind == "store" and x.op == "list")
    gets = sum(1 for x in s.log.calls[mark:] if x.kind == "store" and x.op == "get")
    out = ["# 04. Проход контроллера на srv-a, который размещает три камеры (часть 04-placement):",
           "# pass_once(1) + publish_snapshot() в одном one_pass — как юнит. Всё, что он читает (слоты, heartbeat'ы —",
           "# объекты через ресурс srv-a, ресурсы, политика, drain, метки серверов platform/servers/*), записи размещения",
           "# (vms/placement/<id>) и назначения (vms/workers/<w>), файлы снапшота (vms/snapshot/<w>) и отчёта прохода.", "",
           s.view(mark).render(),
           f"# за проход: {c}; из чтений хранилища list={lists}, get={gets}",
           f"# отчёт прохода: {json.dumps(rep, ensure_ascii=False)}",
           f"# where(1..3) = {[ctl.where(i) for i in (1, 2, 3)]}"]
    for w in ("w-srv-a-1", "w-srv-b-1", "w-srv-c-1"):
        out.append(pretty_obj(ctl.objects, f"vms/snapshot/{w}").rstrip("\n"))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------------------------------
# 05 — воркеры берут эпохи и запускают

def s05_workers() -> str:
    s = S()
    ws = boot(s)
    con = s.console("srv-a")
    for i in (1, 2, 3):
        con.create_camera(cam(i))
    ctl = s.controller("srv-a")
    controller_pass(ctl)
    out = ["# 05. Воркеры читают назначение, берут эпоху камеры (CAS) и запускают её; heartbeat с камерой",
           "# (часть 05-workers-and-epochs). Один проход воркера на стенде = reconcile_once(), затем heartbeat_once()",
           "# (в юните heartbeat — раз в 10 с, продление имени lease_pass — раз в ~8 с).", ""]
    mark = s.log.mark()
    ws["srv-a"].reconcile_once()
    ws["srv-a"].heartbeat_once()
    out += ["# ---- w-srv-a-1: весь проход ----", s.view(mark).render(), f"# итого: {s.counts(mark)}",
            f"# работает: {sorted(ws['srv-a'].actuator.running)} под эпохами {dict(ws['srv-a'].actuator.epochs)}",
            pretty_obj(ws["srv-a"].objects, "vms/heartbeats/w-srv-a-1")]
    for n in ("srv-b", "srv-c"):
        mark = s.log.mark()
        ws[n].reconcile_once()
        ws[n].heartbeat_once()
        out += [f"# ---- {ws[n].name}: коротко — только записи; {s.counts(mark)} ----",
                s.view(mark, writes_only).render(),
                f"# работает: {sorted(ws[n].actuator.running)} под эпохами {dict(ws[n].actuator.epochs)}", ""]
    s.wall.advance(8)
    mark = s.log.mark()
    ws["srv-a"].lease_pass()
    out += ["# ---- 8 с спустя, w-srv-a-1, следующий lease_pass: продление имени и эпохи ----", s.view(mark).render()]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------------------------------
# 06 — оператор подтверждает

def s06_confirm() -> str:
    s = S()
    running(s)
    con = Console(s, "srv-b")
    try:
        out = ["# 06. Оператор подтверждает (часть 06-confirmation): консоль на srv-b, три страницы. Под каждым",
               "# HTTP-запросом — что консоль ради него прочла в хранилище и в объектах.", ""]
        mark = s.log.mark()
        con.call("GET", "/cameras")
        out += ["# ---- GET /cameras ----", s.view(mark).render(), f"# итого: {s.counts(mark)}", ""]
        mark = s.log.mark()
        con.call("GET", "/where/1")
        out += ["# ---- GET /where/1 ----", s.view(mark).render(), f"# итого: {s.counts(mark)}", ""]
        mark = s.log.mark()
        _, text = con.call("GET", "/metrics")
        out += ["# ---- GET /metrics ----", s.view(mark).render(), f"# итого: {s.counts(mark)}",
                "# тело ответа /metrics (text/plain), строки vms_* и platform_* целиком:"]
        out += ["#   " + (l if not l.startswith("vms_reconcile_pass_seconds ") else
                             "vms_reconcile_pass_seconds <время прохода по часам машины: меняется от прогона к прогону>")
                for l in text.splitlines()]
        return "\n".join(out) + "\n"
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------------------------------
# 07 — правка и удаление

def s07_edit_delete() -> str:
    s = S()
    ws, ctl = running(s)
    con = Console(s, "srv-a")
    try:
        out = ["# 07. Правка камеры 2 и удаление камеры 3 (часть 07-edit-and-delete), консоль на srv-a; затем проходы",
               "# воркеров и контроллера. Камера 2 у w-srv-b-1, камера 3 у w-srv-c-1.", ""]
        mark = s.log.mark()
        con.call("PUT", "/cameras/2", {"events_retention_days": 30}, key="k-anna-0004")
        out += ["# ---- PUT /cameras/2 {events_retention_days: 30} ----", s.view(mark).render(), ""]
        mark = s.log.mark()
        con.call("DELETE", "/cameras/3")
        out += ["# ---- DELETE /cameras/3 (ключа идемпотентности у DELETE нет) ----", s.view(mark).render(), ""]
        mark = s.log.mark()
        ws["srv-b"].reconcile_once(); ws["srv-b"].heartbeat_once()
        out += ["# ---- проход w-srv-b-1 после правки камеры 2 ----", s.view(mark).render(),
                f"# итого: {s.counts(mark)}; работает {sorted(ws['srv-b'].actuator.running)}, эпохи {dict(ws['srv-b'].actuator.epochs)}", ""]
        mark = s.log.mark()
        ws["srv-c"].reconcile_once(); ws["srv-c"].heartbeat_once()
        out += ["# ---- проход w-srv-c-1 после удаления камеры 3, ДО прохода контроллера ----", s.view(mark).render(),
                f"# итого: {s.counts(mark)}; работает {sorted(ws['srv-c'].actuator.running)}", ""]
        mark = s.log.mark()
        controller_pass(ctl)
        out += ["# ---- проход контроллера: только записи ----", s.view(mark, writes_only).render(),
                f"# итого: {s.counts(mark)}", ""]
        mark = s.log.mark()
        ws["srv-c"].reconcile_once(); ws["srv-c"].heartbeat_once()
        out += ["# ---- следующий проход w-srv-c-1 ----", s.view(mark).render(),
                f"# итого: {s.counts(mark)}; работает {sorted(ws['srv-c'].actuator.running)}"]
        return "\n".join(out) + "\n"
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------------------------------
# 08 — отказы

def s08_1_double_save() -> str:
    s = S()
    boot(s)
    con = Console(s, "srv-a")
    try:
        out = ["# 08-1. Двойное «Сохранить» (часть 08-failures, 8.1): тот же POST /cameras с тем же",
               "# Idempotency-Key и тем же телом дважды. Второй ответ берётся из vms/idem/<ключ>; камера одна.", ""]
        mark = s.log.mark()
        con.call("POST", "/cameras", cam(1), key="k-anna-0001")
        out += ["# ---- первое нажатие ----", s.view(mark).render(), ""]
        mark = s.log.mark()
        con.call("POST", "/cameras", cam(1), key="k-anna-0001")
        out += ["# ---- второе нажатие, тот же ключ ----", s.view(mark).render(), ""]
        mark = s.log.mark()
        con.call("POST", "/cameras", {**cam(1), "name": "Ворота-2"}, key="k-anna-0001")
        out += ["# ---- тот же ключ, ДРУГОЕ тело ----", s.view(mark).render(), "",
                f"# камер в хранилище: {[r['id'] for r in con.ctl.cameras()]}"]
        return "\n".join(out) + "\n"
    finally:
        con.close()


def s08_2_two_operators() -> str:
    s = S()
    boot(s)
    a, b = Console(s, "srv-a"), Console(s, "srv-b")
    try:
        put = a.ctl.vars.put
        first = {"done": False}

        def racing_put(path, items, cas=None, **kw):
            if path == "vms/next_id" and not first["done"]:
                first["done"] = True               # между чтением next_id консолью A и её записью — B создаёт свою
                b.call("POST", "/cameras", cam(2), key="k-boris-0001", user="boris")
            return put(path, items, cas, **kw)
        a.ctl.vars.put = racing_put
        out = ["# 08-2. Два оператора создают камеру одновременно на разных консолях (часть 08-failures, 8.2):",
               "# anna на консоли srv-a создаёт «Ворота», boris на консоли srv-b — «Парковку». Консоль B успевает между",
               "# чтением vms/next_id консолью A и её записью (стенд вклинивает запрос B ровно туда). CAS A получает",
               "# 409, A читает снова и берёт следующий номер. HTTP-обмен B вложен внутрь запроса A.", ""]
        mark = s.log.mark()
        a.call("POST", "/cameras", cam(1), key="k-anna-0001")
        out += [s.view(mark).render(),
                f"# камеры: {[(r['id'], r['name']) for r in a.ctl.cameras()]}"]
        return "\n".join(out) + "\n"
    finally:
        a.close(); b.close()


def s08_3_unplaceable() -> str:
    s = S()
    ws, ctl = running(s)
    con = Console(s, "srv-a")
    try:
        said = tap_journal(ctl)
        out = ["# 08-3. Камера 4 «Касса» с меткой vlan:cctv-dmz, которой нет ни у одного сервера (часть 08-failures, 8.3).",
               "# Создание проходит; проход контроллера её не размещает (размещения и назначения нет) и считает её",
               "# недостачей (units_short), но ПРЕДЛОЖЕНИЯ слота не пишет: ни один из известных серверов не покрывает",
               "# vlan:cctv-dmz, запасному негде встать (spares_withheld, тревога spares.no_server); /unplaceable называет её.", ""]
        mark = s.log.mark()
        con.call("POST", "/cameras", {"name": "Касса", "source": "driverpack://acme/10.2.0.14",
                                      "labels": ["vlan:cctv-dmz"]}, key="k-anna-0004")
        out += ["# ---- POST /cameras: только HTTP и записи ----", s.view(mark, writes_only).render(), ""]
        mark = s.log.mark()
        rep = controller_pass(ctl)
        out += ["# ---- проход контроллера: только записи ----", s.view(mark, writes_only).render(),
                f"# итого: {s.counts(mark)}",
                f"# отчёт прохода: unplaced={rep.get('unplaced')}, units_short={rep.get('units_short')}, "
                f"workers_needed={rep.get('workers_needed')}, spare_offers={rep.get('spare_offers')}, "
                f"spares_withheld={json.dumps(rep.get('spares_withheld'), ensure_ascii=False)}",
                *journal_lines(said, 0), ""]
        mark = s.log.mark()
        con.call("GET", "/unplaceable")
        out += ["# ---- GET /unplaceable ----", s.view(mark).render(), f"# итого: {s.counts(mark)}"]
        return "\n".join(out) + "\n"
    finally:
        con.close()


def s08_4_resource_silent() -> str:
    s = S()
    ws, ctl = running(s)
    out = ["# 08-4. Замолчал ресурс srv-b (часть 08-failures, 8.4): процесс w2c-resource на srv-b не пишет heartbeat,",
           "# а сам сервер и воркер w-srv-b-1 живы (продлевают имя и пишут heartbeat). Через 45 с ресурс «silent»:",
           "# воркер на сервере без живого ресурса выпадает из пула, его камера 2 уезжает. Только записи.", ""]
    mark = s.log.mark()
    for step in (20, 20, 10):
        s.wall.advance(step)
        beat_all(s, ws, resources_skip=("srv-b",))
    out += ["# ---- 50 с: остальные продлевают имена и пишут heartbeat'ы (srv-b — воркер да, ресурс нет) ----",
            s.view(mark, writes_only).render(), ""]
    mark = s.log.mark()
    rep = controller_pass(ctl)
    out += ["# ---- проход контроллера ----", s.view(mark, writes_only).render(), f"# итого: {s.counts(mark)}",
            f"# resource_state(srv-b) = {ctl.resource_state('srv-b')}; where(1..3) = {[ctl.where(i) for i in (1, 2, 3)]}",
            f"# причина: {ctl.placement(2).reason!r}", ""]
    mark = s.log.mark()
    to = ctl.where(2)
    srv = next(n for n, w in ws.items() if w.name == to)
    ws[srv].reconcile_once(); ws[srv].heartbeat_once()
    lost = ws["srv-b"].lease_pass(); ws["srv-b"].reconcile_once(); ws["srv-b"].heartbeat_once()
    out += [f"# ---- {to} запускает камеру 2; w-srv-b-1 на своём проходе её отдаёт ----",
            s.view(mark, writes_only).render(),
            f"# w-srv-b-1.lease_pass() потерял {lost}; работает {sorted(ws['srv-b'].actuator.running)}; "
            f"{to} работает {sorted(ws[srv].actuator.running)} под эпохами {dict(ws[srv].actuator.epochs)}"]
    return "\n".join(out) + "\n"


def s08_5_one_worker() -> str:
    s = S()
    out = ["# 08-5. Воркер один, а не три (часть 08-failures, 8.5): юнит vms-vmsworker запущен только на srv-a",
           "# (на srv-b и srv-c — только ресурс). Три камеры, ёмкость 50: все три на w-srv-a-1. Только записи.", ""]
    mark = s.log.mark()
    ws = boot(s, servers=("srv-a",))
    con = s.console("srv-a")
    for i in (1, 2, 3):
        con.create_camera(cam(i))
    ctl = s.controller("srv-a")
    m2 = s.log.mark()
    rep = controller_pass(ctl)
    out += [s.view(m2, writes_only).render(), f"# проход контроллера: {s.counts(m2)}",
            f"# where(1..3) = {[ctl.where(i) for i in (1, 2, 3)]}; workers_needed = {rep.get('workers_needed')}"]
    m3 = s.log.mark()
    ws["srv-a"].reconcile_once(); ws["srv-a"].heartbeat_once()
    out += ["", "# ---- w-srv-a-1 запускает все три ----", s.view(m3, writes_only).render(),
            f"# работает {sorted(ws['srv-a'].actuator.running)}"]
    return "\n".join(out) + "\n"


def tap_journal(ctl) -> list:
    """Журнал контроллера (`Controller.journal`): в М11 он пишет только в лог процесса (архив событий контроллеры не
    монтируют), в трассу хранилища и объектов не попадает — поэтому строки `say` перехватываются здесь."""
    said = []
    j = ctl.journal
    say = j.say

    def tapped(kind, *a, **kw):
        said.append((kind, *[str(x) for x in a], {k: v for k, v in kw.items() if k != "why"}))
        return say(kind, *a, **kw)
    j.say = tapped
    return said


def journal_lines(said: list, since: int) -> list[str]:
    return [f"# журнал контроллера (в М11 — только лог процесса): {json.dumps(list(x), ensure_ascii=False)}" for x in said[since:]] or \
        ["# журнал контроллера (в М11 — только лог процесса): ничего"]


def judged(rep: dict) -> str:
    keep = ("workers_hung", "workers_hung_moved_total", "workers_unsure_moved_total", "hung_move_after",
            "workers_unjudged", "units_unjudged")
    return "# отчёт прохода: " + json.dumps({k: rep[k] for k in keep if k in rep}, ensure_ascii=False)


def _fate_lines(s: S, ctl, mark: int, worker: str = "w-srv-b-1") -> list[str]:
    fate = ctl.fates().get(worker)
    return [f"# slot_fate({worker}) = {fate}", f"# where(1..3) = {[ctl.where(i) for i in (1, 2, 3)]}"]


def _slot_row(s: S, worker: str = "w-srv-b-1") -> str:
    items, idx = s.vars.get(f"vms/slots/{worker}")
    return f"# в хранилище vms/slots/{worker} (index {idx}) = {json.dumps(items, ensure_ascii=False)}"


def _door_row(s: S, server: str = "srv-b") -> str:
    items, idx = s.vars.get(f"platform/doors/{server}")
    return f"# в хранилище platform/doors/{server} (index {idx}) = {json.dumps(items, ensure_ascii=False)}"


def _beat_until(s: S, ws, t_now: float, t_to: float, step: float = 20.0, **kw) -> float:
    """Живые воркеры продлевают имя и пишут heartbeat, ресурсы отчитываются — шагами по `step` с, без трассы."""
    while t_now < t_to:
        d = min(step, t_to - t_now)
        s.wall.advance(d)
        t_now += d
        beat_all(s, ws, **kw)
    return t_now


def _takes_over(s: S, ws, ctl, cam_id: int = 2) -> list[str]:
    """Воркер, которому досталась камера, на своём проходе берёт её эпоху и запускает."""
    to = ctl.where(cam_id)
    srv = next(n for n, w in ws.items() if w.name == to)
    mark = s.log.mark()
    ws[srv].reconcile_once(); ws[srv].heartbeat_once()
    return [f"# ---- {to} на своём проходе берёт камеру {cam_id}: только записи; {s.counts(mark)} ----",
            s.view(mark, writes_only).render(),
            f"# {to} работает {sorted(ws[srv].actuator.running)} под эпохами {dict(ws[srv].actuator.epochs)}"]


def s08_6a_process_dies() -> str:
    s = S()
    ws, ctl = running(s)
    said = tap_journal(ctl)
    out = ["# 08-6a. Процесс воркера w-srv-b-1 упал после назначения, сервер srv-b и его ресурс живы (часть 08-failures,",
           "# 8.6). Как развёрнут М11: юнит запускает make_worker, и процесс зарегистрирован у ресурса своего сервера",
           "# (Worker.present: замок-файл в .workers/ дерева ресурса, пока процесс жив). Процесс умер — замок отпущен",
           "# (absent()), ресурс srv-b в своём heartbeat говорит: w-srv-b-1 размещён здесь (workers), но не работает",
           "# (нет в running). Слот w-srv-b-1 перестаёт продлеваться; как только его until прошёл, контроллер по слову",
           "# ресурса уводит камеру 2 (fate «move») — без запаса SLOT_LOST_AFTER. Контроллер — один процесс юнита на srv-a.",
           "# systemd (Restart=always, RestartSec=2) обычно поднимает процесс через 2 с; здесь он будто не поднимался до",
           "# t+100 (например, падает на старте), чтобы было видно, что делает контроллер.", ""]
    b = ws.pop("srv-b")
    b.absent()                                            # kill -9: конец процесса отпускает его замок у ресурса
    mark = s.log.mark()
    s.wall.advance(15)
    beat_all(s, ws)
    out += ["# ---- t+15 с: живые воркеры продлевают имя (lease_pass: vms/slots/<w> и эпохи), пишут heartbeat; ресурсы ----",
            s.view(mark, writes_only).render(), ""]
    for t, step in ((40, 25), (50, 10), (95, 45)):
        s.wall.advance(step)
        beat_all(s, ws)
        mark, j = s.log.mark(), len(said)
        rep = controller_pass(ctl)
        for w in ws.values():                             # живые воркеры на своём проходе
            w.reconcile_once()
        out += [f"# ---- t+{t} с: проход контроллера, затем reconcile живых воркеров; только записи; {s.counts(mark)} ----",
                s.view(mark, writes_only).render(), *_fate_lines(s, ctl, mark), judged(rep),
                *journal_lines(said, j), ""]
    mark = s.log.mark()
    again = s.worker("srv-b")                             # systemd: Restart=always — тот же юнит, новый процесс
    again.reconcile_once(); again.heartbeat_once()
    out += ["# ---- systemd поднимает w-srv-b-1 заново (новый процесс, то же имя): берёт имя, регистрируется, читает",
            "# назначение ----",
            s.view(mark).render(),
            f"# новый w-srv-b-1 работает {sorted(again.actuator.running)} под эпохами {dict(again.actuator.epochs)}"]
    return "\n".join(out) + "\n"


def _server_b_dies(s: S, ws) -> None:
    """srv-b обесточен: ни его ресурс, ни его воркер больше ничего не пишут и ни на что не отвечают."""
    ws.pop("srv-b")
    s.servers["srv-b"].down = True


def s08_6b_server_dies() -> str:
    s = S()
    ws, ctl = running(s)
    said = tap_journal(ctl)
    out = ["# 08-6b. Сервер srv-b обесточен (часть 08-failures, 8.6): молчат и слот w-srv-b-1, и ресурс srv-b. Контроллер",
           "# на srv-a работает всё это время (один процесс): heartbeat'ы w-srv-b-1 и ресурса srv-b — файлы на srv-b — он",
           "# прочёл, пока srv-b отвечал, и помнит прочитанное. Два молчания: слот истёк и прошёл запас SLOT_LOST_AFTER,",
           "# ресурс не отчитывался дольше 45 с (и его `at` в platform/doors/srv-b тоже старше 45 с) — fate «move».", ""]
    _server_b_dies(s, ws)
    t = 0
    for t_to in (50, 95):
        t = _beat_until(s, ws, t, t_to)
        mark, j = s.log.mark(), len(said)
        rep = controller_pass(ctl)
        for w in ws.values():
            w.reconcile_once()
        out += [f"# ---- t+{t:g} с: проход контроллера, затем reconcile живых воркеров; только записи; {s.counts(mark)} ----",
                s.view(mark, writes_only).render(), *_fate_lines(s, ctl, mark),
                f"# resource_state(srv-b) = {ctl.resource_state('srv-b')}", judged(rep), *journal_lines(said, j), ""]
    out += _takes_over(s, ws, ctl)
    return "\n".join(out) + "\n"


def s08_6c_fresh_controller() -> str:
    s = S()
    ws, ctl = running(s)
    out = ["# 08-6c. Сервер srv-b обесточен, а контроллер запущен ПОСЛЕ этого (часть 08-failures, 8.6): например, юниты",
           "# w2c-controller@vms на srv-a и srv-c перезапущены обновлением. Свежий процесс не читал ничего с srv-b: файлов",
           "# heartbeat'ов w-srv-b-1 и ресурса srv-b ему не прочесть (их сервер не отвечает). Он судит по тому, что лежит в",
           "# хранилище: в слоте держатель пишет свой сервер (Slot.server, в каждом продлении), а ресурс каждые 15 с",
           "# (ALIVE_EVERY) обновляет `at` своей строки двери platform/doors/<server>. Слот истёк, `at` двери srv-b",
           "# старше 45 с — два молчания, камера 2 уезжает. (На коммите 6fd86b5 тут было «wait: never said which server»",
           "# навсегда — блокер 5 двенадцатого ревью, проба p1_fresh_reader.)", ""]
    out += ["# ---- до обесточивания: что w-srv-b-1 и ресурс srv-b оставили в хранилище ----",
            _slot_row(s), _door_row(s), ""]
    _server_b_dies(s, ws)
    t = _beat_until(s, ws, 0, 95)
    fresh = s.controller("srv-a")                         # новый процесс: ничего не помнит
    said = tap_journal(fresh)
    mark = s.log.mark()
    rep = controller_pass(fresh)
    for w in ws.values():
        w.reconcile_once()
    hb = fresh._heard("w-srv-b-1")
    out += [f"# ---- t+{t:g} с: свежий контроллер на srv-a, первый проход; ВСЕ запросы ----",
            s.view(mark).render(), f"# за проход и reconcile живых воркеров: {s.counts(mark)}",
            *_fate_lines(s, fresh, mark),
            f"# heartbeat w-srv-b-1, как его видит свежий контроллер: {'нет' if hb is None else 'есть'}; "
            f"resource_state(srv-b) = {fresh.resource_state('srv-b')}", judged(rep), *journal_lines(said, 0), ""]
    out += _takes_over(s, ws, fresh)
    return "\n".join(out) + "\n"


class CutPeers(StandPeers):
    """Дверь ресурса на сервере из `cut` (порт 8090) не отвечает другим серверам; raft и хранилище работают."""

    def __init__(self, cluster, cut=()):
        super().__init__(cluster)
        self.cut = set(cut)

    def _srv(self, url):
        if stand_host(url) in self.cut:
            raise ConnectionError(f"{url} does not answer")
        return super()._srv(url)


def s08_6d_unsure() -> str:
    from w2cplatform.contract import HUNG_MOVE_AFTER
    s = S()
    ws, ctl = running(s)
    said = tap_journal(ctl)
    out = ["# 08-6d. Судить нельзя: unsure → unsure_moved (часть 08-failures, 8.6). Дверь ресурса srv-b (порт 8090)",
           "# перестала отвечать другим серверам — правило сети, — а сам ресурс srv-b жив: отчитывается в свой файл и",
           "# каждые 15 с обновляет `at` своей строки platform/doors/srv-b в хранилище (raft между серверами цел). В это",
           "# же время процесс w-srv-b-1 упал и не поднимается. Контроллер на srv-a не может прочесть свежий heartbeat",
           "# ресурса srv-b, но видит свежий `at`: resource_state = «unreachable». Жив ли процесс w-srv-b-1, сказать",
           "# некому — fate «unsure»: камера стоит (вторым писателем её не делают). Через HUNG_MOVE_AFTER",
           f"# ({HUNG_MOVE_AFTER:g} с) после until слота — «unsure_moved»: камера уезжает всё равно, с тревогой.",
           "# Контроллер — один процесс на srv-a; показаны только его проходы в отмеченные моменты.", ""]
    for n in s.servers:
        s.servers[n].res.peers = CutPeers(s, cut=("srv-b",))
    b = ws.pop("srv-b")
    b.absent()
    until = s.vars.get("vms/slots/w-srv-b-1")[0]["until"]
    t0 = s.wall()
    out += [f"# until слота w-srv-b-1 = t+{float(until) - t0:g} с", ""]
    t = 0
    for t_to in (50, 95):
        t = _beat_until(s, ws, t, t_to)
        mark, j = s.log.mark(), len(said)
        rep = controller_pass(ctl)
        out += [f"# ---- t+{t:g} с: проход контроллера; только записи; {s.counts(mark)} ----",
                s.view(mark, writes_only).render(), *_fate_lines(s, ctl, mark), judged(rep), *journal_lines(said, j),
                f"# resource_state(srv-b) = {ctl.resource_state('srv-b')}", ""]
    t_moved = float(until) - t0 + HUNG_MOVE_AFTER + 5
    t = _beat_until(s, ws, t, t_moved, resources_skip=())
    out += [_door_row(s), ""]
    mark, j = s.log.mark(), len(said)
    rep = controller_pass(ctl)
    for w in ws.values():
        w.reconcile_once()
    out += [f"# ---- t+{t:g} с (until + HUNG_MOVE_AFTER + 5): проход контроллера, затем reconcile живых; только записи;"
            f" {s.counts(mark)} ----",
            s.view(mark, writes_only).render(), *_fate_lines(s, ctl, mark),
            judged(rep), *journal_lines(said, j),
            ""]
    out += _takes_over(s, ws, ctl)
    return "\n".join(out) + "\n"


def s08_6e_hung() -> str:
    from w2cplatform.contract import HUNG_MOVE_AFTER
    s = S()
    ws, ctl = running(s)
    said = tap_journal(ctl)
    out = ["# 08-6e. Процесс w-srv-b-1 завис: hung → hung_moved (часть 08-failures, 8.6). Процесс жив и держит свой замок",
           "# у ресурса srv-b, но не продлевает имя и не пишет heartbeat (SIGSTOP, тупик). Ресурс srv-b жив и говорит:",
           "# w-srv-b-1 размещён и работает (running). Контроллер его камеру не трогает (fate «hung», тревога",
           "# worker.hung) — перенос дал бы второго писателя. Через HUNG_MOVE_AFTER",
           f"# ({HUNG_MOVE_AFTER:g} с) после until слота — «hung_moved»: камера уезжает всё равно. В юните есть сторож",
           "# (WatchdogSec=360, процесс шлёт WATCHDOG=1 из цикла): зависший цикл systemd убил бы на 6-й минуте, замок",
           "# отпустился бы, и это был бы 08-6a. В стенде сторожа нет — так выглядит зависание, которое сторож не снял.", ""]
    b = ws.pop("srv-b")                                   # завис: объект жив (замок держится), но его никто не крутит
    until = s.vars.get("vms/slots/w-srv-b-1")[0]["until"]
    t0 = s.wall()
    out += [f"# until слота w-srv-b-1 = t+{float(until) - t0:g} с", ""]
    t = 0
    for t_to in (50, 95):
        t = _beat_until(s, ws, t, t_to)
        mark, j = s.log.mark(), len(said)
        rep = controller_pass(ctl)
        out += [f"# ---- t+{t:g} с: проход контроллера; только записи; {s.counts(mark)} ----",
                s.view(mark, writes_only).render(), *_fate_lines(s, ctl, mark), judged(rep), *journal_lines(said, j), ""]
    t = _beat_until(s, ws, t, float(until) - t0 + HUNG_MOVE_AFTER + 5)
    mark, j = s.log.mark(), len(said)
    rep = controller_pass(ctl)
    for w in ws.values():
        w.reconcile_once()
    out += [f"# ---- t+{t:g} с (until + HUNG_MOVE_AFTER + 5): проход контроллера, затем reconcile живых; только записи;"
            f" {s.counts(mark)} ----",
            s.view(mark, writes_only).render(), *_fate_lines(s, ctl, mark),
            judged(rep), *journal_lines(said, j),
            ""]
    out += _takes_over(s, ws, ctl)
    mark = s.log.mark()
    lost = b.lease_pass()
    b.reconcile_once(); b.heartbeat_once()
    out += ["", "# ---- зависший процесс w-srv-b-1 оживает (SIGCONT): продление, проход, heartbeat ----",
            s.view(mark).render(),
            f"# lease_pass() потерял {lost}; recording_allowed={b.recording_allowed}; работает {sorted(b.actuator.running)}; "
            f"name={b.name!r}"]
    return "\n".join(out) + "\n"


def s08_7_two_copies() -> str:
    s = S()
    ws, ctl = running(s)
    a = ws["srv-a"]
    out = ["# 08-7. Две копии одного воркера (часть 08-failures, 8.7): юнит vms-vmsworker на srv-a перезапущен, а",
           "# старый процесс ещё жив (завис, был остановлен SIGSTOP) — или второй запущен руками. Второй берёт имя",
           "# w-srv-a-1 сразу (новый gen); первый узнаёт об этом на продлении, и его эпохи уже не его.", ""]
    mark = s.log.mark()
    b = s.worker("srv-a", tag="(вторая копия, srv-a:4104:001008)")
    out += ["# ---- вторая копия стартует: берёт имя ----", s.view(mark).render(), ""]
    mark = s.log.mark()
    b.reconcile_once(); b.heartbeat_once()
    out += ["# ---- вторая копия: проход ----", s.view(mark).render(),
            f"# вторая копия работает {sorted(b.actuator.running)} под эпохами {dict(b.actuator.epochs)}", ""]
    mark = s.log.mark()
    lost = a.lease_pass()
    a.reconcile_once(); a.heartbeat_once()
    out += ["# ---- первая копия просыпается: продление ----", s.view(mark).render(),
            f"# первая копия: lease_pass() потерял {lost}; recording_allowed={a.recording_allowed}; работает "
            f"{sorted(a.actuator.running)}; name={a.name!r}"]
    return "\n".join(out) + "\n"


def s08_8_spares() -> str:
    from cluster.console import metrics_text
    s = S()
    ws, ctl = running(s, capacity=1)
    out = ["# 08-8. Камер больше ёмкости (часть 08-failures, 8.8). Чтобы не создавать 151 камеру, ёмкость воркеров",
           "# здесь 1 (CAPACITY=1): три камеры заняли всех. Камера 4 «Касса» (vlan:cctv) ждёт. Проход контроллера",
           "# считает недостачу и пишет ПРЕДЛОЖЕНИЕ слота (offer) — пустую строку vms/slots/w-<N> с набором меток;",
           "# w2c-spares.sh на srv-c (таймер w2c-spares-vmsworker, пользователь w2c-spares) читает /metrics и запускает",
           "# запасной из шаблона юнита роли: пишет строку SPARE_FOR=vlan:cctv в /run/w2c-spares/vms-vmsworker-spare@1.service.env",
           "# и делает `systemctl start vms-vmsworker-spare@1` (polkit разрешает этому пользователю только start шаблонов).",
           "# Шаблон — юнит воркера без WORKER_NAME (тот же пользователь vms, группы, ключ, сторож; RTSP_PORT=auto);",
           "# w2c-run.sh берёт из файла только строку SPARE_FOR=. Запасной, как и любой воркер, регистрируется у ресурса",
           "# srv-c (make_worker), берёт предложение по CAS, контроллер размещает на нём камеру. Механика сцен курса",
           "# a_spare_takes_an_offer и what_the_spares_script_reads. Только записи; чтения посчитаны.", ""]
    con = s.console("srv-a")
    mark = s.log.mark()
    con.create_camera({"name": "Касса", "source": "driverpack://acme/10.2.0.14", "labels": ["vlan:cctv"]})
    rep = controller_pass(ctl)
    out += ["# ---- камера 4 создана; проход контроллера: недостача и предложение ----",
            s.view(mark, writes_only).render(), f"# итого: {s.counts(mark)}",
            f"# отчёт: units_short={rep['units_short']}, workers_needed={rep['workers_needed']}, "
            f"spare_offers={rep['spare_offers']}, spares_starting={rep['spares_starting']}", ""]
    text = metrics_text(s.console("srv-c", who="console on srv-c (w2c-spares.sh → GET /metrics)"), 0.0)
    series = ("vms_workers_live", "vms_worker_load", "vms_workers_needed", "vms_units_short", "vms_spare_offers",
              "vms_server_labels", "vms_spares_starting")
    keep = [l for l in text.splitlines() if l.replace("# TYPE ", "").replace("# HELP ", "").split("{")[0].split(" ")[0] in series]
    out += ["# ---- что w2c-spares.sh читает в /metrics (строки серий, которые читает скрипт) ----"]
    out += ["#   " + l for l in keep]
    out.append("")
    mark = s.log.mark()
    spare = s.worker("srv-c", capacity=1, spare_for="vlan:cctv")
    spare.heartbeat_once()
    out += ["# ---- запасной на srv-c: systemctl start vms-vmsworker-spare@1 (SPARE_FOR=vlan:cctv из его файла) ----",
            s.view(mark, writes_only).render(), f"# итого: {s.counts(mark)}; имя запасного: {spare.name}", ""]
    mark = s.log.mark()
    rep = controller_pass(ctl)
    spare.reconcile_once(); spare.heartbeat_once()
    out += ["# ---- проход контроллера и запасного ----", s.view(mark, writes_only).render(),
            f"# итого: {s.counts(mark)}; where(4) = {ctl.where(4)}; запасной работает {sorted(spare.actuator.running)}",
            f"# отчёт: units_short={rep['units_short']}, workers_needed={rep['workers_needed']}, "
            f"spare_offers={rep['spare_offers']}, spares_starting={rep['spares_starting']}"]
    return "\n".join(out) + "\n"


def s08_9_garbled() -> str:
    s = S()
    ws, ctl = running(s)
    con = Console(s, "srv-a")
    try:
        out = ["# 08-9. Строка камеры 2 в хранилище не читается (часть 08-failures, 8.9): root через admin-сокет пишет в",
               "# vms/cameras/2 поле revision = «два» (правка руками). Что делают контроллер, воркер w-srv-b-1 и консоль.", ""]
        v = s.door("admin", "root on srv-a")
        row, idx = v.get("vms/cameras/2")
        mark = s.log.mark()
        v.put("vms/cameras/2", {**row, "revision": "два"}, cas=idx)
        out += ["# ---- порча ----", s.view(mark).render(), ""]
        mark = s.log.mark()
        rep = controller_pass(ctl)
        out += ["# ---- проход контроллера: только записи ----", s.view(mark, writes_only).render(),
                f"# итого: {s.counts(mark)}; отчёт: garbled={rep.get('garbled')}, unplaced={rep.get('unplaced')}; "
                f"where(2) = {ctl.where(2)}", ""]
        mark = s.log.mark()
        ws["srv-b"].reconcile_once(); ws["srv-b"].heartbeat_once()
        hb = json.loads(ws["srv-b"].objects.local.get("vms/heartbeats/w-srv-b-1"))
        out += ["# ---- проход w-srv-b-1 ----", s.view(mark).render(),
                f"# работает {sorted(ws['srv-b'].actuator.running)}; в heartbeat: "
                + json.dumps({k: v_ for k, v_ in hb.get("extra", hb).items() if "garbl" in k or k in ("status",)}, ensure_ascii=False), ""]
        mark = s.log.mark()
        con.call("GET", "/cameras")
        out += ["# ---- GET /cameras: только HTTP ----", s.view(mark, lambda c: c.kind == "http").render()]
        return "\n".join(out) + "\n"
    finally:
        con.close()


def s08_10_decommission() -> str:
    s = S()
    ws, ctl = running(s)
    con = Console(s, "srv-a")
    try:
        out = ["# 08-10. Списание сервера (часть 08-failures, «если есть»): srv-c сгорел и не вернётся. Пока ресурс srv-c",
               "# отвечает, консоль отказывает (409); когда сервер молчит — пишет platform/decommission/srv-c, и проход",
               "# контроллера освобождает слот w-srv-c-1 и уводит камеру 3. Только записи; чтения посчитаны.",
               "# (Контроллер в эти 100 с нарочно не запускался, чтобы всё списание было одним проходом; в жизни камера 3",
               "# уехала бы раньше — по двум молчаниям: слот истёк и ресурс srv-c молчит.)", ""]
        mark = s.log.mark()
        con.call("POST", "/servers/srv-c/decommission", {"why": "srv-c сгорел"})
        out += ["# ---- srv-c ещё отвечает ----", s.view(mark, writes_only).render(), ""]
        s.servers["srv-c"].down = True
        ws_alive = {n: w for n, w in ws.items() if n != "srv-c"}
        for step in (30, 30, 40):
            s.wall.advance(step)
            beat_all(s, ws_alive)
        mark = s.log.mark()
        con.call("POST", "/servers/srv-c/decommission", {"why": "srv-c сгорел"})
        out += ["# ---- 100 с спустя srv-c молчит ----", s.view(mark, writes_only).render(), f"# итого: {s.counts(mark)}", ""]
        mark = s.log.mark()
        rep = controller_pass(ctl)
        out += ["# ---- проход контроллера ----", s.view(mark, writes_only).render(), f"# итого: {s.counts(mark)}",
                f"# отчёт: servers_decommissioned={rep.get('servers_decommissioned')}, slots_released={rep.get('slots_released')}; "
                f"where(1..3) = {[ctl.where(i) for i in (1, 2, 3)]}"]
        return "\n".join(out) + "\n"
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------------------------------
# 10 — пределы

def _measure(n: int, capacity: int) -> dict:
    s = S()
    ws = boot(s, capacity=capacity)
    con = s.console("srv-a")
    for i in range(1, n + 1):
        con.create_camera({"name": f"cam-{i}", "source": f"driverpack://acme/10.2.{i // 250}.{i % 250 + 1}",
                           "labels": ["vlan:cctv"]})
    ctl = s.controller("srv-a")
    m = s.log.mark()
    rep = controller_pass(ctl)
    first = s.counts(m)
    for w in ws.values():
        w.reconcile_once(); w.heartbeat_once()
    m = s.log.mark()
    controller_pass(s.controller("srv-a"))
    steady = s.counts(m)
    w = ws["srv-a"]
    w.pump_once()                         # первый взгляд на просьбы с уборкой sweep_marks — не в замерах ниже
    m = s.log.mark()
    w.reconcile_once(); w.pump_once()     # проход цикла (VmsWorker.run): reconcile_once и pump_once
    wpass = s.counts(m)
    m = s.log.mark()
    w.heartbeat_once()
    hbeat = s.counts(m)
    m = s.log.mark()
    w.lease_pass()
    lease = s.counts(m)
    m = s.log.mark()
    w.beat_once()                         # обычный взгляд между проходами: уборка была меньше MARK_SWEEP назад
    beat = s.counts(m)
    s.clock.advance(w.MARK_SWEEP)
    m = s.log.mark()
    w.beat_once()                         # взгляд, на который пришлась уборка отметок (раз в MARK_SWEEP с)
    beat_sweep = s.counts(m, who="vmsworker")
    beat_sweep_res = s.counts(m, who="resource")
    raw = w.objects.local.get("vms/heartbeats/w-srv-a-1") or b""
    hb = (unit_size(raw), len(raw))
    snap = {k: len(ctl.objects.local.get(k) or b"") for k in ctl.objects.local.list("vms/snapshot/")}
    return {"n": n, "capacity": capacity, "placed": n - rep.get("unplaced", 0), "first": first, "steady": steady,
            "worker_pass": wpass, "hbeat": hbeat, "lease": lease, "beat": beat, "beat_sweep": beat_sweep, "beat_sweep_res": beat_sweep_res, "running_a": len(w.actuator.running), "hb": hb, "snap": snap,
            "short": rep.get("units_short"), "needed": rep.get("workers_needed")}


def s10_limits() -> str:
    out = ["# 10. Числа для части 10-limits-and-scale — измерены прогоном на стенде (3 сервера, по воркеру на каждом).",
           "# Проход контроллера = pass_once(1)+publish_snapshot() в одном one_pass, новый процесс (кэша нет).",
           "# «первый» — проход, который размещает все N; «устойчивый» — следующий, когда всё на местах и работает.",
           "# Проход воркера = reconcile_once()+pump_once() у w-srv-a-1, как в цикле VmsWorker.run (каждые 2 с);",
           "# heartbeat_once — отдельно (раз в 10 с), lease_pass — отдельно (раз в ~8 с); beat_once — между проходами",
           "# каждые 0.25 с: обычный взгляд и взгляд, на который пришлась уборка отметок команд (sweep_marks, раз в 30 с",
           "# по часам процесса — её делает первый взгляд на просьбы после срока, на проходе или между ними).",
           "# store_reads/writes — запросы к configstore; object_requests — GET к ресурсу (/v1/objects);",
           "# object_files_written — файлы объектов, записанные на своём сервере.", ""]
    rows = []
    for n, cap in ((3, 50), (30, 50), (100, 50), (300, 50), (300, 100)):
        r = _measure(n, cap)
        rows.append(r)
        out += [f"# ---- N={n} камер, ёмкость {cap} (размещено {r['placed']}, у w-srv-a-1 работает {r['running_a']}) ----",
                f"#   контроллер, первый проход:   {r['first']}",
                f"#   контроллер, устойчивый:      {r['steady']}",
                f"#   воркер w-srv-a-1, проход (reconcile_once + pump_once): {r['worker_pass']}",
                f"#   воркер w-srv-a-1, heartbeat_once: {r['hbeat']}",
                f"#   воркер w-srv-a-1, lease_pass: {r['lease']}",
                f"#   воркер w-srv-a-1, beat_once (обычный взгляд на просьбы между проходами, COMMANDS_BEAT=0.25 с): {r['beat']}",
                f"#   воркер w-srv-a-1, beat_once с уборкой отметок sweep_marks (раз в MARK_SWEEP=30 с): {r['beat_sweep']}",
                f"#     …и ресурс srv-a, отвечая на её запрос объектов, перечитал строки дверей (срок DOORS_FRESH=10 с вышел —",
                f"#     часы стенда сдвинуты на 30 с; это его чтения, не воркера): {r['beat_sweep_res']}",
                f"#   heartbeat w-srv-a-1: {r['hb'][0]} байт в юните (на стенде {r['hb'][1]}: путь archive длиннее); снапшот (байт на воркера): {r['snap']}",
                f"#   недостача: units_short={r['short']}, workers_needed={r['needed']}", ""]
    s = S()
    running(s)
    v = s.door("admin", "root on srv-a")
    mark = s.log.mark()
    v.get("vms/cameras/1")
    c = s.log.calls[mark]
    raw = json.dumps(c.answer["items"], ensure_ascii=False).encode()
    w = next(x for x in s.log.calls if x.kind == "store" and x.write and isinstance(x.body, dict)
             and x.body.get("key") == "vms/cameras/1")
    body = json.dumps(w.body, ensure_ascii=False).encode()
    out += ["# ---- строка камеры 1 «Ворота» (как её отдаёт хранилище) ----", s.view(mark).render(),
            f"# items в JSON: {len(raw)} байт (UTF-8), полей {len(c.answer['items'])}; тело записи POST /v1/write при "
            f"создании (с op/key/cas/id операции): {len(body)} байт"]
    return "\n".join(out) + "\n"


SCENES = {
    "02-1-start-before-first-camera": s02_1_start,
    "02-2-store-before-operator": s02_2_store,
    "03-console-creates-three-cameras": s03_create,
    "04-controller-places-three": s04_place,
    "05-workers-take-epochs": s05_workers,
    "06-operator-confirms": s06_confirm,
    "07-edit-and-delete": s07_edit_delete,
    "08-1-double-save": s08_1_double_save,
    "08-2-two-operators-at-once": s08_2_two_operators,
    "08-3-label-nobody-has": s08_3_unplaceable,
    "08-4-resource-srv-b-silent": s08_4_resource_silent,
    "08-5-one-worker-not-three": s08_5_one_worker,
    "08-6a-process-dies-server-alive": s08_6a_process_dies,
    "08-6b-server-dies-controller-running": s08_6b_server_dies,
    "08-6c-server-dies-fresh-controller": s08_6c_fresh_controller,
    "08-6d-unsure-then-moved": s08_6d_unsure,
    "08-6e-hung-then-moved": s08_6e_hung,
    "08-7-two-copies-one-worker": s08_7_two_copies,
    "08-8-more-cameras-than-capacity": s08_8_spares,
    "08-9-garbled-row": s08_9_garbled,
    "08-10-decommission-srv-c": s08_10_decommission,
    "10-limits-numbers": s10_limits,
}


def main() -> None:
    write = "--write" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if write:
        os.makedirs(OUT, exist_ok=True)
    for name, scene in SCENES.items():
        if only and not any(o in name for o in only):
            continue
        text = scene()
        if write:
            with open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8") as f:
                f.write(text)
            print(f"{name}: {len(text.splitlines())} lines")
        else:
            print(f"==== {name}\n{text}")


if __name__ == "__main__":
    main()
