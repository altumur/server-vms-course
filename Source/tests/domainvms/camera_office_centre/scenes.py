"""The scenes of the camera–office–centre notes, in their order. Each takes the `stand.Site` the scenes before it left,
and says what happens in it with `site.log.note(...)` lines — the rest of the trace is the code's own."""
from __future__ import annotations

import json


def s01_founding(site) -> None:
    log = site.log
    log.note("Сцена 1. Домен основан на srv.\n"
             "Установщик на srv до первого старта (в курсе — функция term.install установщика; у продукта\n"
             "`domain install --holder srv --recovery …`, stand.sh start): корень домена вне держателя, файл\n"
             "восстановления отдан оператору; первый набор ключей и запись держателя срока 1 подписаны корнем.")
    site.install()
    log.note("Первый человек домена — тоже установщика (в курсе — вызовы IdentityStore.create_local и\n"
             "grants.set_domain_grants; у продукта `domain user add`, `domain grant --cluster domain`): дверь людей —\n"
             "подписывающего, и она спрашивает админа.")
    site.first_admin("anna")
    log.note(f"Подписывающий стартует (signer_service.main): CLUSTERS={site.clusters_line()}")
    site.start_signer()
    log.note("Консоль домена (console.main) и воркер VMS на домене (vms.domainpart) стартуют; агент держателя тоже.")
    site.start_domain_console()
    site.start_domainpart()
    site.holder_agent()
    site.cluster_console("srv")
    log.note("Первый проход подписывающего (Holder.run_pass); его объекты — файлы на srv — тоже в трассе.")
    log.objects = True
    site.holder.run_pass()
    log.objects = False
    log.note("Первый проход воркера VMS на домене: слот domain/vms/worker, книги — пусто.")
    site.domainpart.pass_once()
    log.note("Первый проход агента держателя: он читает своё хранилище сам (DOMAIN_CONFIG_URL), отчёта не пишет.")
    site.sync("srv")


def s02_members_knock(site) -> None:
    log = site.log
    site.wall.advance(60)
    log.note("Сцена 2. Члены стучатся.\n"
             "Офисы поднимают свои юниты: консоль кластера и агента с дверью ретранслятора (RELAY=1, REPORT=1,\n"
             "DOMAIN_URL — дверь подписывающего). Агент делает ключ члена при первом старте и печатает его.")
    for office in ("relay-a", "relay-b"):
        site.cluster_console(office)
    for office in ("relay-a", "relay-b"):
        site.office_agent(office)
    log.note("Первый проход агента relay-a: он ищет держателя по консолям CLUSTERS (GET /api/held) и просит своё\n"
             "у двери домена (GET /api/carry/relay-a, подписано ключом члена).")
    site.sync("relay-a")
    log.note("Камеры: кластер из одного на своём флеше, ещё не загружен; агент камеры видит только свой офис\n"
             "(RELAY_URL — дверь ретранслятора relay-a:8446, REPORT=1).")
    for cam in ("cam-a", "cam-a2", "cam-b"):
        site.camera(cam)
    log.note("Первый проход агента cam-a: дверь ретранслятора его не знает.")
    site.sync("cam-a")
    log.note("Проход держателя: список членов не записан никем; стучащихся нет — агент, которому дверь отказала,\n"
             "отчёта не пишет (DomainAgent._sync выходит до отчёта).")
    site.domain_pass()


