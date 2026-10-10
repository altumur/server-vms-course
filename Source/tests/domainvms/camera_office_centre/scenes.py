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
             {"name": "disk", "kind": "local", "url": f"file:///data/relay-a/objectstorage", "quota_bytes": 1 << 30,
              "server": "relay-a"}, headers={"Idempotency-Key": "relay-a-disk"})
    log.note("Регистратор офиса r-relay-a-1 стартует; приёмник и передатчик живут в нём (RecWorker.host_ingest).")
    site.recorder("relay-a")
    site.ask("anna", "POST", "console relay-a", "/rec/recordings", {"name": "SN-A", "cam": "ref:SN-A"},
             headers={"Idempotency-Key": "relay-a-SN-A"})
    log.note("Контроллер записей офиса ставит запись на регистратор; регистратор берёт том, слот, говорит heartbeat.")
    site.place("relay-a")
    rec = site.recorders["relay-a"]
    with log.acting("recworker r-relay-a-1 on relay-a"):
        rec.lease_pass()
        rec.volume_pass()
        rec.reconcile_once()
        rec.heartbeat_once()
    with log.muted():
        site.ask("anna", "POST", "console relay-b", "/rec/volumes",
                 {"name": "disk", "kind": "local", "url": "file:///data/relay-b/objectstorage", "quota_bytes": 1 << 30,
                  "server": "relay-b"}, headers={"Idempotency-Key": "relay-b-disk"})
        site.recorder("relay-b")
        site.ask("anna", "POST", "console relay-b", "/rec/recordings", {"name": "SN-B", "cam": "ref:SN-B"},
                 headers={"Idempotency-Key": "relay-b-SN-B"})
        site.place("relay-b")
        r = site.recorders["relay-b"]
        r.lease_pass(); r.volume_pass(); r.reconcile_once(); r.heartbeat_once()
        site.recorder("srv")
        site.recorders["srv"].heartbeat_once()


SCENES = {
    "01-founding": s01_founding,
    "02-members-knock": s02_members_knock,
    "03-admitted": s03_admitted,
    "04-camera-boots": s04_camera_boots,
    "05-domain-learns": s05_domain_learns,
    "06-office-ready": s06_office_ready,
}


def before(name: str) -> list[str]:
    """The scenes played before `name`: the happy path up to it; a failure scene (`f…`) after all of it."""
    names = list(SCENES)
    happy = [n for n in names if not n.startswith("f")]
    if name.startswith("f"):
        return happy
    return names[:names.index(name)]