def s03_admitted(site) -> None:
    log = site.log
    site.wall.advance(60)
    log.note("Сцена 3. Анна входит, принимает членов, пишет топологию; ключи членов регистрирует оператор на srv.")
    site.login("anna")
    site.ask("anna", "GET", "domain console", "/domain/members")
    log.note("Ключ relay-a — сразу, как его напечатал агент: список членов ещё никем не записан, и команда его не пишет.")
    site.operator_key("relay-a")
    log.note("Анна принимает камеры: первая запись списка несёт членов из CLUSTERS (how: configuration) и камеру.")
    for cam in ("cam-a", "cam-a2", "cam-b"):
        site.ask("anna", "POST", "domain console", "/domain/members", {"name": cam})
    site.console_pass()
    log.note("Топология: центр srv, звёзд нет, камеры через свои офисы.")
    _, topo = site.ask("anna", "GET", "domain console", "/domain/topology")
    site.ask("anna", "PUT", "domain console", "/domain/topology",
             {"base_rev": topo.get("rev", 0), "centre": "srv", "star": [],
              "via": {"cam-a": "relay-a", "cam-a2": "relay-a", "cam-b": "relay-b"}})
    log.note("Ключи членов — оператор на srv, как их напечатали агенты.")
    for m in ("relay-a", "relay-b", "cam-a", "cam-a2", "cam-b"):
        site.operator_key(m)
    log.note("Права Анны на кластере офиса: консоль офиса проверит её токен по ключам и правам, что принесёт агент.\n"
             "Дверь — PUT /domain/grants/<кластер> консоли домена. FINDINGS.md, F1: дверь падает без ответа — проверка\n"
             "declared.guarded читает domain/vms/stream-clients/anna, а роли domainconsole это чтение запрещено.")
    site.ask("anna", "PUT", "domain console", "/domain/grants/relay-a",
             {"lines": [{"subject": "anna", "cap": "admin", "scope": "*"}]})
    log.note("Обход для сценария (не дверь): права пишет оператор на srv, как это делает команда продукта.")
    for c in ("srv", "relay-a", "relay-b"):
        site.operator_grants(c, [{"subject": "anna", "cap": "admin"}])
    log.note("Борис — зритель домена: человек — у подписывающего (POST /domain/users → /api/people/users).")
    site.passwords["boris"] = "boris-test-password"
    site.ask("anna", "POST", "domain console", "/domain/users", {"name": "boris", "password": "boris-test-password"})
    log.note("Его право view на домене — та же дверь PUT /domain/grants/domain и та же находка F1; обход — оператор.")
    site.ask("anna", "PUT", "domain console", "/domain/grants/domain",
             {"lines": [{"subject": "anna", "cap": "admin", "scope": "*"}, {"subject": "boris", "cap": "view", "scope": "*"}]})
    site.operator_grants("domain", [{"subject": "anna", "cap": "admin"}, {"subject": "boris", "cap": "view"}])
    log.note("Проход держателя: подписывающий следует за списком членов и топологией.")
    site.domain_pass()
    log.note("Проход агента relay-a: первый /api/carry → 200; затем он просит за своих членов (?for=cam-a, ?for=cam-a2),\n"
             "держит ответы в памяти и несёт сводный отчёт.")
    site.sync("relay-a")
    log.note("Проход агента cam-a: дверь ретранслятора отдаёт ему его строки, проверив подпись его ключом.")
    site.sync("cam-a")
    with log.muted():
        for n in ("relay-b", "cam-a2", "cam-b", "relay-a", "relay-b", "srv"):
            site.sync(n)


def s04_camera_boots(site) -> None:
    log = site.log
    site.wall.advance(60)
    log.note("Сцена 4. Камера cam-a (SN-A) загружается: кластер из одного (DeviceCluster.boot) — эпоха по CAS на флеше,\n"
             "строка vms/cameras/1 с ref=SN-A при первой загрузке, heartbeat и срез снапшота в RAM, дверь после публикации.\n"
             "Потом процесс камеры: карта — том card (kind: edge, cam: 1), запись 1-sd (home: card, when: offline),\n"
             "регистратор карты r-1 над кольцом камеры, толкатель, связанный с ним (ingest.camera_process).")
    site.boot("cam-a")
    log.note("Пять секунд жизни камеры: сенсор пишет в кольцо, толкатель смотрит в книги (их ещё нет), карта — по воротам.")
    for _ in range(5):
        site.wall.advance(1)
        site.camera_step("cam-a")
    log.note("Что регистратор карты говорит о себе: heartbeat r-1 в RAM камеры.")
    raw = site.cams["cam-a"].ram.get("rec/heartbeats/r-1")
    log.note(json.dumps(json.loads(raw), ensure_ascii=False, indent=1) if raw else "нет heartbeat")
    with log.muted():
        for cam in ("cam-a2", "cam-b"):
            site.boot(cam)


def s05_domain_learns(site) -> None:
    log = site.log
    site.wall.advance(10)
    log.note("Сцена 5. Домен узнаёт камеры. Отчёт камеры — в объекты её офиса (в курсе — запись в процессе; у продукта\n"
             "POST /api/member/cam-a в дверь ретранслятора), сводный отчёт офиса — в объекты держателя.")
    log.note("Офисы публикуют свой (пустой) снапшот — без него агент офиса не отчитывается (uplink.NotPublished).")
    for office in ("relay-a", "relay-b"):
        site.place(office)
    site.sync("cam-a")
    with log.muted():
        for cam in ("cam-a2", "cam-b"):
            site.sync(cam)
    log.note("Агент relay-a: свой отчёт и сводный отчёт за cam-a и cam-a2.")
    site.sync("relay-a")
    with log.muted():
        site.sync("relay-b")
    log.note("Проход держателя: подписывающий читает отчёты, оставляет вид; консоль домена читает тоже.")
    site.domain_pass()
    log.note("Анна смотрит камеры домена: откуда известно и сколько лет.")
    site.login("anna")
    site.ask("anna", "GET", "domain console", "/domain/vms/cameras")
    site.ask("anna", "GET", "domain console", "/domain/where/SN-A")


def s06_office_ready(site) -> None:
    log = site.log
    site.wall.advance(30)
    log.note("Сцена 6. Офис готов писать. Анна на консоли relay-a объявляет том disk и запись камеры SN-A по ref:.\n"
             "Консоль офиса проверяет её токен по ключам и правам, что принёс агент relay-a.")
    site.login("anna")
    site.ask("anna", "POST", "console relay-a", "/rec/volumes",
             {"name": "disk", "kind": "local", "url": site.cluster("relay-a").server.volume, "quota_bytes": 1 << 30,
              "server": "relay-a"}, headers={"Idempotency-Key": "relay-a-disk"})
    log.note("Регистратор офиса r-relay-a-1 стартует; приёмник и передатчик живут в нём (RecWorker.host_ingest).\n"
             "FINDINGS.md, F3: роли recworker не дано чтение книг, которые читают приёмник и передатчик\n"
             "(domain/vms/sources, upstream, asks) — на configstore передатчик не строится вовсе. В сценарии их ручка —\n"
             "роль recworker с этими чтениями сверх файла прав; каждая её строка помечена «(+F3)».")
    site.recorder("relay-a")
    site.ask("anna", "POST", "console relay-a", "/rec/recordings", {"name": "SN-A", "cam": "ref:SN-A"},
             headers={"Idempotency-Key": "relay-a-SN-A"})
    log.note("Регистратор берёт слот и том, говорит heartbeat; контроллер записей офиса ставит запись на него; регистратор\n"
             "запускает её и говорит heartbeat снова.")
    rec = site.recorders["relay-a"]
    with log.acting("recworker r-relay-a-1 on relay-a"):
        rec.lease_pass()
        rec.volume_pass()
        rec.heartbeat_once()
    site.place("relay-a")
    with log.acting("recworker r-relay-a-1 on relay-a"):
        rec.reconcile_once()
        rec.heartbeat_once()
    site.say_heartbeat("relay-a")
    with log.muted():
        site.ask("anna", "POST", "console relay-b", "/rec/volumes",
                 {"name": "disk", "kind": "local", "url": site.cluster("relay-b").server.volume, "quota_bytes": 1 << 30,
                  "server": "relay-b"}, headers={"Idempotency-Key": "relay-b-disk"})
        site.recorder("relay-b")
        site.ask("anna", "POST", "console relay-b", "/rec/recordings", {"name": "SN-B", "cam": "ref:SN-B"},
                 headers={"Idempotency-Key": "relay-b-SN-B"})
        r = site.recorders["relay-b"]
        r.lease_pass(); r.volume_pass(); r.heartbeat_once()
        site.place("relay-b")
        r.reconcile_once(); r.heartbeat_once()
        site.recorder("srv")
        site.recorders["srv"].heartbeat_once()


def s07_who_records(site) -> None:
    log = site.log
    site.wall.advance(20)
    log.note("Сцена 7. Кто пишет SN-A. Решение «камеру SN-A пишет кластер relay-a» — одно на камеру, у держателя\n"
             "(domain/vms/crossings). Двери у него в курсе нет: это вызов Crossings.record в процессе воркера VMS на домене\n"
             "(module-design.md М12B, открытый пункт 2); у продукта — POST /domain/vms/crossings {ref, on, move: true}\n"
             "консоли srv (stand.sh setup).")
    with log.muted():                                      # the offices' and the centre's recorders say where they take streams
        for name in ("relay-a", "relay-b", "srv"):
            site.recorders[name].heartbeat_once()
        site.agents_pass()
        site.holder.run_pass()
        site.console_pass()
    with log.acting("vmsdomain on srv"):
        got = site.crossings.record("SN-A", on="relay-a", move=True)
    log.note(f"→ {json.dumps(got, ensure_ascii=False)}")
    with log.muted():
        site.crossings.record("SN-B", on="relay-b", move=True)
    log.note("Проход воркера VMS на домене: книги sources (relay-a), primaries (cam-a: куда толкать и токен потока),\n"
             "polls, upstream (relay-a: куда передавать вверх, в центр); токены — у подписывающего, через его сокет токенов.")
    site.domainpart.pass_once()


def s08_books_home(site) -> None:
    log = site.log
    site.wall.advance(10)
    log.note("Сцена 8. Агенты несут книги домой: relay-a — свои (sources, upstream) и, по дороге, книги cam-a;\n"
             "cam-a — через дверь relay-a, токен потока запечатан ключу камеры.")
    site.sync("relay-a")
    site.sync("cam-a")
    with log.muted():
        for n in ("relay-b", "cam-a2", "cam-b", "srv"):
            site.sync(n)


def s09_stream_flows(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Сцена 9. Поток пошёл. Регистратор офиса хочет поток SN-A — в курсе этого шва нет: RecWorker.source ищет\n"
             "камеру в heartbeat'ах VMS своего кластера и пишет «camera held by nobody» (сцена 6); приёмник он не\n"
             "спрашивает. Здесь подписку делает сценарий, как тесты урока 16 (ingest.want + subscribe от имени регистратора).")
    ing = site.ingests["relay-a"]
    with log.acting("recworker r-relay-a-1 on relay-a"):
        ing.want("SN-A", "recorder:r-relay-a-1")
        site.taken = ing.subscribe("SN-A", "recorder:r-relay-a-1", maxsize=100000)
    log.note("Камера: опрос → «толкай» → толчок кадров из кольца; карта держится, пока поток берут.")
    for _ in range(3):
        site.wall.advance(1)
        out = site.camera_step("cam-a")
        log.note(f"толкатель cam-a: {json.dumps(out, ensure_ascii=False)}")
    got = site.taken.drain()
    log.note(f"подписчик в приёмнике relay-a получил {len(got)} кадров")
    rec = site.recorders["relay-a"]
    with log.acting("recworker r-relay-a-1 on relay-a"):
        rec.heartbeat_once()
    site.say_heartbeat("relay-a")
    key = "rec/polled/" + "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in site.ingest_url("relay-a"))
    raw = rec.objects.get(key)
    log.note(f"свидетель для тревог {key} (объект на relay-a): " + (raw.decode() if raw else "нет"))
    cam = site.cams["cam-a"]
    cam.rec.heartbeat_once()
    hb = json.loads(cam.ram.get("rec/heartbeats/r-1"))
    log.note("регистратор карты r-1: " + json.dumps({"status": [{k: st.get(k) for k in ("id", "phase", "hold", "why")}
                                                              for st in hb["status"]], "stream": hb.get("stream")},
                                                            ensure_ascii=False, indent=1))


def s10_watching(site) -> None:
    from vms.domainpart.ingest import LINGER
    log = site.log
    site.wall.advance(5)
    log.note("Сцена 10. Борис смотрит SN-A из центра. Шлюз в центре — модель курса (domainpart/gateway.py поверх\n"
             "приёмника srv); у продукта — RTSP-раздача приёмника rtsp://srv/ingest/SN-A и WHEP (VMS_LIVE_HTTP). Открыть\n"
             "раздачу — значит захотеть поток: желание идёт вниз (центр → офис → камера), поток вверх.")
    site.login("boris")
    gw = site.gateway()
    with log.acting("gateway gw-centre on srv"):
        view = gw.watch("SN-A", site.tokens["boris"], "boris", maxsize=100000)
    log.note("Передатчик relay-a держит опрос у приёмника центра: центр хочет SN-A — значит, и офис хочет его от камеры.")
    log.note("в курсе передатчик ходит в приёмник центра вызовом (dial), у продукта — тот же опрос и толчок по HTTP")
    site.forward("relay-a")
    log.note("Камера толкает как толкала — один поток в офис; передатчик несёт его вверх.")
    for _ in range(2):
        site.wall.advance(1)
        site.camera_step("cam-a")
        site.forward("relay-a")
    with log.acting("gateway gw-centre on srv"):
        gw.pump()
    log.note(f"Борис получил {len(view.drain())} кадров — живой край, не кольцо.")
    log.note("Борис ушёл: желание живёт ещё LINGER = 10 с, потом центр не хочет SN-A, и офис перестаёт нести его вверх.")
    with log.acting("gateway gw-centre on srv"):
        gw.leave("SN-A", "boris")
        site.ingests["srv"].release("SN-A", "gw-centre")
    site.wall.advance(LINGER + 1)
    site.camera_step("cam-a")
    site.forward("relay-a")
    rec = site.recorders["relay-a"]
    with log.acting("recworker r-relay-a-1 on relay-a"):
        rec.heartbeat_once()
    site.say_heartbeat("relay-a", fields=("upstream",))


SCENARIO = {"when": {"camera": "SN-A2", "kind": "vehicle"},
            "then": {"camera": "SN-B", "action": "preset", "arg": 3, "within": 10}}


def s11_scenario(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Сцена 11. Сценарий между объектами: «машина у ворот (cam-a2, объект A) — камера cam-b на объекте B в пресет 3».\n"
             "Сценарий — документ auto в общих настройках домена (PUT /domain/shared → подписывающий проверяет и подписывает).")
    site.login("anna")
    _, shared = site.ask("anna", "GET", "domain console", "/domain/shared")
    rev = int((shared.get("doc") or {}).get("rev", 0)) if isinstance(shared, dict) else 0
    site.ask("anna", "PUT", "domain console", "/domain/shared",
             {"base_rev": rev, "shared": {"auto": {"scenarios": [SCENARIO]}}})
    log.note("Проход держателя: воркер VMS на домене строит книгу запросов — cam-a2 может спросить cam-b, дорогой через\n"
             "свой офис relay-a и вверх, в центр (up: srv); relay-a получает право нести эту пару; токены «ask».")
    site.holder.run_pass()
    site.domainpart.pass_once()
    log.note("Агенты несут книги и документ домой: relay-a — свою книгу запросов и книги cam-a2, cam-a2 — документ и книгу.")
    site.sync("relay-a")
    site.sync("cam-a2")
    with log.muted():
        site.agents_pass()
    log.note("Событие на cam-a2: машина. Камера оставляет запрос у приёмника своего офиса (в курсе — вызов\n"
             "Scenarios.on_event; у продукта — событие прошивки GET /api/v1/events → запрос POST /ingest/SN-B/ask).")
    sc = site.scenarios("cam-a2")
    with log.acting("automation on cam-a2"):
        left = sc.on_event("vehicle")
    log.note("→ " + json.dumps([{k: v for k, v in x.items() if k != "ingest"} for x in left], ensure_ascii=False))
    log.note("Передатчик relay-a, разбуженный запросом, несёт его в центр.")
    with log.acting("forwarder in r-relay-a-1 on relay-a"):
        lifted = site.recorders["relay-a"].forwarder.lift()
    log.note(f"→ {json.dumps(lifted, ensure_ascii=False)}")
    log.note("Передатчик relay-b держит опрос у центра за SN-B: запрос приходит в ответе и спускается в приёмник relay-b.")
    site.forward("relay-b")
    log.note("cam-b на своём опросе получает запрос и выполняет его.")
    site.wall.advance(1)
    out = site.camera_step("cam-b")
    log.note(f"толкатель cam-b: asks = {json.dumps(out.get('asks'), ensure_ascii=False)}")
    log.note("Исход назад: relay-b — в центр, relay-a — из центра к спросившей камере.")
    with log.acting("forwarder in r-relay-b-1 on relay-b"):
        site.recorders["relay-b"].forwarder.lift()
    with log.acting("forwarder in r-relay-a-1 on relay-a"):
        site.recorders["relay-a"].forwarder.lift()
    x = next((x for x in left if x.get("target") == "SN-B"), None)
    if x and x.get("ask"):
        with log.acting("automation on cam-a2"):
            outcome = sc.asker.outcome("SN-B", x["ask"], x["deadline"])
        log.note(f"cam-a2 читает исход своего запроса: {outcome}")


def s12_alarm(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Сцена 12. Тревога с камеры. У cam-a2 мало памяти: кольцо держит ~20 с её потока, а карте, чтобы начало\n"
             "обрыва попало на неё, нужно 50 с (обрыв замечают через LOST_AFTER + запас). Регистратор карты поднимает\n"
             "тревогу card.prebuffer.short — событие на карте камеры.")
    with log.muted():
        for _ in range(25):
            site.wall.advance(1)
            site.camera_step("cam-a2")
    cam = site.cams["cam-a2"]
    with log.acting("recworker r-1 on cam-a2"):
        short = cam.rec.prebuffer_pass()
    log.note(f"prebuffer_pass: {json.dumps(short)}")
    from w2cplatform.domain.alarms import Card
    page = Card("rec", cam.events).alarms(site.wall() - 3600, site.wall() + 1, 10)
    log.note("на карте cam-a2: " + json.dumps(page, ensure_ascii=False))
    agent = site.agents["cam-a2"]
    log.note(f"Агент cam-a2 спрашивает раз в секунду, нет ли на карте тревоги новее его последнего отчёта: due() = "
             f"{agent.due()} — и отчитывается сразу, не дожидаясь прохода (report_now).")
    with log.acting("domainagent on cam-a2"):
        agent.report_now()
    log.note("Офис relay-a несёт сводный отчёт; держатель держит неделю тревог; Анна смотрит список домена.")
    site.sync("relay-a")
    site.holder.run_pass()
    site.console_pass()
    site.login("anna")
    site.ask("anna", "GET", "domain console", "/domain/alarms")


# -- the failure scenes: each its own run from the end of the happy path ---------------------------------------------------
def _card_said(site, name: str) -> str:
    cam = site.cams[name]
    cam.rec.heartbeat_once()
    hb = json.loads(cam.ram.get("rec/heartbeats/r-1"))
    st = next((x for x in hb["status"] if x["id"] == "1-sd"), {})
    keep = ("phase", "hold", "why", "card_segments", "card_bytes", "samples_written")
    return json.dumps({"1-sd": {k: st.get(k) for k in keep if k in st},
                       "stream": {k: v for k, v in (hb.get("stream") or {}).items()
                                  if k in ("state", "up", "behind_s", "owed_s", "owed_gaps", "cut_s", "left_s")}},
                      ensure_ascii=False)


def _cameras_seen(site, who: str = "anna") -> None:
    st, got = site.ask(who, "GET", "domain console", "/domain/vms/cameras")
    if isinstance(got, dict):
        site.log.note("консоль домена: " + json.dumps({"clusters": got.get("clusters"), "complete": got.get("complete"),
                                                       "why": got.get("why")}, ensure_ascii=False))


def f01_office_off(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Отказ 1. Офис relay-a выключен на пять минут. Камеры за ним толкают в никуда; их книги стареют (агент\n"
             "камеры не доходит до двери офиса), и карта 1-sd (when: offline) пишет; центр видит молчание офиса и его\n"
             "камер разом.")
    site.login("anna")
    site.off("relay-a")
    log.note("relay-a выключен. Первый шаг cam-a после этого:")
    site.wall.advance(1)
    out = site.camera_step("cam-a")
    log.note(f"толкатель cam-a: {out.get('state')}")
    site.sync("cam-a")
    log.note("Шестьдесят секунд (свёрнуто: шаги камер, проходы агентов и держателя).")
    with log.muted():
        site.tick(60)
    log.note("карта cam-a: " + _card_said(site, "cam-a"))
    site.holder.run_pass()
    site.console_pass()
    _cameras_seen(site)
    log.note("Ещё четыре минуты (свёрнуто).")
    with log.muted():
        site.tick(240)
    log.note("карта cam-a: " + _card_said(site, "cam-a"))
    log.note("relay-a включён. Офис встаёт: регистратор, передатчик, агент; камера возвращается к приёмнику.")
    site.on("relay-a")
    rec = site.recorders["relay-a"]
    with log.acting("recworker r-relay-a-1 on relay-a"):
        rec.heartbeat_once()
    site.wall.advance(1)
    out = site.camera_step("cam-a")
    log.note(f"толкатель cam-a: {json.dumps({k: out.get(k) for k in ('state', 'pushed', 'continue')}, ensure_ascii=False)}")
    site.sync("relay-a")
    site.sync("cam-a")
    with log.muted():
        site.tick(30)
    log.note("карта cam-a через 30 с: " + _card_said(site, "cam-a"))
    site.holder.run_pass()
    site.console_pass()
    _cameras_seen(site)


def f02_camera_road(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Отказ 2. Обрыв камера → офис: на минуту, потом на полчаса. Короткий обрыв продолжается из памяти камеры\n"
             "(кольцо, have); длиннее кольца — карта и дозапись по слову камеры (ADR-0040).")
    site.login("anna")
    site.cut_road("cam-a", "relay-a")
    log.note("Дорога cam-a — relay-a перерезана.")
    site.wall.advance(1)
    out = site.camera_step("cam-a")
    log.note(f"толкатель cam-a: {out.get('state')}")
    with log.muted():
        site.tick(59, cams=("cam-a",))
    site.mend_road("cam-a", "relay-a")
    log.note("Минута прошла, дорога вернулась. Первый шаг:")
    site.wall.advance(1)
    out = site.camera_step("cam-a")
    log.note(f"толкатель cam-a: {json.dumps({k: out.get(k) for k in ('state', 'pushed', 'continue', 'behind')}, ensure_ascii=False)}")
    with log.muted():
        site.tick(20, cams=("cam-a",))
    log.note("карта cam-a: " + _card_said(site, "cam-a"))
    log.note("Теперь на полчаса (свёрнуто).")
    site.cut_road("cam-a", "relay-a")
    with log.muted():
        site.tick(1800, step=10, cams=("cam-a",))
    log.note("карта cam-a в конце обрыва: " + _card_said(site, "cam-a"))
    site.mend_road("cam-a", "relay-a")
    log.note("Дорога вернулась. Первый шаг:")
    site.wall.advance(1)
    out = site.camera_step("cam-a")
    log.note(f"толкатель cam-a: {json.dumps({k: out.get(k) for k in ('state', 'pushed', 'continue', 'behind')}, ensure_ascii=False)}")
    with log.muted():
        site.tick(30, cams=("cam-a",))
    log.note("карта cam-a: " + _card_said(site, "cam-a"))


def f03_uplink(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Отказ 3. Обрыв офис → центр. Запись в офисе идёт; зритель в центре теряет поток; передатчик держит\n"
             "FORWARD_HOLD = 10 с несданного и повторяет без дублей; книги камер за офисом стареют — офис говорит их возраст.")
    site.login("boris")
    gw = site.gateway()
    with log.acting("gateway gw-centre on srv"):
        view = gw.watch("SN-A", site.tokens["boris"], "boris", maxsize=100000)
    with log.muted():
        site.tick(10, cams=("cam-a",))
    with log.acting("gateway gw-centre on srv"):
        gw.pump()
    log.note(f"Борис смотрит: {len(view.drain())} кадров за 10 с. Дорога relay-a — srv перерезана.")
    site.cut_road("relay-a", "srv")
    site.wall.advance(1)
    site.camera_step("cam-a")
    site.forward("relay-a")
    site.sync("relay-a")
    with log.muted():
        site.tick(30, cams=("cam-a",))
    with log.acting("gateway gw-centre on srv"):
        gw.pump()
    log.note(f"Борис за 30 с обрыва получил {len(view.drain())} кадров. Офис пишет: подписчик в приёмнике relay-a "
             f"получил {len(site.taken.drain())} кадров.")
    site.sync("cam-a")
    raw = site.cams["cam-a"].ram.get("domain/seen")
    log.note("cam-a знает, сколько лет его книгам (domain/seen в RAM): " + (raw.decode() if raw else "нет"))
    site.mend_road("relay-a", "srv")
    log.note("Дорога вернулась.")
    site.wall.advance(1)
    site.camera_step("cam-a")
    site.forward("relay-a")
    with log.acting("gateway gw-centre on srv"):
        gw.pump()
    log.note(f"Борис снова получает: {len(view.drain())} кадров.")
    rec = site.recorders["relay-a"]
    rec.heartbeat_once()
    site.say_heartbeat("relay-a", fields=("upstream",))


def f04_centre_off(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Отказ 4. Центр srv выключен на шесть часов. Запись идёт по книгам и ключу потока, который камеры и офисы\n"
             "уже несут; нового входа нет; книги стареют.")
    site.login("anna")
    entry = site.cams["cam-a"].pusher.entry()
    until = float(entry["ingest"]["until"])
    log.note(f"Токен потока cam-a действует до {until:.0f} — ещё {until - site.wall():.0f} с от выключения.")
    site.off("srv")
    log.note("srv выключен. Анна стучится в консоль домена; агент relay-a — в дверь подписывающего:")
    site.ask("anna", "GET", "domain console", "/domain/vms/cameras")
    site.sync("relay-a")
    log.note("Шесть часов (свёрнуто: камеры толкают, офисы пишут, агенты не доходят до домена).")
    with log.muted():
        site.tick(6 * 3600, step=60, cams=("cam-a",), offices=("relay-a",), agents_every=300)
    log.note("Через шесть часов: камера толкает по прежнему токену, офис принимает.")
    site.wall.advance(1)
    out = site.camera_step("cam-a")
    log.note(f"толкатель cam-a: {out.get('state')}; токен действует ещё {until - site.wall():.0f} с")
    log.note(f"На исходе суток токена ({until:.0f}) приёмник откажет камере: новый токен выдаёт только держатель, на\n"
             "проходе книг после половины срока токена.")
    site.on("srv")
    log.note("srv включён: проходы держателя, книги, агенты.")
    site.domain_pass()
    site.sync("relay-a")
    site.sync("cam-a")
    site.domain_pass()
    site.login("anna")                                     # her token of six hours ago lived 900 s
    _cameras_seen(site)


def f07_camera_reboot(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Отказ 7. Камера cam-a перезагрузилась. Эпоха +1 по CAS на флеше, RAM пуста — heartbeat и срез снапшота\n"
             "публикуются заново, дверь после публикации; процесс камеры — новое кольцо, регистратор карты, толкатель.\n"
             "Шаг часов камеры в стенде не показан: у камеры стенда нет своих часов (часы стенда одни).")
    site.reboot("cam-a")
    site.wall.advance(1)
    out = site.camera_step("cam-a")
    log.note(f"толкатель cam-a после загрузки: {json.dumps({k: out.get(k) for k in ('state', 'pushed')}, ensure_ascii=False)}")
    site.sync("cam-a")
    site.sync("relay-a")
    site.domain_pass()
    site.login("anna")
    _, got = site.ask("anna", "GET", "domain console", "/domain/vms/cameras")


def f08_centre_restart(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Отказ 8. Регистратор центра (а с ним приёмник центра) перезапустился посреди потока, который смотрит Борис.")
    site.login("boris")
    gw = site.gateway()
    with log.acting("gateway gw-centre on srv"):
        view = gw.watch("SN-A", site.tokens["boris"], "boris", maxsize=100000)
    with log.muted():
        site.tick(10, cams=("cam-a",))
    log.note("Процесс r-srv-1 перезапущен: новый приёмник, память пуста.")
    with log.muted():
        site.cluster("srv").recorders = None
    site.recorder("srv")
    site.recorders["srv"].heartbeat_once()
    site._gateway = None
    gw = site.gateway()
    with log.acting("gateway gw-centre on srv"):
        view = gw.watch("SN-A", site.tokens["boris"], "boris", maxsize=100000)
    for _ in range(2):
        site.wall.advance(1)
        site.camera_step("cam-a")
        site.forward("relay-a")
    with log.acting("gateway gw-centre on srv"):
        gw.pump()
    log.note(f"Борис снова получает: {len(view.drain())} кадров.")
    rec = site.recorders["relay-a"]
    rec.heartbeat_once()
    site.say_heartbeat("relay-a", fields=("upstream",))
    site.recorders["srv"].heartbeat_once()
    site.say_heartbeat("srv", fields=("ingest", "ingest_streams"))


def f10_member_leaves(site) -> None:
    log = site.log
    site.wall.advance(5)
    log.note("Отказ 10. Член уходит: Анна удаляет cam-a2 из списка членов. Следующий проход держателя его не читает;\n"
             "дверь домена ему больше ничего не отдаёт.")
    site.login("anna")
    site.ask("anna", "DELETE", "domain console", "/domain/members/cam-a2")
    site.domain_pass()
    site.sync("relay-a")
    site.sync("cam-a2")
    _cameras_seen(site)


SCENES = {
    "01-founding": s01_founding,
    "02-members-knock": s02_members_knock,
    "03-admitted": s03_admitted,
    "04-camera-boots": s04_camera_boots,
    "05-domain-learns": s05_domain_learns,
    "06-office-ready": s06_office_ready,
    "07-who-records": s07_who_records,
    "08-books-home": s08_books_home,
    "09-stream-flows": s09_stream_flows,
    "10-watching": s10_watching,
    "11-scenario": s11_scenario,
    "12-alarm": s12_alarm,
    "f01-office-off": f01_office_off,
    "f02-camera-road": f02_camera_road,
    "f03-uplink": f03_uplink,
    "f04-centre-off": f04_centre_off,
    "f07-camera-reboot": f07_camera_reboot,
    "f08-centre-restart": f08_centre_restart,
    "f10-member-leaves": f10_member_leaves,
}


def before(name: str) -> list[str]:
    """The scenes played before `name`: the happy path up to it; a failure scene (`f…`) after all of it."""
    names = list(SCENES)
    happy = [n for n in names if not n.startswith("f")]
    if name.startswith("f"):
        return happy
    return names[:names.index(name)]
