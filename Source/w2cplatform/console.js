// The platform's console module — what every console page is built from: the platform's own minimal page
// (console.html: this module and nothing else) and a subsystem's page, which mounts it and adds its own.
// The contract is the course's КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md; this file is version 1 of it.
//
// What the module knows is the spec and the platform's doors: /spec and the specs /mounts carries, the units
// of each (/<rows>), where a unit is (/where), the servers (/servers), the session (/session), the units'
// events (/events, /marks). It names no subsystem: what a unit is called, how its fields are explained, how
// the kinds of its events read — all of that comes from the spec's `display`, as data. A page that has more
// to show (bytes, players, its own tables) adds it through the calls below; those are the page calling this
// library inside itself, not the platform calling a subsystem.
//
// `display` and `about` are the spec's alone; the session's grants are /session's. `may` says yes when the
// session names no grants: the server decides.
(function () {
  "use strict";
  const VERSION = 1;

  // The platform's own words, per language. A subject's words come from the spec.
  const WORDS = {
    en: {
      // the frame: header, rail, panel, footer, sign-in
      unsaved: "Unsaved changes of the selected object", discarded: "Cancelled",
      serverUnsaid: "server not named",
      newRoot: "group", newSub: "subgroup", newGroupTop: "A new group", newGroupIn: "A new group inside «{p}»", groupNameEmpty: "Give the group a name",
      groupExists: "There is such a group already", newGroupNoteT: "The group is made — put a {u} in it, or it will not be kept", addHereT: "Add a {u} here",
      noRows: "No rows",
      deleted: "Deleted",
      slotTitle: "Slot", slotReleased: "released", slotHung: "hung", slotUnknown: "alive or not — unknown", leaseTill: "Lease until", leaseGarbled: "the term cannot be read",
      volumesW: "Places held", conflictHead: "Name conflict: the name is held by {h}", onMachine: "on the machine", slotNameless: "waits for its name (nameless)",
      slotRefused: "refused: the name is taken", alreadyW: "for", nameAdvice2: "Such a process takes no new number: two processes under one name would write the same. Stop the extra process or give it another name.",
      hungNote: "The worker hung{s}: the server's resource says the process is alive, and there is no pulse. Its units are not moved, so that they never have two writers, until the limit (15 min by default).",
      unknownNote: "Whether the worker is alive is unknown{s}: no pulse, and the server's resource cannot say whether its process runs ({p}). Its units are not moved, so that they never have two writers, until the limit (15 min by default).",
      garbledNote: "The slot's lease term cannot be read.", releasedNote: "The slot is released by the controller: it gets no units, the name is free for a new process.",
      workersOutNote: "Workers are retired by the controller. If the server will never come back, decommission it in the server's card.",
      sinceW: "since",
      groupContents: "Contents", inNoGroupSuffix: "in no group", groupEmpty: "Empty", pathW: "Path", insideW: "inside",
      pickTitle: "Pick an object in the tree", serversInCluster: "servers in the cluster", serversN: "Servers", resOnlineN: "Resources online",
      unitsOnServer: "Units on a server", schemaVer: "Store layout version", buildsW: "builds", silentProcs: "Silent: {p} — too early to raise the layout version.",
      drainingNow: "Being drained", canStop: "may be stopped", notAllMoved: "not everything has moved yet",
      whyLabels: "none of the {n} live workers covers the labels: {l}", whyLive: "live workers it could go to: {n}", notPlacing: "Not placed",
      noWorkerSuffix: "without a worker", allPlaced: "Everything is placed", serversNets: "Servers' networks", noServers: "No servers",
      unplacedNote: "The controller places a unit at its next pass. If it stays here, see whether there is a live worker whose labels cover the unit's, and whether its server's resource answers.",
      srcConsole: "set in the console", srcUnknown: "the row cannot be read", srcNode: "from the node's settings", unknownW: "unknown",
      centreTip: "Centre: the top; units nobody records poll its receiver", starTip: "Star relay: it cannot be dialled; it takes its streams from the centre",
      viaTip: "Goes to the domain only through this relay", domSilentNote: "The domain is silent: its view was updated {a} ago. Below is the last it saw — not «nothing there».",
      longAgo: "long", listIncomplete: "The list is incomplete: {m} have not published for long. What they carry is shown by their last publication.",
      holderIs: "The domain's holder is", viewAge: "the view was updated", ago: "ago", knockTimes: "tried to publish {n} time(s), the last at {t}",
      knockNote: "The domain reads only its members. These clusters published through its agent but are not on the list: the domain does not read them until they are admitted.",
      alarmsDay: "for a day, newest first", holderHere: "the domain's holder (this console)", domainPage: "The domain's page",
      domainPageNote: "Edits of other clusters' units and decisions on which cluster carries what are the domain's:", accessTab: "Access",
      keysAsking: "Asking the console what the domain keeps in the store.", keysFailed: "Did not work", bW: "B", kbW: "KB", kVar: "variable", kItems: "items",
      kIndex: "index", kEmpty: "The row is empty.", kObj: "object", kKeys: "keys", kNone: "no record", kNowEmpty: "Empty now",
      keysIntro: "Everything the domain keeps in its holder's store under domain/: variables — its decisions and books; objects — its view and what members sent. Read only.",
      kfMembers: "Members of the domain", kfMembersAbout: "The domain's member list: who is admitted, how and since when.",
      kfMembersAbsent: "No record: the domain keeps the list from its configuration. It appears at the first edit of the list — when a cluster is admitted or taken out.",
      kfPublished: "Members' publications", kfPublishedAbout: "What each cluster's agent sent the domain itself: snapshots, heartbeats, the networks it sees. The domain does not call clusters — they publish.",
      kfReaches: "The holder's networks", kfReachesAbout: "The networks the domain's holder itself sees.", kfTopologyAbout: "The centre and the relay each cluster goes to the domain through. Edited on the «Overview» tab.",
      kfPending: "Edits waiting", kfPendingAbout: "Edits waiting for their cluster: the domain does not call it — the cluster's agent takes them itself.",
      kfOutcomes: "Outcomes of edits", kfOutcomesAbout: "How edits ended: each cluster's last answers.", kfView: "The domain's view",
      kfViewAbout: "The document the domain makes for people each pass: members, whether the list is complete, what they carry.", kfOther: "Other keys",
      kfOtherAbout: "Keys this page has no title for — as they lie in the store.", noReaches: "has not said", noOthers: "No other clusters in the domain.",
      writeW: "Write", clusterW: "Cluster", toDomain: "To the domain", seesNets: "Sees networks", relayFor: "Relay for", behindBy: "behind by", aheadBy: "ahead by",
      memberNote: "Every connection is opened by the cluster: it publishes its own and takes books and edits. The domain does not dial it.",
      inDomain: "In the domain", byConfigShort: "In the domain by its configuration", memberSub: "A cluster of its own, in the domain",
      domPlaced: "The domain is held by", termW: "term", backupKept: "This cluster keeps a backup copy of the domain: rev {r} of term {t}.", noBackupKept: "This cluster keeps no backup copy of the domain.",
      overview: "Overview", serverCap: "Server", resourceIs: "Resource", drainingBd: "being drained", workersN: "Workers", diskFree: "Disk free",
      diskTotal: "Disk total", buildW: "Build", eventsOnDisk: "Events on disk", gbW: "GB", idle: "idle by policy", workerSilent: "The worker does not answer",
      loadW: "Load", capW: "Capacity", freeW: "Free", labelsW: "Labels", idleNote: "Idle by the policy servers: {p}: units are carried by one worker per server.",
      holdsW: "Holds", carriesNone: "Carries nothing", drainTitle: "Drain", decomTitle: "Decommission", labelsTitle: "Server's networks (labels)",
      stOff: "Switched off", stUnplaced: "Not placed", stStale: "Worker silent", stFailed: "Failed", stRunning: "Running", stStarting: "Starting",
      workerServer: "Worker · server", state: "State", whyAsking: "Why here — asking the controller…", notPlacedYet: "Not placed anywhere yet.",
      placement: "Placement", noReason: "Placement: the controller's decision is not recorded.", inNoGroup: "In no group — it goes to «{g}».",
      noOtherGroups: "no other groups", newGroup: "New group", removeShort: "Remove",
      workersCap: "Workers", theme: "Theme", dark: "Dark", light: "Light", pollW: "Refresh", pollEvery: "every {n} s", manual: "by hand",
      refreshNow: "Refresh now", hint: "Only the selected object is saved", discard: "Cancel", hwSection: "Units", byGroups: "By groups",
      byGroupsHint: "Groups from the list field → units", byServers: "By servers", byServersHint: "Servers → workers and what they carry",
      filterPh: "Filter by name…", byName: "By name…", noLink: "no link", resOnline: "{a} of {b} resources online", subsystemW: "subsystem",
      loginAt: "Sign in at the domain's holder: ", noHolder: "This cluster knows no domain holder: only break-glass sign-in.", needLogin: "sign in",
      glassIntro: "Break-glass sign-in — when the domain is unreachable. Every attempt and every action is an alarm in the journal.",
      glassGo: "Break-glass sign-in", loginBtn: "Sign in", noConsole: "No link with the console", actions: "Actions", openIt: "Open",
      loadCap: "Load / capacity", srvShort: "srv.", goneW: "gone",
      units: "units", unit: "unit", servers: "servers", journal: "journal", pick: "Pick one", add: "Add", save: "Save",
      enable: "Enable", disable: "Disable", del: "Delete", events: "Events", mark: "Mark", markPh: "what you saw",
      unplaced: "unplaced", stale: "last known state", workers: "workers", noWorkers: "no workers", notPlaceable: "not placeable",
      resource: "resource", login: "Sign in", user: "User", password: "Password", refused: "refused", saved: "Saved",
      every: "every subsystem", deleteQ: "Delete", setKeeps: "set — empty keeps it", notSet: "not set", noEvents: "no events",
      policy: "servers", loading: "…", where: "why here", none: "—", worker: "worker", server: "server",
      labels: "Labels: the networks the server is plugged into", labelsConsole: "set in the console — placement reads these",
      labelsNode: "from the node's settings (LABELS / meta.labels): not set in the console", labelsUnknown: "the server's labels row cannot be read: which labels hold is unknown; nothing is moved by labels meanwhile",
      nodeSays: "the node says", noLabels: "none — the server reaches no network", backToNode: "Back to the node's labels",
      labelsMove: "units that need a label it loses move to a server that has it, a few a pass, or are left unplaced", labelsLose: "units on it it will no longer reach",
      drain: "Drain", drainOn: "Being drained", drained: "Drained: everything it carried is elsewhere — the machine may be stopped", draining: "Draining: some of it is still here",
      drainHelp: "for a server that comes back (maintenance, upgrade): its units leave and it waits; a server that will not come back is decommissioned (below)",
      undrain: "Back in service", otherDraining: "another server is being drained",
      decom: "Decommission", decomForever: "for good: the server is out of placement, its slots are released, its units move, what it held is lost with it",
      decomAsked: "decommission requested", decomDone: "decommissioned", decomBack: "Give the server back", decomNo: "cannot be decommissioned",
      decomAnswers: "the server answers again — the decommission is not carried out",
      gone: "The server is physically gone (burnt, removed) — I confirm", goneNote: "if the server is in fact alive behind a broken network, it sees the decommission and stops; it can be given back by withdrawing the decommission",
      doorQuiet: "its door does not answer: whether it is alive is unknown", goneMark: "confirmed gone",
      search: "search", allStates: "all states", running: "running", problems: "with problems", unplacedF: "unplaced",
      favs: "favourites", star: "Add to favourites", unstar: "Remove from favourites", nothingFound: "nothing found",
      full: "Full screen (Esc to leave)", rail: "Hide or show the sections", general: "General",
      addItem: "add", remove: "remove", newUnit: "New", create: "Create", created: "Created", retry: "Retry", group: "group", noGroup: "without a group", renameGroup: "Rename", newName: "New name", addToGroup: "Add to this group", unitsIn: "in it",
      removeFrom: "remove from the group", renamed: "Renamed", notAll: "not done for", pickUnit: "Which", groupHelp: "a group is a value of a list field: it exists while one unit carries it", retrying: "Sending it again…", done: "Done",
      // [course leads] a group the domain's shared settings offer (/domain/shared/<sub>)
      sharedGroup: "From the domain's shared settings (rev {r}): it is there with no unit in it",
      logout: "Sign out", glass: "Break-glass sign-in", glassWho: "Who", glassWhy: "Why", glassPass: "Break-glass password", glassOn: "Break-glass session for 15 minutes: every action goes into the journal as an alarm", normal: "Normal sign-in", open: "open console", secretSet: "set — an empty field keeps it; to change it, enter a new one", secretUnset: "not set", decomLost: "lost with the server", decomPass: "the controllers release its slots and move its units on their next pass",
      slot: "Slot", released: "released", hung: "hung", presence: "alive or not — unknown", leaseUntil: "lease until", holds: "holds", garbled: "the slot's lease cannot be read",
      hungSays: "the server's resource says the process runs, and there is no heartbeat: its units are not moved, so they never get two writers, until the bound runs out (15 min by default)",
      presenceSays: "no heartbeat, and the server's resource cannot say whether the process runs", releasedSays: "released by the controller: it gets no units; the name is free for a new process",
      workersOut: "workers are taken out by the controller; a server that will not come back is decommissioned on its card",
      nameConflict: "name conflict: held by", nameless: "waits for its name", refusedName: "refused: the name is taken", nameAdvice: "such a process takes no other number: stop the extra one or give it another name",
      boundAnew: "is bound to a field you changed: enter it anew — the one kept was for the old value",
      access: "access", people: "people", clusters: "clusters", domainWord: "domain", view: "view", edit: "act", admin: "manage",
      allUnits: "all", oneUnit: "one", byLabels: "with labels", noGrants: "no grants", grant: "Grant", revoke: "Revoke",
      newPerson: "New person", name: "Name", pass10: "Password (10 characters or more)", pass12: "Password (12 characters or more)",
      setPass: "Password", disabledW: "disabled", off: "Disable", on: "Enable", by: "by", howOidc: "the organisation's sign-in", howPass: "password",
      glass: "Break-glass password", glassSet: "break-glass password set", glassNone: "no break-glass password", who: "Who", what: "What", onWhat: "On what",
      scopeHelp: "* — all; unit:<sub>/<id> — one; labels:a,b — those with these labels", cancel: "Cancel", ok: "OK",
      grantNote: "a cluster gets it with its agent's next pass; a token issued earlier lives out its hour",
      deletePerson: "the person and all their grants on every cluster and on the domain are deleted; this cannot be undone",
      glassNote: "keep it apart from the site's computers; every use is an alarm in the cluster's journal",
      domain: "domain", noDomain: "this cluster is in no domain", holder: "holder", thisCluster: "this cluster", term: "term", backup: "backup copy",
      noBackup: "this cluster keeps no backup copy of the domain", move: "Move the domain here", moveHelp: "when the holder is dead: the newest copy anyone keeps, on a larger term; a live holder hands it over from its own page",
      members: "members", publishes: "publishes", readHere: "read in place", never: "never published", silentFor: "silent", domSilent: "the domain is silent",
      knocking: "asking to join", admit: "Admit", fingerprint: "key fingerprint", fpCheck: "compare it with the fingerprint the server itself shows (member key in its agent's log); a mismatch means someone else",
      leave: "Take out of the domain", leaveHelp: "from the next pass the domain does not read it; the cluster itself goes on working", reaches: "reaches", direct: "to the domain directly", via: "via relay",
      topology: "topology", centre: "centre", starW: "star", none2: "none — the top is the holder", rev: "revision", notWritten: "not written", cancel2: "Undo",
      topoHelp: "who goes through whom is the network's policy, written by the operator in one record; what a cluster reaches, it says itself",
      alarms: "alarms from every member", noAlarms: "no alarms", keys: "keys", lastPub: "last published", skew: "clock vs the domain",
      byList: "by the member list, revision", byConfig: "by the domain's configuration: no member list written yet",
      confirmQ: "Are you sure?", heard: "last heard", policyShared: "every worker carries units, two on one server included", policyDistinct: "one worker per server carries units",
      // the platform's own events: its servers and workers (a subsystem's kinds are its spec's display.kinds)
      kinds: {
        "server.decommission_requested": "server decommission requested", "server.decommission_withdrawn": "server decommission withdrawn",
        "server.decommissioned": "server decommissioned", "server.decommission_refused": "server decommission refused",
        "worker.released_by_controller": "the controller released a worker's slot", "worker.hung": "worker hung",
        "worker.hung_moved": "a hung worker's units moved", "worker.retire_requested": "worker retirement requested",
        "worker.name_taken": "a worker's name was taken", "worker.name_back": "a worker got its name back", "worker.name_conflict": "worker name conflict",
        "worker.presence_unknown": "whether a worker is alive is unknown", "worker.presence_unknown_moved": "the units of a worker without a pulse moved",
        "worker.slot_ahead": "a worker's slot lease ran ahead",
        "session.debug_open": "debug sign-in without a password is on",
      },
      // the domain's holder: its term, its trust, the units on the domain, the shared settings, the edits (§10a)
      domTerm: "Holding", heldOn: "The domain is held on", restoredFrom: "restored from backup rev {r} of {f}", backupAtW: "backup copy at",
      noBackupYet: "nobody yet", handOver: "Hand the domain over…", handTo: "To", handBtn: "Hand over",
      handNote: "For a few seconds edits are not taken; then the domain works there and this holder steps aside.",
      handing: "Handing over: the last copy goes to {t}…", handed: "Handed over", notHanded: "Not handed over",
      deposedNote: "This holder was replaced: the domain is held by {h} at term {t}. Edits go there, not here:",
      strandedHead: "Not in term {t} — apply again?", strandedNote: "Only this holder held these: after its last backup copy. Nothing is applied by itself — a person decides.",
      nothingStranded: "Nothing left behind: all this holder held is in term {t}.", reapplyOn: "Apply again at {h}", redoOn: "do it again at {h}",
      reapplied: "The edit is saved again at the new holder", editFor: "edit for",
      trustW: "Trust", notInstalled: "The domain is not installed: its door is open, nobody is asked who they are.", keysRev: "Key set revision",
      rootFp: "Root", currentKey: "Current key", issuingW: "Issuing keys", revokedW: "revoked", holderKeys: "The holder has the keys", yesW: "yes", noW: "no",
      admittedKey: "admitted", presentedKey: "presents", holdsRev: "holds rev", rotating: "rotation not finished",
      rotationNote: "A member whose revision is below the set's, or whose key is not the admitted one, has not finished the rotation.",
      domUnits: "Units", domUnitsNote: "What the subsystems hold in the domain's clusters, by their specs: the ref, the cluster, where it runs, its state.",
      noUnitsDecl: "no subsystem on the domain declared units", uLive: "running", uStale: "worker silent — last known", uConfigured: "configured, nobody holds it",
      uSilent: "cluster silent — last known", turnOn: "Turn on", turnOff: "Turn off",
      sharedW: "Shared settings", sharedNote: "Settings of the site, not of one unit: one document of the domain each member's agent carries home and keeps — the domain may go, the settings stay where they are read. They are defaults: they are not written into the units' rows.",
      sharedRev: "rev {r} · term {t} · {a}", neverPub: "never published yet", onePerLine: "one a line", publishW: "Publish",
      publishedRev: "Published: rev {r}. The agents carry it on their next pass", noSharedDecl: "no subsystem shares fields with the domain", noShared: "no shared settings here", notSetW: "not set",
      editsW: "Edits for the clusters", editsNote: "The domain calls no cluster: an edit waits here, the cluster's agent takes it on its next publication, applies it and sends back the outcome.",
      waitsPub: "waits for publication", appliedW: "applied", refusedStatus: "refused {s}", takenAt: "taken", appliedAt: "applied", noEdits: "no edits",
      debugBadge: "debug: no sign-in", debugTip: "The door let you in without a password: a request from this machine, W2C_DEBUG_PERSON is set (a stand only, ADR-0050). Your rights are this person's.",
      n: { asPerson: "as", on: "on", silent: "silent", unitsN: "units", noTwoWriters: "not moved, so that there are never two writers", movedAfter: "moved after",
        holds: "held by", leaseUntil: "lease until", pastLimit: "past the limit of", server: "server", lost: "lost",
        nameHeld: "the name is held by", waits: "this process waits for its name", namedAgain: "has its name again", after: "after", nameless: "without a name",
        refused: "refused", min: "min", s: "s" },
    },
    ru: {
      unsaved: "Несохранённые изменения выбранного объекта", discarded: "Отменено",
      serverUnsaid: "сервер не назван",
      newRoot: "группа", newSub: "подгруппа", newGroupTop: "Новая группа", newGroupIn: "Новая группа внутри «{p}»", groupNameEmpty: "Укажите имя группы",
      groupExists: "Такая группа уже есть", newGroupNoteT: "Группа создана — добавьте в неё: {u}, иначе она не сохранится", addHereT: "Добавить сюда: {u}",
      noRows: "Нет строк",
      deleted: "Удалено",
      slotTitle: "Слот", slotReleased: "отпущен", slotHung: "завис", slotUnknown: "жив ли — неизвестно", leaseTill: "Аренда до", leaseGarbled: "срок нечитаем",
      volumesW: "Держит места", conflictHead: "Конфликт имени: имя держит {h}", onMachine: "на машине", slotNameless: "ждёт своё имя (без имени)",
      slotRefused: "отказал: имя занято", alreadyW: "уже", nameAdvice2: "Нового номера такой процесс не берёт: два процесса под одним именем писали бы одно и то же. Остановите лишний процесс или дайте ему другое имя.",
      hungNote: "Воркер завис{s}: ресурс сервера говорит, что процесс жив, а пульса нет. Единицы с него не переносятся, чтобы у них не оказалось двух писателей, — пока не выйдет предел (по умолчанию 15 мин).",
      unknownNote: "Жив ли воркер — неизвестно{s}: пульса нет, а ресурс сервера не может сказать, работает ли его процесс ({p}). Единицы с него не переносятся, чтобы у них не оказалось двух писателей, — пока не выйдет предел (по умолчанию 15 мин).",
      garbledNote: "У слота нечитаемый срок аренды.", releasedNote: "Слот отпущен контроллером: единиц он не получит, имя свободно для нового процесса.",
      workersOutNote: "Воркеры выводит контроллер. Если сервер не вернётся никогда, спишите его в карточке сервера.",
      sinceW: "с",
      groupContents: "Состав группы", inNoGroupSuffix: "без группы", groupEmpty: "Пусто", pathW: "Путь", insideW: "внутри",
      pickTitle: "Выберите объект в дереве", serversInCluster: "серверов в кластере", serversN: "Серверов", resOnlineN: "Ресурсов на связи",
      unitsOnServer: "Юниты на сервере", schemaVer: "Версия раскладки хранилища", buildsW: "сборки", silentProcs: "Молчат: {p} — поднимать версию раскладки рано.",
      drainingNow: "Выводится из эксплуатации", canStop: "можно останавливать", notAllMoved: "ещё не всё уехало",
      whyLabels: "ни один из {n} живых воркеров не покрывает метки: {l}", whyLive: "живых воркеров, куда это можно поставить: {n}", notPlacing: "Не размещается",
      noWorkerSuffix: "без воркера", allPlaced: "Всё размещено", serversNets: "Сети серверов", noServers: "Серверов нет",
      unplacedNote: "Контроллер разместит единицу на следующем проходе. Если она висит здесь — смотрите, есть ли живой воркер, чьи метки покрывают её метки, и отвечает ли ресурс его сервера.",
      srcConsole: "заданы в консоли", srcUnknown: "строка не читается", srcNode: "из настройки узла", unknownW: "неизвестно",
      centreTip: "Центр: верхний уровень; единицы, которые никто не пишет, опрашивают его приёмник", starTip: "Ретранслятор-звезда: до него не дозвониться, свои потоки он забирает из центра",
      viaTip: "К домену ходит только через этот ретранслятор", domSilentNote: "Домен молчит: его вид обновлялся {a} назад. Ниже — последнее, что он видел; это не «ничего нет».",
      longAgo: "давно", listIncomplete: "Список неполный: {m} давно не публиковал(и). Их единицы показаны по последней публикации.",
      holderIs: "Держатель домена —", viewAge: "вид обновлён", ago: "назад", knockTimes: "пытался публиковаться {n} раз(а), последний раз {t}",
      knockNote: "Домен читает только своих членов. Эти кластеры его агентом публиковались, но в списке их нет: домен их не читает, пока их не примут.",
      alarmsDay: "за сутки, новые сверху", holderHere: "держатель домена (эта консоль)", domainPage: "Страница домена",
      domainPageNote: "Правки единиц других кластеров и решения «какой кластер что несёт» принимает домен:", accessTab: "Доступ",
      keysAsking: "Спрашиваем консоль, что домен держит в хранилище.", keysFailed: "Не получилось", bW: "Б", kbW: "КБ", kVar: "переменная", kItems: "строк",
      kIndex: "индекс", kEmpty: "Строка пуста.", kObj: "объект", kKeys: "ключ(ей)", kNone: "строки нет", kNowEmpty: "Сейчас пусто",
      keysIntro: "Всё, что домен держит в хранилище держателя домена под domain/: переменные — его решения и книги, объекты — его вид и то, что прислали члены. Только чтение.",
      kfMembers: "Члены домена", kfMembersAbout: "Список членов домена: кто принят, как и с какого времени.",
      kfMembersAbsent: "Строки нет: домен держит список из своей конфигурации. Она появится при первой правке списка — когда кластер примут в домен или выведут из него.",
      kfPublished: "Публикации членов", kfPublishedAbout: "Что агент каждого кластера сам прислал домену: снимки, сердцебиения, сети, которые кластер видит. Домен кластерам не звонит — они публикуются сами.",
      kfReaches: "Сети держателя домена", kfReachesAbout: "Сети, которые видит сам держатель домена.", kfTopologyAbout: "Центр и через какой ретранслятор каждый кластер ходит к домену. Правится на закладке «Обзор».",
      kfPending: "Правки в ожидании", kfPendingAbout: "Правки, которые ждут свой кластер: домен кластеру не звонит — агент кластера забирает их сам.",
      kfOutcomes: "Итоги правок", kfOutcomesAbout: "Чем кончились правки: последние ответы каждого кластера.", kfView: "Вид домена",
      kfViewAbout: "Документ, который домен составляет каждый проход для людей: члены, полнота списка, что они несут.", kfOther: "Прочие ключи",
      kfOtherAbout: "Ключи, для которых у этой страницы нет подписи, — как они лежат в хранилище.", noReaches: "сети не сообщал", noOthers: "Других кластеров в домене нет.",
      writeW: "Сохранить", clusterW: "Кластер", toDomain: "К домену", seesNets: "Видит сети", relayFor: "Ретранслятор для", behindBy: "отстают на", aheadBy: "спешат на",
      memberNote: "Все соединения открывает кластер: публикует своё, забирает книги и правки. Домен его не набирает.",
      inDomain: "В домене", byConfigShort: "В домене по конфигурации", memberSub: "Отдельный кластер, в домене",
      domPlaced: "Домен размещён:", termW: "срок", backupKept: "Этот кластер хранит резервную копию домена: rev {r} срока {t}.", noBackupKept: "Резервной копии домена этот кластер не хранит.",
      overview: "Обзор", serverCap: "Сервер", resourceIs: "Ресурс", drainingBd: "выводится из эксплуатации", workersN: "Воркеров", diskFree: "Диск свободно",
      diskTotal: "Диск всего", buildW: "Сборка", eventsOnDisk: "События на диске", gbW: "ГБ", idle: "простаивает по политике", workerSilent: "Воркер не отвечает",
      loadW: "Нагрузка", capW: "Ёмкость", freeW: "Свободно", labelsW: "Метки", idleNote: "Простаивает по политике servers: {p}: единицы несёт один воркер на сервер.",
      holdsW: "Держит", carriesNone: "Ничего не держит", drainTitle: "Вывод из эксплуатации", decomTitle: "Списание сервера", labelsTitle: "Сети сервера (метки)",
      stOff: "Выключена", stUnplaced: "Не размещена", stStale: "Воркер молчит", stFailed: "Ошибка", stRunning: "Работает", stStarting: "Запускается",
      workerServer: "Воркер · сервер", state: "Состояние", whyAsking: "Почему здесь — спрашиваем у контроллера…", notPlacedYet: "Пока никуда не размещена.",
      placement: "Размещение", noReason: "Размещение: контроллер не назвал причину.", inNoGroup: "Не в группе — попадёт в «{g}».",
      noOtherGroups: "других групп нет", newGroup: "Новая группа", removeShort: "Убрать",
      workersCap: "Воркеры", theme: "Тема", dark: "Тёмная", light: "Светлая", pollW: "Обновление", pollEvery: "каждые {n} с", manual: "вручную",
      refreshNow: "Обновить сейчас", hint: "Сохраняется только выбранный объект", discard: "Отменить", hwSection: "Объекты", byGroups: "По группам",
      byGroupsHint: "Группы из поля-списка → единицы", byServers: "По серверам", byServersHint: "Серверы → воркеры и то, что они несут",
      filterPh: "Фильтр по имени…", byName: "По имени…", noLink: "нет связи", resOnline: "{a} из {b} ресурсов на связи", subsystemW: "подсистема",
      loginAt: "Вход у держателя домена: ", noHolder: "Держатель домена этому кластеру не известен: войти можно только аварийно.", needLogin: "нужно войти",
      glassIntro: "Аварийный вход — когда домен недоступен. Каждая попытка и каждое действие — тревога в журнале.",
      glassGo: "Аварийный вход", loginBtn: "Войти", noConsole: "Нет связи с консолью", actions: "Действия", openIt: "Открыть",
      loadCap: "Нагрузка / ёмкость", srvShort: "серв.", goneW: "удалён",
      units: "единицы", unit: "единица", servers: "серверы", journal: "журнал", pick: "Выберите объект", add: "Добавить",
      save: "Сохранить", enable: "Включить", disable: "Выключить", del: "Удалить", events: "События", mark: "Отметить",
      markPh: "что вы увидели", unplaced: "не размещена", stale: "последнее известное состояние", workers: "воркеры",
      noWorkers: "воркеров нет", notPlaceable: "размещать нельзя", resource: "ресурс", login: "Вход", user: "Пользователь",
      password: "Пароль", refused: "Отказано", saved: "Сохранено", every: "все подсистемы", deleteQ: "Удалить",
      setKeeps: "задан — пусто оставляет прежний", notSet: "не задан", noEvents: "событий нет", policy: "серверы",
      loading: "…", where: "почему здесь", none: "—", worker: "воркер", server: "сервер",
      labels: "Метки: сети, в которые включён сервер", labelsConsole: "заданы в консоли — размещение читает их",
      labelsNode: "из настройки узла (LABELS / meta.labels): в консоли не задавались", labelsUnknown: "строку меток сервера не прочитать: какие метки действуют, неизвестно; по меткам пока ничего не переносится",
      nodeSays: "узел говорит", noLabels: "нет — сервер не видит ни одной сети", backToNode: "Вернуть метки узла",
      labelsMove: "единицы, которым нужна снятая метка, переедут на сервер с ней — по нескольку за проход — или станут неразмещёнными", labelsLose: "единицы на нём, которых он больше не увидит",
      drain: "Вывести из эксплуатации", drainOn: "Выводится", drained: "Сервер выведен: всё, что он нёс, уже в другом месте — машину можно останавливать", draining: "Сервер выводится: часть ещё на нём",
      drainHelp: "для сервера, который вернётся (обслуживание, обновление): единицы уходят, сервер ждёт возврата; сервер, который не вернётся, списывают (ниже)",
      undrain: "Вернуть в работу", otherDraining: "сейчас выводится другой сервер",
      decom: "Списать сервер", decomForever: "навсегда: сервер исключается из размещения, его слоты отпускаются, единицы переезжают, то, что он держал, утрачено вместе с ним",
      decomAsked: "списание запрошено", decomDone: "списан", decomBack: "Вернуть сервер", decomNo: "списать нельзя",
      decomAnswers: "сервер снова отвечает — списание не исполняется",
      gone: "Сервера физически больше нет (сгорел, вывезен) — подтверждаю", goneNote: "если сервер на самом деле жив за обрывом сети, он увидит списание и остановится; вернуть его можно отменой списания",
      doorQuiet: "его дверь не отвечает: жив ли он, неизвестно", goneMark: "подтверждено: сервера нет",
      search: "поиск", allStates: "все состояния", running: "работают", problems: "с проблемами", unplacedF: "не размещены",
      favs: "избранное", star: "В избранное", unstar: "Убрать из избранного", nothingFound: "ничего не найдено",
      full: "На весь экран (Esc — назад)", rail: "Скрыть или показать разделы", general: "Общее",
      addItem: "добавить", remove: "убрать", newUnit: "Новая", create: "Создать", created: "Создано", retry: "Повторить", group: "группа", noGroup: "без группы", renameGroup: "Переименовать", newName: "Новое имя", addToGroup: "Добавить в эту группу", unitsIn: "в ней",
      removeFrom: "убрать из группы", renamed: "Переименовано", notAll: "не сделано для", pickUnit: "Что", groupHelp: "группа — значение поля-списка: она есть, пока его несёт хоть одна единица", retrying: "Отправляю ещё раз…", done: "Выполнено",
      // [course leads] группа из общих настроек домена (/domain/shared/<sub>)
      sharedGroup: "Из общих настроек домена (rev {r}): есть и без единиц",
      logout: "Выйти", glass: "Аварийный вход", glassWho: "Кто входит", glassWhy: "Зачем", glassPass: "Пароль аварийного входа", glassOn: "Аварийный вход на 15 минут: каждое действие попадает в журнал как тревога", normal: "Обычный вход", open: "консоль открыта", secretSet: "задан — пустое поле оставляет его; чтобы сменить, впишите новый", secretUnset: "не задан", decomLost: "утрачено вместе с сервером", decomPass: "контроллеры отпустят слоты сервера и перенесут единицы на ближайшем проходе",
      slot: "Слот", released: "отпущен", hung: "завис", presence: "жив ли — неизвестно", leaseUntil: "аренда до", holds: "держит", garbled: "у слота нечитаемый срок аренды",
      hungSays: "ресурс сервера говорит, что процесс жив, а пульса нет: единицы не переносятся, чтобы у них не оказалось двух писателей, — пока не выйдет предел (по умолчанию 15 мин)",
      presenceSays: "пульса нет, а ресурс сервера не может сказать, работает ли процесс", releasedSays: "отпущен контроллером: единиц не получит, имя свободно для нового процесса",
      workersOut: "воркеры выводит контроллер; сервер, который не вернётся, списывают в его карточке",
      nameConflict: "конфликт имени: имя держит", nameless: "ждёт своё имя", refusedName: "отказал: имя занято", nameAdvice: "нового номера такой процесс не берёт: остановите лишний или дайте ему другое имя",
      boundAnew: "привязан к полю, которое вы изменили: впишите его заново — прежний был для старого значения",
      access: "права", people: "люди", clusters: "кластеры", domainWord: "домен", view: "смотреть", edit: "действовать", admin: "управлять",
      allUnits: "все", oneUnit: "одна", byLabels: "с метками", noGrants: "прав нет", grant: "Дать право", revoke: "Убрать",
      newPerson: "Новый пользователь", name: "Имя", pass10: "Пароль (10 символов и больше)", pass12: "Пароль (12 символов и больше)",
      setPass: "Пароль", disabledW: "отключён", off: "Отключить", on: "Включить", by: "кто", howOidc: "вход через провайдера организации", howPass: "пароль",
      glass: "Аварийный пароль", glassSet: "аварийный пароль задан", glassNone: "аварийного пароля нет", who: "Кому", what: "Что", onWhat: "На что",
      scopeHelp: "* — все; unit:<подсистема>/<id> — одна; labels:a,b — с этими метками", cancel: "Отмена", ok: "OK",
      grantNote: "кластер получит его со следующим проходом агента; выданный раньше токен доживает свой час",
      deletePerson: "пользователь и все его права на всех кластерах и на домене будут удалены; это не отменить",
      glassNote: "храните его отдельно от компьютеров площадки; каждое использование — тревога в журнале кластера",
      domain: "домен", noDomain: "этот кластер не в домене", holder: "держатель", thisCluster: "этот кластер", term: "срок", backup: "резервная копия",
      noBackup: "резервной копии домена этот кластер не держит", move: "Перенести домен сюда", moveHelp: "когда держатель умер: берётся самая новая копия, на новом сроке; живой держатель передаёт домен со своей страницы",
      members: "члены", publishes: "публикует", readHere: "читается на месте", never: "ещё не публиковал", silentFor: "молчит", domSilent: "домен молчит",
      knocking: "просятся в домен", admit: "Принять", fingerprint: "отпечаток ключа", fpCheck: "сверьте его с отпечатком, который показывает сам сервер (member key в логе его агента); не совпадает — это кто-то другой",
      leave: "Вывести из домена", leaveHelp: "со следующего прохода домен его не читает; сам кластер продолжает работать", reaches: "видит", direct: "к домену напрямую", via: "через ретранслятор",
      topology: "топология", centre: "центр", starW: "звезда", none2: "нет — верх это держатель домена", rev: "ревизия", notWritten: "не задавалась", cancel2: "Отменить",
      topoHelp: "кто через кого ходит — политика сети, её задаёт оператор одной правкой; что кластер видит, он сообщает сам",
      alarms: "тревоги со всех членов", noAlarms: "тревог нет", keys: "ключи", lastPub: "последняя публикация", skew: "часы относительно домена",
      byList: "по списку членов, ревизия", byConfig: "по конфигурации домена: списка членов ещё нет",
      confirmQ: "Уверены?", heard: "последний раз слышен", policyShared: "единицы несёт каждый воркер, два на одном сервере тоже", policyDistinct: "единицы несёт один воркер на сервер",
      kinds: {
        "server.decommission_requested": "запрошено списание сервера", "server.decommission_withdrawn": "списание сервера отменено",
        "server.decommissioned": "сервер списан", "server.decommission_refused": "списание сервера отклонено",
        "worker.released_by_controller": "контроллер отпустил слот воркера", "worker.hung": "воркер завис",
        "worker.hung_moved": "единицы зависшего воркера перенесены", "worker.retire_requested": "запрошено списание воркера",
        "worker.name_taken": "имя воркера забрали", "worker.name_back": "воркер вернул себе имя", "worker.name_conflict": "конфликт имени воркера",
        "worker.presence_unknown": "жив ли воркер — неизвестно", "worker.presence_unknown_moved": "единицы воркера без пульса перенесены",
        "worker.slot_ahead": "аренда слота воркера ушла вперёд",
        "session.debug_open": "отладочный вход без пароля включён",
      },
      domTerm: "Размещение", heldOn: "Домен размещён на", restoredFrom: "восстановлен из копии rev {r} с {f}", backupAtW: "резервная копия у",
      noBackupYet: "пока ни у кого", handOver: "Передать домен…", handTo: "Кому", handBtn: "Передать",
      handNote: "На несколько секунд правки не принимаются; затем домен работает там, а этот держатель отходит.",
      handing: "Передача: последняя копия — на {t}…", handed: "Передано", notHanded: "Не передано",
      deposedNote: "Этот держатель заменён: домен держит {h} на сроке {t}. Правки туда, здесь они не принимаются:",
      strandedHead: "Не вошло в срок {t} — применить заново?", strandedNote: "Это держал только этот держатель: после его последней резервной копии. Само ничего не применяется — решает человек.",
      nothingStranded: "Ничего не брошено: всё, что держал этот держатель, вошло в срок {t}.", reapplyOn: "Применить заново на {h}", redoOn: "сделайте заново на {h}",
      reapplied: "Правка снова сохранена на новом держателе", editFor: "правка для",
      trustW: "Доверие", notInstalled: "Домен не установлен: дверь открыта, никого не спрашивают, кто он.", keysRev: "Ревизия набора ключей",
      rootFp: "Корень", currentKey: "Текущий ключ", issuingW: "Ключи выдачи", revokedW: "отозваны", holderKeys: "Ключи у держателя", yesW: "да", noW: "нет",
      admittedKey: "принят", presentedKey: "предъявляет", holdsRev: "держит rev", rotating: "ротация не закончена",
      rotationNote: "Член, у которого ревизия ниже ревизии набора или предъявленный ключ не тот, что принят, ротацию не закончил.",
      domUnits: "Единицы", domUnitsNote: "Что подсистемы держат в кластерах домена — по их спекам: ссылка, кластер, где работает, в каком состоянии.",
      noUnitsDecl: "ни одна подсистема на домене не объявила единиц", uLive: "идёт", uStale: "воркер молчит — последнее известное", uConfigured: "настроена, никто не держит",
      uSilent: "кластер молчит — последнее известное", turnOn: "Включить", turnOff: "Выключить",
      sharedW: "Общие настройки", sharedNote: "Настройки площадки, а не одной единицы: один документ домена, который агент каждого члена уносит домой и хранит у себя — домен может пропасть, настройки остаются там, где их читают. Это умолчания: в строки единиц они не пишутся.",
      sharedRev: "rev {r} · срок {t} · {a}", neverPub: "ещё ни разу не публиковались", onePerLine: "по одному на строку", publishW: "Опубликовать",
      publishedRev: "Опубликовано: rev {r}. Агенты унесут его на следующем проходе", noSharedDecl: "ни одна подсистема не делит полей с доменом", noShared: "общих настроек здесь нет", notSetW: "не задано",
      editsW: "Правки для кластеров", editsNote: "Домен не звонит кластерам: правка ждёт здесь, агент кластера забирает её при следующей публикации, применяет у себя и присылает исход.",
      waitsPub: "ждёт публикации", appliedW: "применена", refusedStatus: "отказ {s}", takenAt: "принята", appliedAt: "применена", noEdits: "правок нет",
      debugBadge: "отладка: вход без пароля", debugTip: "Дверь впустила без пароля: запрос с этой машины, задан W2C_DEBUG_PERSON (только стенд, ADR-0050). Права — этого человека.",
      n: { asPerson: "как", on: "на", silent: "молчит", unitsN: "единиц", noTwoWriters: "не переносятся, чтобы не было двух писателей", movedAfter: "перенесены через",
        holds: "держит", leaseUntil: "аренда до", pastLimit: "дальше предела", server: "сервер", lost: "утрачены",
        nameHeld: "имя держит", waits: "этот процесс ждёт своё имя", namedAgain: "снова с именем", after: "после", nameless: "без имени",
        refused: "отказал", min: "мин", s: "с" },
    },
  };

  const h = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const isSecret = name => /_secret$/.test(name);
  const MASK = "***";
  const sleep = ms => new Promise(ok => setTimeout(ok, ms));
  const fmt = t => (t ? new Date(t * 1000).toLocaleString() : "—");


  // The console's icons: 16×16 drawings in the current colour. A page adds its own by name (addIcons) — its
  // decoration and its sections name them; a name nobody drew is a dot.
  const svgIc = d => `<svg class="ic-svg" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">${d}</svg>`;
  const ICONS = {
    sec_units: `<rect x="1.8" y="3" width="12.4" height="8.2" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M5.4 13.6h5.2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`,
    sec_access: `<circle cx="8" cy="5.2" r="2.7" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2.9 14c0-2.8 2.3-4.4 5.1-4.4s5.1 1.6 5.1 4.4" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`,
    sec_journal: `<path d="M2.6 4.2h10.8M2.6 8h10.8M2.6 11.8h7.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
    domain: `<path fill="currentColor" d="M8 1.2 1.5 5.2v1.2h1.3V14h4.2V9.2h2V14h4.2V6.4H14.5V5.2z"/>`,
    unalloc: `<rect x="2" y="2" width="12" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4" stroke-dasharray="2.2 1.6"/>`,
    server: `<path fill="currentColor" d="M4.2 1.5h7.6c.6 0 1.1.5 1.1 1.1v11c0 .5-.4.9-.9.9H4c-.5 0-.9-.4-.9-.9v-11c0-.6.5-1.1 1.1-1.1zm1.3 1.6v7.2h5V3.1h-5zm1.2 8.8c0 .5.4.9.9.9s.9-.4.9-.9-.4-.9-.9-.9-.9.4-.9.9z"/>`,
    user: `<circle cx="8" cy="5" r="2.8" fill="currentColor"/><path fill="currentColor" d="M2.6 14.2c0-3 2.4-5 5.4-5s5.4 2 5.4 5z"/>`,
    svcs: `<rect x="2.2" y="2.2" width="5.2" height="5.2" rx="1.1" fill="none" stroke="currentColor" stroke-width="1.35"/><rect x="8.6" y="2.2" width="5.2" height="5.2" rx="1.1" fill="none" stroke="currentColor" stroke-width="1.35"/><rect x="2.2" y="8.6" width="5.2" height="5.2" rx="1.1" fill="none" stroke="currentColor" stroke-width="1.35"/>`,
    search: `<circle cx="6.8" cy="6.8" r="4" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="m9.8 9.8 3.4 3.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
    folder: `<path d="M1.8 4.1c0-.6.5-1.1 1.1-1.1h3l1.4 1.6h5.9c.6 0 1.1.5 1.1 1.1v6.2c0 .6-.5 1.1-1.1 1.1H2.9c-.6 0-1.1-.5-1.1-1.1z" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linejoin="round"/>`,
    folderOpen: `<path d="M1.8 12.2V4.1c0-.6.5-1.1 1.1-1.1h3l1.4 1.6h5.4c.6 0 1.1.5 1.1 1.1v1.1" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linejoin="round"/><path d="M3.1 12.9h9.3l1.9-5.4H4.9z" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linejoin="round"/>`,
    gear: `<circle cx="8" cy="8" r="2.4" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M8 1.6v2M8 12.4v2M1.6 8h2M12.4 8h2M3.5 3.5l1.4 1.4M11.1 11.1l1.4 1.4M12.5 3.5l-1.4 1.4M4.9 11.1l-1.4 1.4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`,
    bolt: `<path fill="currentColor" d="M8.9 1.4 3.2 9h3.4l-1.5 5.6L12.8 7H9.4z"/>`,
    bell: `<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="8" r="2.2" fill="currentColor"/>`,
    funnel: `<path d="M2 3.5H14L9.5 9.5V13.5H6.5V9.5L2 3.5Z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`,
  };

  // Favourites are any refs, kept in this browser (an operator's convenience: a page that cannot store still works).
  const FAVS = "pc.favs.v1";
  function loadFavs() { try { const a = JSON.parse(localStorage.getItem(FAVS) || "[]"); return Array.isArray(a) ? a.filter(x => typeof x === "string").slice(0, 200) : []; } catch (e) { return []; } }
  function saveFavs(a) { try { localStorage.setItem(FAVS, JSON.stringify(a)); } catch (e) { /* no storage */ } }

  function mount(root, opts) {
    opts = opts || {};
    // The domain holder's page (§10a): the module with the domain alone — no units of a cluster, no servers, no root
    // subsystem; the domain's card is the page.
    const domainOnly = Array.isArray(opts.sections) && opts.sections.includes("domain") && !opts.sections.includes("units");
    const W = WORDS[opts.lang] || WORDS[(navigator.language || "").startsWith("ru") ? "ru" : "en"];
    const C = { version: VERSION };
    const IC = { logo: "◉", funnel: svgIc(ICONS.funnel), search: svgIc(ICONS.search) };
    const pageIcons = {};
    const ic = name => { const n = String(name || "x").replace(/[^a-zA-Z0-9_-]/g, ""); const d = pageIcons[n] || (ICONS[n] && svgIc(ICONS[n])); return `<span class="ici ici-${n}">${d || "•"}</span>`; };
    // A page's own icons by name: {name: the svg's inner drawing} — the page's code, never data.
    C.addIcons = map => { for (const [k, v] of Object.entries(map || {})) pageIcons[String(k).replace(/[^a-zA-Z0-9_-]/g, "")] = svgIc(String(v)); paintRail(); paintTree(); return C; };
    const listeners = {};
    const shell = { sections: [], tabs: {}, nodes: {}, menus: {} };
    const st = {
      section: domainOnly ? "domain" : "units", sel: null, subs: [], units: {}, servers: {}, policy: {}, session: null, events: [], evfilter: "",
      open: new Set(), draft: null, drain: { draining: "", safe: true, subsystems: {} }, labelDraft: null, acc: null, dom: null, alarms: null, held: null, topo: null, keys: null,
      q: "", stateF: "", favs: loadFavs(), shut: new Set(), tab: {}, full: false, norail: false,
      shared: {},   // [course leads] the groups each subsystem shares with the domain: {sub: {groups, rev}}
    };

    // -- events to the page ---------------------------------------------------------------------------------
    C.on = (evt, fn) => { (listeners[evt] = listeners[evt] || []).push(fn); return C; };
    const emit = (evt, ...a) => (listeners[evt] || []).forEach(fn => { try { fn(...a); } catch (e) { console.error(e); } });

    // -- requests: one Idempotency-Key per submission, retried with it until the answer is final ------------
    // The same request with the same body keeps its key until it has a final answer (2xx, or a 4xx other than
    // 409 "in flight"); a network error, a timeout, a 5xx and 409 "in flight" are retried with it, then handed
    // back as "not lost — retry".
    const keys = new Map();
    let lastRetry = null;   // the write that ran out of retries: a toast saying its failure offers to send it again
    const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : "k-" + Date.now().toString(36) + Math.random().toString(36).slice(2));
    C.retryWaits = [2000, 3000, 5000];
    C.timeoutMs = 20000;
    C.api = async function api(method, path, body) {
      const keyed = method === "POST" || method === "PUT";
      const text = body === undefined ? undefined : JSON.stringify(body);
      const sig = method + " " + path + " " + (text || "");
      const hd = {};
      if (text !== undefined) hd["Content-Type"] = "application/json";
      if (keyed) { if (!keys.has(sig)) keys.set(sig, newKey()); hd["Idempotency-Key"] = keys.get(sig); }
      for (let i = 0; ; i++) {
        let r = null, d = null, lost = "";
        if (!keyed) r = await fetch(path, { method, headers: hd, body: text });
        else {
          const ac = typeof AbortController === "function" ? new AbortController() : null;
          const t = ac ? setTimeout(() => ac.abort(), C.timeoutMs) : 0;
          try { r = await fetch(path, { method, headers: hd, body: text, signal: ac ? ac.signal : undefined }); }
          catch (e) { lost = e && e.name === "AbortError" ? "timeout" : "network"; }
          finally { clearTimeout(t); }
        }
        if (r) { try { d = await r.json(); } catch (e) { d = null; } }
        const said = d && (d.detail || d.error);
        const inFlight = !!r && r.status === 409 && /in.?flight/i.test(String(said || ""));
        if (!keyed || (r && r.status < 500 && !inFlight)) {
          if (keyed) keys.delete(sig);
          if (r.status === 401) showLogin(said || "");
          if (!r.ok) { const e = new Error(said || String(r.status)); e.status = r.status; e.body = d; throw e; }
          return d;
        }
        if (i >= C.retryWaits.length) { const e = new Error((lost || said || String(r && r.status)) + " — not lost: retry sends it again with the same key"); e.retry = { method, path, body }; lastRetry = { ...e.retry, msg: e.message }; throw e; }
        const after = Number(d && d.retry_after);
        await sleep(after > 0 ? Math.min(5000, Math.max(1000, after * 1000)) : C.retryWaits[i]);
      }
    };
    const getJSON = async path => { const r = await fetch(path); if (r.status === 401) showLogin(""); if (!r.ok) throw new Error(path + ": " + r.status); return r.json(); };

    // -- the spec's words, and the interim ones the page passes ----------------------------------------------
    const display = sub => sub.spec.display || {};   // what the spec calls things
    const aboutOf = sub => sub.spec.about || null;   // the spec says what a subsystem's units are about
    const unitWord = (sub, many) => { const d = display(sub); return (many ? d.units : d.unit) || (many ? sub.spec.rows : W.unit); };
    C.display = name => { const s = st.subs.find(x => x.name === name); return s ? display(s) : {}; };
    // [course leads] the spec as /spec gave it, a copy — for the page's own reading of it (its places' table, spec.places)
    C.spec = name => { const s = st.subs.find(x => x.name === name); return s ? JSON.parse(JSON.stringify(s.spec)) : null; };
    const kindWord = e => { const s = st.subs.find(x => x.name === e.subsystem); const k = s && display(s).kinds; return (k && k[e.kind]) || W.kinds[e.kind] || e.kind; };
    // What a platform event says beyond its kind, from its fields; a subsystem's events say it in their note.
    const dur = sec => { sec = Math.round(+sec || 0); const m = Math.floor(sec / 60), r = sec % 60; return m ? `${m} ${W.n.min}${r ? " " + r + " " + W.n.s : ""}` : `${r} ${W.n.s}`; };
    const eventNote = e => {
      const n = W.n, k = e.kind || "", at = (who, srv) => `${who ?? "?"}${srv ? " " + n.on + " " + srv : ""}`, j = a => a.filter(Boolean).join(" · ");
      if (k === "worker.presence_unknown" || k === "worker.presence_unknown_moved")
        return j([at(e.worker, e.server), e.silent_s != null ? n.silent + " " + dur(e.silent_s) : "", e.why, e.units != null ? n.unitsN + ": " + e.units : "",
          k === "worker.presence_unknown" ? n.noTwoWriters : e.after_s != null ? n.movedAfter + " " + dur(e.after_s) : ""]);
      if (k === "worker.slot_ahead")
        return j([e.worker ?? "?", e.holder ? n.holds + " " + e.holder : "", e.until ? n.leaseUntil + " " + fmt(e.until) : "",
          e.limit_s != null ? n.pastLimit + " " + dur(e.limit_s) : "", e.units != null ? n.unitsN + ": " + e.units : ""]);
      if (k === "session.debug_open") return e.person ? n.asPerson + " " + e.person : "";
      if (k === "worker.name_taken") return j([`${e.worker ?? "?"}: ${n.nameHeld} ${e.holder ?? "?"}${e.holder_box ? " (" + e.holder_box + ")" : ""}`, n.waits + (e.box ? " (" + e.box + ")" : "")]);
      if (k === "worker.name_back") return `${e.worker ?? ""} ${n.namedAgain}${e.nameless_s != null ? " " + n.after + " " + dur(e.nameless_s) + " " + n.nameless : ""}`.trim();
      if (k === "worker.name_conflict")
        return `${e.worker ?? "?"}: ${n.holds} ${e.holder ?? "?"}${e.holder_box ? " (" + e.holder_box + ")" : ""}, ${n.refused} ${e.contender ?? "?"}${e.contender_hostname ? " " + n.on + " " + e.contender_hostname : ""}${e.contender_server ? " (" + e.contender_server + ")" : ""}`;
      if (/^server\.decommission/.test(k) && e.server != null)
        return j([n.server + " " + e.server, e.user || e.by, e.refusal || e.why, e.lost ? n.lost + ": " + e.lost : "", e.units != null && k === "server.decommissioned" ? n.unitsN + ": " + e.units : ""]);
      if (/^worker\.(hung|hung_moved|released_by_controller)$/.test(k) && e.worker != null)
        return j([at(e.worker, e.server), e.silent_s != null ? n.silent + " " + dur(e.silent_s) : "", e.units != null ? n.unitsN + ": " + e.units : "", e.why]);
      for (const fn of shell.eventNotes || []) { try { const t = fn(e); if (t) return t; } catch (x) { /* the next */ } }   // the page's words for its own events
      return e.note || e.detail || "";
    };
    C.kindWord = kindWord;
    // A page's words for its subsystems' events (what the spec's kinds cannot say: amounts, causes): fn(e) → text.
    C.addEventNote = fn => { (shell.eventNotes = shell.eventNotes || []).push(fn); return C; };
    C.eventNote = eventNote;

    // -- rights: the session's grants, when it names them -----------------------------------------------------
    // may(action, ref): action is view | edit | admin. Without grants in /session the answer is yes — the
    // server checks every request anyway; this only does not offer a person what would be refused.
    const RANK = { view: 1, edit: 2, admin: 3 };
    C.may = (action, ref) => {
      const g = st.session && st.session.grants;
      if (!Array.isArray(g)) return true;
      const need = RANK[action] || 3;
      const unit = String(ref || "").startsWith("unit:") ? String(ref).slice(5) : null;
      return g.some(x => (RANK[x.cap] || 0) >= need && (x.scope === "*" || (unit && x.scope === "unit:" + unit)));
    };

    // -- the page's calls into the library ------------------------------------------------------------------
    C.addSection = s => { shell.sections.push(s); paintRail(); return C; };
    C.addTab = (kind, t) => { (shell.tabs[kind] = shell.tabs[kind] || []).push(t); return C; };
    C.addTreeNodes = (kind, fn) => { (shell.nodes[kind] = shell.nodes[kind] || []).push(fn); return C; };
    // The page's own editor of ONE field inside the module's form: render(host, ref, obj, value, set). The form still
    // sends it — set(v) writes the value the form will read; the field is still the spec's.
    C.addFieldEditor = (kind, field, render) => { ((shell.editors = shell.editors || {})[kind] = (shell.editors[kind] || {}))[field] = render; return C; };
    // The card of the page's own objects (refs with its prefix: addTreeNodes made them): render(host, ref), in the
    // inspector where the module's cards are, with the same star and full screen.
    C.addCard = (prefix, render) => { (shell.cards = shell.cards || {})[prefix] = render; return C; };
    C.addMenu = (kind, fn) => { (shell.menus[kind] = shell.menus[kind] || []).push(fn); return C; };
    // The page's decoration of a node and of its card's title: an icon (a class, pc-ic-<icon>, drawn by the page's
    // CSS), a badge and a title — text, escaped here. The module has no logic of it.
    C.addDecor = (kind, fn) => { (shell.decor = shell.decor || {})[kind] = (shell.decor[kind] || []).concat(fn); paintTree(); return C; };
    function decor(ref) {
      const kind = String(ref).split(":")[0], fns = (shell.decor || {})[kind] || [];
      let out = "";
      for (const fn of fns) {
        let d; try { d = fn(ref, objectOf(ref)) || {}; } catch (e) { d = {}; }
        const icon = String(d.icon || "").replace(/[^a-z0-9_-]/gi, "");
        if (icon) out += d.title ? ic(icon).replace("<span ", `<span title="${h(d.title)}" `) : ic(icon);
        if (d.badge) out += `<span class="tag pc-badge"${d.title && !icon ? ` title="${h(d.title)}"` : ""}>${h(d.badge)}</span>`;
      }
      return out;
    }
    C.selected = () => st.sel;
    C.isFav = ref => st.favs.includes(ref);
    C.toggleFav = ref => { st.favs = C.isFav(ref) ? st.favs.filter(x => x !== ref) : [ref, ...st.favs]; saveFavs(st.favs); paintTree(); paintMain(); return C; };
    C.where = async ref => {
      const u = parseUnit(ref); if (!u) return null;
      try { const w = await getJSON(u.sub.base + "/where/" + encodeURIComponent(u.id)); return { worker: w.worker, server: w.server, door: w.door || null, reason: w.reason }; }
      catch (e) { return null; }
    };
    C.select = ref => { st.sel = ref; st.draft = null; paintTree(); paintMain(); const m = $(".pc-main"); if (m) m.scrollTop = 0; emit("select", ref, objectOf(ref)); return C; };   // another object starts at the top
    C.refresh = () => load();

    // -- refs ------------------------------------------------------------------------------------------------
    const unitRef = (sub, id) => "unit:" + sub.name + "/" + id;
    function parseUnit(ref) {
      const m = /^unit:([^/]+)\/(.+)$/.exec(String(ref || "")); if (!m) return null;
      const sub = st.subs.find(s => s.name === m[1]); if (!sub) return null;
      return { sub, id: m[2], row: (st.units[sub.name] || []).find(u => String(u.id) === m[2]) || null };
    }
    function objectOf(ref) {
      const u = parseUnit(ref); if (u) return u.row;
      if (String(ref).startsWith("server:")) return st.servers[String(ref).slice(7)] || null;
      if (String(ref).startsWith("worker:")) { const n = String(ref).slice(7); for (const s2 of Object.values(st.servers)) for (const w2 of s2.workers || []) if (w2.worker === n) return w2; return null; }
      if (String(ref).startsWith("member:")) return ((st.dom && st.dom.members) || []).find(m => m.name === String(ref).slice(7)) || null;
      if (ref === "domain") return st.dom;
      return null;
    }

    // -- layout ----------------------------------------------------------------------------------------------
    // The console's look is the product console's, one for every page (the course's КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md,
    // §9): a header with the counters and the person's menu, the rail of sections, the panel with its layout and
    // filter, a border that drags, the inspector, a footer that saves the selected object. Styles are
    // /platform/console.css; the pc-* classes are this file's handles, not the look.
    root.innerHTML = `<div class="app pc"><header>
        <div class="logo"><b aria-hidden="true">${IC.logo}</b></div><span style="flex:1"></span>
        <div class="hr-tools">
          <div class="hload pc-hload"><span class="hmet"><span class="hlab pc-hunits-l">—</span><b class="pc-hunits">—</b></span><span class="hmet"><span class="hlab">${h(W.workersCap)}</span><b class="pc-hworkers">—</b></span><span class="hsrv pc-hsrv"></span></div>
          <div class="umenu pc-umenu"><button type="button" class="ubtn pc-ubtn" aria-expanded="false"><span class="uav">◐</span><span class="uname pc-uname">—</span><span class="uchev">▾</span></button>
            <span class="bd off pc-debug" hidden>${h(W.debugBadge)}</span>
            <div class="upop pc-upop"><div class="uhead"><span class="uav">◐</span><b class="pc-uinst">—</b></div>
              <label>${h(W.theme)}<select class="pc-theme"><option value="dark">${h(W.dark)}</option><option value="light">${h(W.light)}</option></select></label>
              <label>${h(W.pollW)}<select class="pc-poll"><option value="5">${h(W.pollEvery.replace("{n}", 5))}</option><option value="15">${h(W.pollEvery.replace("{n}", 15))}</option><option value="0">${h(W.manual)}</option></select></label>
              <button type="button" class="btn s w pc-reload" style="margin-top:2px">${h(W.refreshNow)}</button>
              <button type="button" class="btn s w pc-logout" style="display:none">${h(W.logout)}</button></div></div>
        </div></header>
      <div class="ws pc-ws"><nav class="rail pc-rail" role="tablist"></nav><aside class="pc-side"></aside><div class="rsz pc-rsz"></div><main><div class="hd pc-hd"></div><div class="sc pc-main"></div></main></div>
      <footer><span class="hint pc-hint">${h(W.hint)}</span><span style="flex:1"></span><button type="button" class="btn s pc-discard" disabled>${h(W.discard)}</button><button type="button" class="btn pri s pc-save" disabled>${h(W.save)}</button></footer></div>
      <div class="confirm pc-login" hidden><div class="cbox"><div class="chead pc-login-t">${h(W.login)}</div><div class="cbody">
        <form class="pc-login-f"><div class="g"><div><label>${h(W.user)}</label><input name="user" autocomplete="username"></div><div><label>${h(W.password)}</label><input name="password" type="password" autocomplete="current-password"></div></div>
          <p class="sub pc-login-w" style="margin-top:8px"></p><button type="submit" hidden></button></form>
        <form class="pc-glass-f" hidden><p class="sub">${h(W.glassIntro)}</p><div class="g"><div><label>${h(W.glassWho)}</label><input name="who" autocomplete="off"></div><div><label>${h(W.glassWhy)}</label><input name="why" autocomplete="off"></div><div><label>${h(W.glassPass)}</label><input name="password" type="password" autocomplete="off"></div></div><button type="submit" hidden></button></form>
        <div class="cwarn pc-login-e"></div></div>
        <div class="cfoot"><button type="button" class="btn pc-glass-go">${h(W.glassGo)}</button><span style="flex:1"></span><button type="button" class="btn pri pc-login-ok">${h(W.loginBtn)}</button></div></div></div>
      <div class="confirm pc-dialog" hidden><form class="cbox pc-dialog-f"><div class="chead"></div><div class="cbody pc-dialog-b"></div><div class="cfoot"><button type="button" class="btn pc-dialog-no"></button><button type="submit" class="btn pri pc-dialog-ok"></button></div></form></div>
      <div class="tctx pc-menu" role="menu"></div>
      <div class="pc-toast" hidden></div>`;
    const $ = s => root.querySelector(s);
    const show = (el, on) => { el.hidden = !on; el.classList.toggle("open", !!on); };
    // the theme and the refresh rate are the person's, kept in this browser
    const keep = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return v; };
    const setTheme = v => { document.documentElement.dataset.theme = v === "light" ? "light" : "dark"; keep("pc.theme", document.documentElement.dataset.theme); $(".pc-theme").value = document.documentElement.dataset.theme; };
    setTheme(keep("pc.theme") || "dark");
    $(".pc-theme").onchange = e => setTheme(e.target.value);
    let pollTimer = null;
    const setPoll = s => { s = Number(s); clearInterval(pollTimer); pollTimer = s > 0 ? setInterval(load, s * 1000) : null; keep("pc.poll", String(s)); $(".pc-poll").value = [5, 15, 0].includes(s) ? String(s) : "5"; };
    $(".pc-poll").onchange = e => setPoll(e.target.value);
    $(".pc-reload").onclick = () => load();
    const userMenu = on => { show($(".pc-upop"), on); $(".pc-upop").hidden = false; $(".pc-ubtn").classList.toggle("on", on); $(".pc-ubtn").setAttribute("aria-expanded", on ? "true" : "false"); };
    $(".pc-ubtn").onclick = e => { e.stopPropagation(); userMenu(!$(".pc-upop").classList.contains("open")); };
    document.addEventListener("mousedown", e => { if (!$(".pc-umenu").contains(e.target)) userMenu(false); });
    $(".pc-logout").onclick = () => { userMenu(false); C.logout(); };
    // the panel's width: the border drags it, the browser keeps it
    let asideW = Number(keep("pc.aside")) || 360;
    $(".pc-ws").style.setProperty("--aw", asideW + "px");
    $(".pc-rsz").onmousedown = e => {
      e.preventDefault(); const x0 = e.clientX, w0 = asideW; $(".pc-rsz").classList.add("on");
      const mv = ev => { asideW = Math.max(240, Math.min(720, w0 + ev.clientX - x0)); $(".pc-ws").style.setProperty("--aw", asideW + "px"); };
      const up = () => { document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up); $(".pc-rsz").classList.remove("on"); keep("pc.aside", String(asideW)); };
      document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up);
    };
    let glassMode = false;
    const glassToggle = on => { glassMode = on; $(".pc-login-f").hidden = on; $(".pc-glass-f").hidden = !on; $(".pc-glass-go").textContent = on ? W.normal : W.glassGo; $(".pc-login-t").textContent = on ? W.glassGo : W.login; $(".pc-login-e").textContent = ""; };
    $(".pc-glass-go").onclick = () => glassToggle(!glassMode);
    $(".pc-login-ok").onclick = () => (glassMode ? $(".pc-glass-f") : $(".pc-login-f")).requestSubmit();
    // Break-glass: a cluster's own password, for when the domain's holder is unreachable — every action an alarm.
    $(".pc-glass-f").onsubmit = async e => {
      e.preventDefault(); const f = e.target;
      try {
        const r = await fetch("/session/break-glass", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ who: f.elements.who.value.trim(), why: f.elements.why.value.trim(), password: f.elements.password.value }) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.detail || d.error || String(r.status));
        f.elements.password.value = ""; show($(".pc-login"), false); await loadSession(); await load(); C.toast(W.glassOn);
      } catch (err) { $(".pc-login-e").textContent = err.message; }
    };
    C.logout = async () => { try { await fetch("/session", { method: "DELETE" }); } catch (e) { /* gone anyway */ } st.session = null; await loadSession(); if (!st.session || !st.session.open) showLogin(""); paintHeader(); };
    // Full screen: the inspector over everything; the same button or Esc brings it back.
    C.fullScreen = on => { st.full = on === undefined ? !st.full : !!on; $(".pc").classList.toggle("pc-full", st.full); const b = $(".pc-hd .pc-fullbtn"); if (b) b.textContent = st.full ? "⤡" : "⤢"; return C; };
    document.addEventListener("keydown", e => { if (e.key === "Escape" && st.full) C.fullScreen(false); });
    // A small form: fields [{name, label, type, value, options, help}] → the values, or null when cancelled.
    C.dialog = (title, fields, okLabel) => new Promise(resolve => {
      const box = $(".pc-dialog"), f = $(".pc-dialog-f");
      f.querySelector(".chead").textContent = title;
      f.querySelector(".pc-dialog-b").innerHTML = `<div class="g">${fields.map(x => `<div><label>${h(x.label)}</label>${x.options
        ? `<select name="${h(x.name)}">${x.options.map(o => `<option value="${h(o[0])}">${h(o[1])}</option>`).join("")}</select>`
        : `<input name="${h(x.name)}" type="${x.type === "password" ? "password" : "text"}" value="${h(x.value || "")}" autocomplete="${x.type === "password" ? "new-password" : "off"}">`}${x.help ? `<p class="sub">${h(x.help)}</p>` : ""}</div>`).join("")}</div>`;
      f.querySelector(".pc-dialog-ok").textContent = okLabel || W.ok; f.querySelector(".pc-dialog-no").textContent = W.cancel;
      show(box, true);
      const done = v => { show(box, false); f.onsubmit = null; resolve(v); };
      f.onsubmit = e => { e.preventDefault(); const v = {}; fields.forEach(x => { v[x.name] = f.elements[x.name].value; }); done(v); };
      f.querySelector(".pc-dialog-no").onclick = () => done(null);
    });
    C.confirm = (q, more) => window.confirm(q + (more ? "\n\n" + more : ""));
    C.toast = msg => {
      const t = $(".pc-toast"); t.textContent = msg; t.hidden = false; clearTimeout(t._t);
      // the same request, the same body — so the same key: what the server already did is answered, not done twice
      const rt = lastRetry && String(msg).includes(lastRetry.msg) ? lastRetry : null;
      if (rt) {
        lastRetry = null;
        const b = document.createElement("button"); b.type = "button"; b.className = "btn s pc-retry"; b.textContent = W.retry;
        b.onclick = async () => { t.hidden = true; C.toast(W.retrying); try { await C.api(rt.method, rt.path, rt.body); await load(); paintMain(); C.toast(W.done); } catch (e) { C.toast(W.refused + ": " + e.message); } };
        t.appendChild(b);
      }
      t._t = setTimeout(() => { t.hidden = true; }, rt ? 20000 : 3000);
    };

    // -- the header: the counters, from the gauges the spec names; whose session ---------------------------------
    const cap = s => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);
    st.gauges = {};
    async function loadGauges() {
      const r0 = st.subs[0]; if (!r0 || !(r0.spec.running_gauge || r0.spec.workers_gauge)) { st.gauges = {}; return; }
      try {
        const r = await fetch("/metrics"); if (!r.ok) throw new Error(String(r.status));
        const text = await r.text(), sum = name => { if (!name) return null; let n = null; for (const l of text.split("\n")) { const m = /^([a-zA-Z_:][\w:]*)(\{[^}]*\})?\s+(\S+)/.exec(l); if (m && m[1] === name) n = (n || 0) + Number(m[3]); } return n; };
        st.gauges = { units: sum(r0.spec.running_gauge), workers: sum(r0.spec.workers_gauge) };
      } catch (e) { st.gauges = {}; }
    }
    function paintHeader() {
      if (domainOnly) return paintHolderHeader();
      const r0 = st.subs[0], g = st.gauges || {};
      $(".pc-hunits-l").textContent = cap(r0 ? unitWord(r0, true) : W.units);
      $(".pc-hunits").textContent = g.units == null ? "—" : g.units;
      $(".pc-hworkers").textContent = g.workers == null ? "—" : g.workers;
      const names = Object.keys(st.servers), live = names.filter(n => st.servers[n].resource === "live").length;
      $(".pc-hsrv").textContent = st.loadErr ? W.noLink : W.resOnline.replace("{a}", live).replace("{b}", names.length);
      $(".pc-hload").classList.toggle("stale", !!st.loadErr);
      $(".pc-uinst").textContent = r0 ? W.subsystemW + " " + r0.name : "—";
      const s = st.session || {};
      $(".pc-uname").textContent = s.user ? s.user + (s.glass ? " · " + W.glass : "") : s.open ? W.open : "—";
      paintDebug(s);
    }

    // A door that let the person in without a password (ADR-0050: W2C_DEBUG_PERSON, loopback, a stand only) is said in
    // the header for as long as it is so; there is nothing to sign out of.
    function paintDebug(s) {
      const b = $(".pc-debug"); b.hidden = !s.debug; b.title = W.debugTip;
      $(".pc-logout").style.display = s.user && !s.debug ? "block" : "none";
    }
    // at the holder: the members and how many publish, the holder's name
    function paintHolderHeader() {
      const ms = (st.dom && st.dom.members) || [];
      $(".pc-hunits-l").textContent = cap(W.clusters); $(".pc-hunits").textContent = st.dom ? ms.length : "—"; $(".pc-hworkers").textContent = "—";
      $(".pc-hsrv").textContent = st.loadErr && !st.dom ? W.noLink : st.dom ? ms.filter(m => m.holder || m.state === "ok").length + "/" + ms.length + " " + W.publishes : "";
      $(".pc-hload").classList.toggle("stale", !st.dom);
      $(".pc-uinst").textContent = cap(W.domainWord) + (st.dom && st.dom.holder ? " · " + st.dom.holder : "");
      const s = st.session || {};
      $(".pc-uname").textContent = s.user ? s.user : s.open ? W.open : "—";
      paintDebug(s);
    }

    // -- the rail -------------------------------------------------------------------------------------------------
    // The units, the servers and the domain are one section — two layouts of one panel (by the spec's groups, by
    // servers); the rights; the journal at the bottom. A page's own sections stand where they say (after).
    const SECTIONS = { units: W.hwSection, domain: W.domainWord, access: W.access, journal: W.journal };
    const LAYOUT_OF = { units: "units", servers: "units", domain: "units" };   // what the rail shows as on
    function sectionList() {
      const own = { units: () => (st.subs[0] && display(st.subs[0]).section) || W.hwSection };
      let list = (opts.sections || ["units", "access", "journal"]).filter(s => SECTIONS[s]).map(s => ({ id: s, label: own[s] ? own[s]() : SECTIONS[s], icon: s === "domain" ? "domain" : "sec_" + s, bottom: s === "journal" }));
      for (const s of shell.sections) {
        const at = s.after ? list.findIndex(x => x.id === s.after) : -1;
        const it = { id: s.id, label: s.label, icon: s.icon, off: s.off };
        if (at >= 0) list.splice(at + 1, 0, it); else list.splice(list.findIndex(x => x.bottom) < 0 ? list.length : list.findIndex(x => x.bottom), 0, it);
      }
      return list;
    }
    const railOn = () => sectionList().some(s => s.id === st.section) ? st.section : LAYOUT_OF[st.section] || st.section;
    function goSection(id) {
      if (id === "units") { st.section = keep("pc.layout") === "servers" ? "servers" : "units"; } else st.section = id;
      st.sel = null; paintRail(); paintAside(); paintMain(); if (st.section === "access") loadAccess();
    }
    function paintRail() {
      const on = railOn();
      $(".pc-rail").innerHTML = sectionList().map(s => `<button type="button" class="asw${on === s.id ? " on" : ""}${s.bottom ? " asw-bottom" : ""}${s.off ? " is-off" : ""}" data-s="${h(s.id)}" role="tab" aria-selected="${on === s.id}" title="${h(s.off ? s.label + ": " + s.off : s.label)}">${ic(s.icon)}<span class="asw-lb">${h(cap(s.label))}</span></button>`).join("");
      $(".pc-rail").querySelectorAll("button[data-s]").forEach(b => { b.onclick = () => goSection(b.dataset.s); });
      paintHeader();
    }

    // -- the panel: its head (the layout, the filter) over the tree, the favourites under it ----------------------
    let layoutPop = false;
    function layouts() {
      const r0 = st.subs[0], tr = r0 ? display(r0).tree || {} : {};
      return [{ id: "units", label: tr.group_title || W.byGroups, hint: tr.group_hint || W.byGroupsHint, icon: "folder", n: () => groupCount() },
        { id: "servers", label: W.byServers, hint: W.byServersHint, icon: "server", n: () => Object.keys(st.servers).length }];
    }
    function groupCount() {
      const r0 = st.subs[0]; if (!r0) return 0; const g = (display(r0).tree || {}).group_by; if (!g) return (st.units[r0.name] || []).length;
      const sep = (display(r0).tree || {}).nested_by, seen = new Set();
      for (const v of [...(st.units[r0.name] || []).flatMap(u => Array.isArray(u[g]) ? u[g] : []), ...extraGroups(r0)]) { const p = sep ? String(v).split(sep).filter(Boolean) : [String(v)]; for (let i = 1; i <= p.length; i++) seen.add(p.slice(0, i).join(sep || "")); }
      return seen.size;
    }
    function paintAside() {
      const el = $(".pc-side"), on = railOn();
      const tree = on === "units" || on === "access" || on === "domain";
      const ws = $(".pc-ws"); ws.classList.toggle("one", !tree);
      if (!tree) { el.innerHTML = ""; return; }
      const cur = layouts().find(l => l.id === (st.section === "servers" || st.section === "domain" ? "servers" : "units"));
      el.innerHTML = (on === "units" ? `<div class="ph"><button type="button" class="ph-sel pc-layout${layoutPop ? " on" : ""}" aria-haspopup="listbox" aria-expanded="${layoutPop}" title="${h(cur.hint)}">${ic(cur.icon)}<span class="ph-nm">${h(cur.label)}</span><span class="ph-cnt">${cur.n()}</span><span class="ph-chev" aria-hidden="true">▾</span></button>
          <div class="sq ph-sq"><span class="sq-lead" aria-hidden="true">${IC.funnel}</span><input class="pc-q" placeholder="${h((st.subs[0] && (display(st.subs[0]).tree || {}).filter) || W.filterPh)}" value="${h(st.q)}" autocomplete="off"><button type="button" class="sq-clear pc-qx${st.q ? "" : " hide"}">✕</button></div>
          ${layoutPop ? `<div class="ph-pop sl" role="listbox">${layouts().map(l => `<button type="button" class="ph-mi${l.id === cur.id ? " on" : ""}" role="option" data-layout="${l.id}" title="${h(l.hint)}">${ic(l.icon)}<span class="lbl">${h(l.label)}</span><span class="cnt">${l.n()}</span>${l.id === cur.id ? `<span class="tick" aria-hidden="true">✓</span>` : ""}</button>`).join("")}</div>` : ""}</div>`
        : "") + `<div class="gear-body">${on === "units" ? "" : `<div class="gear-tree-head"><div class="sq-wrap"><div class="sq"><span class="sq-lead" aria-hidden="true">${IC.search}</span><input class="pc-q" placeholder="${h(W.byName)}" value="${h(st.q)}" autocomplete="off"></div></div></div>`}<div class="tree pc-tree"></div></div><div class="fav-wrap pc-favs"></div>`;
      const q = el.querySelector(".pc-q");
      q.oninput = e => { st.q = e.target.value; const x = el.querySelector(".pc-qx"); if (x) x.classList.toggle("hide", !st.q); paintTree(); };
      const x = el.querySelector(".pc-qx"); if (x) x.onclick = () => { st.q = ""; paintAside(); };
      const ls = el.querySelector(".pc-layout"); if (ls) ls.onclick = e => { e.stopPropagation(); layoutPop = !layoutPop; paintAside(); };
      el.querySelectorAll("[data-layout]").forEach(b => { b.onclick = () => { layoutPop = false; keep("pc.layout", b.dataset.layout); if (b.dataset.layout !== (st.section === "units" ? "units" : "servers")) { st.section = b.dataset.layout; st.sel = null; paintMain(); } paintAside(); }; });
      paintTree();
    }
    document.addEventListener("mousedown", e => { if (layoutPop && !(e.target.closest && e.target.closest(".ph"))) { layoutPop = false; paintAside(); } });

    // -- the tree ----------------------------------------------------------------------------------------------
    // Units of every subsystem the page shows; a subsystem whose spec says `about: {sub, field}` is nested under
    // the units of its parent, by that field. `display.tree.group_by` groups a subsystem's units by a list field.
    function childrenOf(sub, row) {
      const out = [];
      for (const s of st.subs) {
        const a = aboutOf(s); if (!a || a.sub !== sub.name) continue;
        for (const u of st.units[s.name] || []) if (String(u[a.field]) === String(row.id)) out.push({ sub: s, row: u });
      }
      return out;
    }
    // The tree's search: the label, the id and every field's text; the state filter: running / with problems / unplaced.
    function unitMatches(sub, u) {
      const q = st.q.trim().toLowerCase();
      if (q && ![label(sub, u), u.id, ...Object.values(u).map(v => Array.isArray(v) ? v.join(" ") : v)].some(v => String(v ?? "").toLowerCase().includes(q))) return false;
      if (st.stateF === "running") return u.phase === "running";
      if (st.stateF === "unplaced") return !u.worker;
      if (st.stateF === "problems") return u.phase !== "running" || u.worker_state === "stale";
      return true;
    }
    // A column's value, formatted by the field's type in the spec (a secret as the mask, a list joined); a status
    // key (phase, worker, server, revision, observed_revision) as it is. No logic: display is a dictionary.
    function colValue(sub, u, field) {
      const f = sub.spec.fields.find(x => x.name === field), v = u[field];
      if (f && isSecret(f.name)) return v ? MASK : "";
      if (Array.isArray(v)) return v.join(", ");
      if (field === "worker" && !v) return W.unplaced;
      return v ?? "";
    }
    const filtering = () => !!(st.q.trim() || st.stateF);
    const label = (sub, u) => u.name || (sub.spec.id === "numeric" ? unitWord(sub, false) + " " + u.id : String(u.id));
    function favLabel(ref) {
      const u = parseUnit(ref); if (u) return u.row ? label(u.sub, u.row) : ref;
      return ref.replace(/^[a-z]+:/, "");
    }
    // One row of the tree, as the product console draws it: the indent, the twisty, the icon, the name, then on
    // the right its tags, its count, its state dot, the star and «⋯».
    function nrow(o) {
      const on = st.sel === o.ref, fav = C.isFav(o.ref);
      return `<div class="n${on ? " on" : ""}${o.off ? " off" : ""}${o.cls ? " " + o.cls : ""}" style="padding-left:${8 + (o.depth || 0) * 14}px" data-ref="${h(o.ref)}"${o.title ? ` title="${h(o.title)}"` : ""}>`
        + (o.has ? `<span class="tw" data-tw="${h(o.ref)}"${o.defOpen ? ' data-shut="1"' : ""}>${o.open ? "▾" : "▸"}</span>` : `<span class="tw"></span>`)
        + (o.iconHtml || (o.icon ? ic(o.icon) : "")) + `<span class="nm">${h(o.name)}</span>`
        + `<span class="n-meta">${o.tags ? `<span class="n-tags">${o.tags}</span>` : ""}${o.cnt != null ? `<span class="n-tail n-tail-cnt"><span class="cnt">${h(o.cnt)}</span></span>` : ""}${o.dot ? `<span class="n-tail"><span class="dot" title="${h(o.dot[1])}" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${o.dot[0]}"></span></span>` : ""}`
        + `<button type="button" class="n-fav${fav ? " on" : ""}" tabindex="-1" aria-pressed="${fav}" data-star="${h(o.ref)}" title="${h(fav ? W.unstar : W.star)}">${fav ? "★" : "☆"}</button><button type="button" class="n-menu" tabindex="-1" aria-haspopup="menu" data-menu="${h(o.ref)}" title="${h(W.actions)}">⋯</button></span></div>`;
    }
    const tagHtml = (t, title) => `<span class="tag"${title ? ` title="${h(title)}"` : ""}>${h(t)}</span>`;
    // The page's decoration, split as the row wants it: the icon before the name, the badges among the tags.
    function decorOf(ref) {
      const kind = String(ref).split(":")[0], fns = (shell.decor || {})[kind] || [];
      let icon = "", tags = "", title = "";
      for (const fn of fns) {
        let d; try { d = fn(ref, objectOf(ref)) || {}; } catch (e) { d = {}; }
        if (d.icon && !icon) { icon = d.icon; title = d.title || ""; }
        if (d.badge) tags += tagHtml(d.badge, d.title).replace('class="tag"', 'class="tag pc-badge"');
      }
      return { iconHtml: icon ? (title ? ic(icon).replace("<span ", `<span title="${h(title)}" `) : ic(icon)) : "", tags };
    }
    // The page's own rows (addTreeNodes): {ref, label, icon, badge, tags: [text | {text, title}], dot: [colour, word],
    // count, off, title, kids, open (shown open until closed)}.
    function extraRows(list, depth) {
      return list.map(x => {
        const kids = Array.isArray(x.kids) ? x.kids : [];
        const open = kids.length > 0 && ((x.open ? !st.shut.has(x.ref) : st.open.has(x.ref)) || filtering());
        if (filtering() && !String(x.label).toLowerCase().includes(st.q.trim().toLowerCase()) && !kids.length) return "";
        const tags = (x.badge ? tagHtml(x.badge) : "") + (x.tags || []).map(t => typeof t === "object" ? tagHtml(t.text, t.title) : tagHtml(t)).join("");
        return nrow({ ref: x.ref, depth, icon: x.icon, name: x.label, tags, dot: x.dot, cnt: x.count, off: x.off, title: x.title, has: kids.length > 0, open, defOpen: !!x.open }) + (open ? extraRows(kids, depth + 1) : "");
      }).join("");
    }
    const nodesOf = (kind, ...a) => (shell.nodes[kind] || []).flatMap(fn => { try { return fn(...a) || []; } catch (e) { return []; } });
    // A unit's state as a dot: running, waiting for a place, switched off, or wrong.
    function unitDot(u) { const [w, , c] = stateOf(u); return [c, w]; }
    function unitRow(sub, u, depth) {
      const ref = unitRef(sub, u.id), tr = display(sub).tree || {};
      const kids = tr.children === false ? [] : childrenOf(sub, u).filter(k => !filtering() || unitMatches(k.sub, k.row));
      if (filtering() && !unitMatches(sub, u) && !kids.length) return "";
      const extra = nodesOf("unit", ref, u);
      const has = kids.length > 0 || extra.length > 0, open = st.open.has(ref) || (filtering() && kids.length > 0);
      const d = decorOf(ref), cols = Array.isArray(tr.columns) ? tr.columns : [];
      const tags = d.tags + cols.map(c => { const v = colValue(sub, u, c.field); return v === "" ? "" : tagHtml(v, c.title || c.field); }).join("");
      return nrow({ ref, depth, iconHtml: d.iconHtml, name: label(sub, u), tags, dot: unitDot(u), has, open, off: u.enabled === false || u.worker_state === "stale" })
        + (has && open ? kids.map(k => unitRow(k.sub, k.row, depth + 1)).join("") + extraRows(extra, depth + 1) : "");
    }
    // Groups by a list field (display.tree.group_by), nested by a separator in the value (display.tree.nested_by):
    // "Office/Entrance" is the group Entrance under Office. A unit stands under each group it names; a group shows
    // the groups below it, then its own units; its count is every unit under it. Its ref is the whole path.
    // [course leads] …and groups with no unit in them yet: those the domain offers for a group_by field the spec shares with it
    // (domain.shared), read by the module at /domain/shared/<sub> — no page passes them any more (addGroupValues is gone)
    // a group made here and carried by no unit yet: kept in this browser, gone when a unit carries it (as the product
    // console's new folder was)
    const LG = "pc.groups";
    const localGroups = () => { try { const o = JSON.parse(localStorage.getItem(LG) || "{}"); return o && typeof o === "object" ? o : {}; } catch (e) { return {}; } };
    const saveLocalGroups = o => { try { localStorage.setItem(LG, JSON.stringify(o)); } catch (e) { /* no storage */ } };
    const localOf = sub => { const g = (display(sub).tree || {}).group_by; return g ? (localGroups()[sub.name + "/" + g] || []) : []; };
    function pruneLocalGroups() {
      const o = localGroups(); let changed = false;
      for (const sub of st.subs) {
        const tr = display(sub).tree || {}, g = tr.group_by, sep = tr.nested_by || "", key = sub.name + "/" + g; if (!g || !o[key]) continue;
        const carried = (st.units[sub.name] || []).flatMap(u => Array.isArray(u[g]) ? u[g] : []).map(String);
        const keep = o[key].filter(p => !carried.some(v => v === p || (sep && v.startsWith(p + sep))));
        if (keep.length !== o[key].length) { o[key] = keep; changed = true; }
      }
      if (changed) saveLocalGroups(o);
    }
    const extraGroups = sub => [...((st.shared[sub.name] || {}).groups || []), ...localOf(sub)].map(String).filter(Boolean);
    // a new group under parent ("" — at the top): its name asked, its path checked; it is selected, and it says how it lives
    async function newGroup(sub, parent) {
      const tr = display(sub).tree || {}, g = tr.group_by, sep = tr.nested_by || ""; if (!g) return;
      const v = await C.dialog(parent ? W.newGroupIn.replace("{p}", parent) : W.newGroupTop, [{ name: "name", label: W.name }], W.create);
      const name = v && String(v.name).trim().split(sep || "\u0000").map(x => x.trim()).filter(Boolean).join(sep); if (!name) { if (v) C.toast(W.groupNameEmpty); return; }
      const path = parent ? parent + sep + name : name;
      const all = new Set([...(st.units[sub.name] || []).flatMap(u => Array.isArray(u[g]) ? u[g] : []).map(String), ...extraGroups(sub)]);
      if ([...all].some(x => x === path || (sep && x.startsWith(path + sep)))) { C.toast(W.groupExists); C.select("group:" + sub.name + "/" + g + "/" + path); return; }
      const o = localGroups(), key = sub.name + "/" + g; o[key] = [...new Set([...(o[key] || []), path])]; saveLocalGroups(o);
      if (parent) st.open.add("group:" + sub.name + "/" + g + "/" + parent);
      C.select("group:" + sub.name + "/" + g + "/" + path);
      C.toast(tr.new_group_note || W.newGroupNoteT.replace("{u}", unitWord(sub, false)));
    }
    const sharedHint = (sub, value) => { const s = st.shared[sub.name], sep = (display(sub).tree || {}).nested_by || "";
      return s && (s.groups || []).some(v => String(v) === value || (sep && String(v).startsWith(value + sep))) ? `<p class="sub pc-shared">${h(W.sharedGroup.replace("{r}", s.rev))}</p>` : ""; };
    function groupRows(sub, units, field, sep) {
      const kids = {}, direct = {}, below = {};
      const split = v => sep ? String(v).split(sep).filter(Boolean) : [String(v)];
      for (const v of extraGroups(sub)) { const parts = split(v); for (let i = 0; i < parts.length; i++) { const path = parts.slice(0, i + 1).join(sep || ""), up = parts.slice(0, i).join(sep || ""); (kids[up] = kids[up] || new Set()).add(path); below[path] = below[path] || new Set(); } }
      for (const u of units) {
        const vals = Array.isArray(u[field]) && u[field].length ? u[field] : [""];
        for (const v of vals) {
          (direct[v] = direct[v] || []).push(u);
          if (v === "") continue;
          const parts = split(v);
          for (let i = 0; i < parts.length; i++) {
            const path = parts.slice(0, i + 1).join(sep || "");
            (kids[parts.slice(0, i).join(sep || "")] = kids[parts.slice(0, i).join(sep || "")] || new Set()).add(path);
            (below[path] = below[path] || new Set()).add(u.id);
          }
        }
      }
      const tr = display(sub).tree || {};
      const node = (path, depth) => {
        const gref = "group:" + sub.name + "/" + field + "/" + path;
        const sub2 = path === "" ? "" : [...(kids[path] || [])].sort().map(p => node(p, depth + 1)).join("");   // "" is the root's key too
        const rows = (direct[path] || []).map(u => unitRow(sub, u, depth + 1)).join("");
        const name = path === "" ? cap(tr.no_group || W.noGroup) : split(path).pop();
        const selfHit = !st.q.trim() || name.toLowerCase().includes(st.q.trim().toLowerCase());
        if (filtering() && !selfHit && !sub2 && !rows) return "";
        const has = !!((path !== "" && kids[path] && kids[path].size) || (direct[path] || []).length);
        const open = has && (st.open.has(gref) || (filtering() && !!(sub2 || rows)));
        return nrow({ ref: gref, depth, icon: path === "" ? "unalloc" : open ? "folderOpen" : "folder", name, cnt: (below[path] || new Set((direct[path] || []).map(u => u.id))).size, has, open, cls: "srv fld" })
          + (open ? sub2 + rows : "");
      };
      return [...(kids[""] || [])].sort().map(p => node(p, 0)).join("") + ((direct[""] || []).length ? node("", 0) : "");
    }
    // The units a worker carries, and the units no worker carries.
    const carried = w => st.subs.filter(s => !aboutOf(s)).flatMap(s => (st.units[s.name] || []).filter(u => u.worker === w).map(u => ({ s, u })));
    function serverRows(depth) {
      return Object.keys(st.servers).sort().map(n => {
        const s = st.servers[n], ref = "server:" + n, q = st.q.trim().toLowerCase();
        const workers = (s.workers || []).map(w => {
          const wref = "worker:" + w.worker, list = carried(w.worker), vis = list.filter(x => !filtering() || unitMatches(x.s, x.u));
          if (filtering() && !String(w.worker).toLowerCase().includes(q) && !vis.length) return "";
          const open = list.length > 0 && (st.open.has(wref) || filtering());
          return nrow({ ref: wref, depth: depth + 1, icon: "svcs", name: w.worker, tags: tagHtml(`${w.load}/${w.capacity}`, W.loadCap) + (w.server_unsaid ? tagHtml(W.serverUnsaid, w.server_unsaid) : ""), cnt: list.length, has: list.length > 0, open, off: w.state === "stale" })
            + (open ? (filtering() ? vis : list).map(x => unitRow(x.s, x.u, depth + 2)).join("") : "");
        }).join("") + extraRows(nodesOf("server", ref, s), depth + 1);
        if (filtering() && !n.toLowerCase().includes(q) && !workers) return "";
        const held = (s.workers || []).reduce((k, w) => k + carried(w.worker).length, 0);
        const open = st.open.has(ref) || filtering(), d = decorOf(ref);
        return nrow({ ref, depth, iconHtml: d.iconHtml || ic("server"), name: n, tags: tagHtml(s.resource || "—", W.resource) + d.tags, cnt: held, has: !!workers, open, off: s.resource === "silent", cls: "srv" }) + (open ? workers : "");
      }).join("");
    }
    function unplacedRow(depth) {
      const list = st.subs.filter(s => !aboutOf(s)).flatMap(s => (st.units[s.name] || []).filter(u => !u.worker).map(u => ({ s, u })));
      const vis = list.filter(x => !filtering() || unitMatches(x.s, x.u));
      if (!list.length || (filtering() && !vis.length)) return "";
      const open = st.open.has("unplaced") || filtering();
      return nrow({ ref: "unplaced", depth, icon: "unalloc", name: cap(W.unplacedF), cnt: list.length, has: true, open, cls: "srv" }) + (open ? vis.map(x => unitRow(x.s, x.u, depth + 1)).join("") : "");
    }
    // The domain's members under the holder's servers: a member behind a relay (the topology's via) under the relay.
    // A page's node may stand in a member's place (replaces: its row is the member's — a member that is one unit, say);
    // its nodes go under it — those marked after, under the members behind it.
    function memberRows(depth, parent) {
      const v = st.dom; if (!v) return "";
      const via = (v.topology || {}).via || {}, names = new Set((v.members || []).map(m => m.name)), q = st.q.trim().toLowerCase();
      return (v.members || []).filter(m => (domainOnly || !m.holder) && (parent ? via[m.name] === parent : !via[m.name] || !names.has(via[m.name]))).map(m => {
        const ref = "member:" + m.name, extra = nodesOf("member", ref, m), stand = extra.find(x => x.replaces);
        const before = extra.filter(x => !x.replaces && !x.after), after = extra.filter(x => !x.replaces && x.after);
        const behind = memberRows(depth + 1, m.name);
        if (stand) return extraRows([{ ...stand, off: stand.off || m.state !== "ok" }], depth) + behind;
        const rows = extraRows(before, depth + 1) + behind + extraRows(after, depth + 1);
        if (filtering() && !m.name.toLowerCase().includes(q) && !rows) return "";
        const has = !!rows || before.length + after.length > 0 || !!behind;
        const open = has && (st.open.has(ref) || filtering()), d = decorOf(ref);
        const n = domainOnly ? Object.values(v.units || {}).reduce((k, l) => k + (l || []).filter(u => u.cluster === m.name).length, 0) : undefined;
        return nrow({ ref, depth, iconHtml: d.iconHtml || ic("server"), name: m.name, tags: d.tags + (m.holder && domainOnly ? tagHtml(W.holder) : ""), cnt: n, has, open, off: !m.holder && m.state !== "ok", cls: "srv" }) + (open ? rows : "");
      }).join("");
    }
    function paintTree() {
      const el = $(".pc-tree"); if (!el) return;
      paintFavs();
      let html = "";
      if (st.loadErr && !st.subs.length) html = `<div class="n"><span class="nm sub">${h(W.noConsole)}</span></div>`;
      else if (st.section === "units") {
        html = st.subs.filter(s => !aboutOf(s)).map(sub => {
          const units = st.units[sub.name] || [], tr = display(sub).tree || {};
          const body = tr.group_by ? groupRows(sub, units, tr.group_by, tr.nested_by) : units.map(u => unitRow(sub, u, 0)).join("");
          return (st.subs.filter(s => !aboutOf(s)).length > 1 ? `<div class="pc-g">${h(cap(unitWord(sub, true)))}</div>` : "") + (body || (filtering() ? `<div class="n n-empty">${h(W.nothingFound)}</div>` : ""))
;
        }).join("") || (filtering() ? `<div class="n n-empty">${h(W.nothingFound)}</div>` : "");
      } else if (st.section === "servers" || st.section === "domain") {
        const v = st.dom;
        if (v) {
          // the domain is the root: this cluster's servers, the other members, the shared places, the unplaced
          const open = !st.shut.has("domain") || filtering();
          const kids = serverRows(1) + memberRows(1) + extraRows(nodesOf("servers"), 1) + unplacedRow(1);
          html = nrow({ ref: "domain", depth: 0, icon: "domain", name: cap(W.domainWord || W.domain), tags: tagHtml(`${Object.keys(st.servers).length + (v.members || []).filter(m => domainOnly || !m.holder).length} ${W.srvShort}`), has: true, open, off: v.complete === false, cls: "srv" }) + (open ? kids : "");
        } else html = serverRows(0) + extraRows(nodesOf("servers"), 0) + unplacedRow(0);
      } else if (st.section === "access") {
        const a = st.acc;
        html = !a ? `<div class="n n-empty">${h(W.loading)}</div>` : a.users.filter(u => !filtering() || u.name.toLowerCase().includes(st.q.trim().toLowerCase())).map(u => nrow({ ref: "person:" + u.name, icon: "user", name: u.name, off: u.disabled })).join("")
          + accClusters().map(c => nrow({ ref: "grants:" + c, icon: c === "domain" ? "domain" : "server", name: c === "domain" ? W.domainWord : c })).join("")
          + extraRows(nodesOf("access"), 0);
      }
      el.innerHTML = html;
      el.querySelectorAll("[data-new]").forEach(b => { b.onclick = e => { e.stopPropagation(); C.select("new:" + b.dataset.new); }; });
      el.querySelectorAll("[data-tw]").forEach(t => { t.onclick = e => { e.stopPropagation(); const r = t.dataset.tw, set = r === "domain" || t.dataset.shut ? st.shut : st.open; set.has(r) ? set.delete(r) : set.add(r); paintTree(); }; });
      el.querySelectorAll("[data-star]").forEach(b => { b.onclick = e => { e.stopPropagation(); C.toggleFav(b.dataset.star); }; });
      el.querySelectorAll("[data-menu]").forEach(b => { b.onclick = e => { e.stopPropagation(); rowMenu(e, b.dataset.menu); }; });
      el.querySelectorAll(".n[data-ref]").forEach(n => {
        n.onclick = () => C.select(n.dataset.ref);
        n.oncontextmenu = e => { e.preventDefault(); rowMenu(e, n.dataset.ref); };
      });
    }
    // The row's menu — the same by the right button and by «⋯»: open, the star, then what the page adds.
    function rowMenu(e, ref) {
      openMenu(e, [{ label: W.openIt, run: () => C.select(ref) }, { label: C.isFav(ref) ? W.unstar : W.star, run: () => C.toggleFav(ref) }, ...groupMenu(ref), ...menuOf(ref), ...unitDelete(ref)]);
    }
    function groupMenu(ref) {
      const g = parseGroup(ref); if (!g || !C.may("edit", null)) return [];
      const tr = display(g.sub).tree || {};
      if (g.value === "") return [{ label: "＋ " + cap(tr.new_root || W.newRoot), run: () => newGroup(g.sub, "") }];
      return [{ label: "＋ " + cap(tr.new_sub || W.newSub), run: () => newGroup(g.sub, g.value) },
        { label: W.renameGroup, run: () => { C.select(ref); const b = $('.pc-main [data-a="rename"]'); if (b) b.click(); } },
        { label: tr.add_here || W.addHereT.replace("{u}", unitWord(g.sub, false)), run: () => { st.newInto = g.value; C.select("new:" + g.sub.name); } }];
    }
    // a unit's «Delete» in its row's menu, as the product console had it: for whoever may administer it, with a question
    function unitDelete(ref) {
      const u = parseUnit(ref); if (!u || !u.row || !C.may("admin", ref)) return [];
      return [{ label: W.del, run: async () => {
        if (!confirm(W.deleteQ + " " + label(u.sub, u.row) + "?")) return;
        try { await C.api("DELETE", u.sub.base + "/" + u.sub.spec.rows + "/" + encodeURIComponent(u.id)); if (st.sel === ref) st.sel = null; await load(); paintMain(); C.toast(W.deleted); }
        catch (err) { C.toast(W.refused + ": " + err.message); }
      } }];
    }
    // The favourites: their own panel under the tree, folded or not.
    let favOpen = keep("pc.favOpen") !== "0";
    function paintFavs() {
      const el = $(".pc-favs"); if (!el) return;
      el.innerHTML = st.favs.length ? `<div class="fav-panel"><button type="button" class="fav-panel-head pc-favhead" aria-expanded="${favOpen}"><span class="tw">${favOpen ? "▾" : "▸"}</span><span class="fav-star" aria-hidden="true">★</span><span class="nm">${h(cap(W.favs))}</span><span class="cnt">${st.favs.length}</span></button>`
        + (favOpen ? `<div class="fav-panel-list">${st.favs.map(r => { const gone = !favAlive(r); return `<div class="n fav-row${gone ? " gone" : ""}${!gone && st.sel === r ? " on" : ""}" data-fav="${h(r)}"><span class="tw"></span>${favIcon(r)}<span class="nm">${h(favLabel(r))}</span><span class="n-meta"><span class="fav-sub">${h(gone ? W.goneW : favWhere(r))}</span><button type="button" class="n-fav on" tabindex="-1" data-unfav="${h(r)}" title="${h(W.unstar)}">${gone ? "✕" : "★"}</button></span></div>`; }).join("")}</div>` : "") + `</div>` : "";
      const hd = el.querySelector(".pc-favhead"); if (hd) hd.onclick = () => { favOpen = !favOpen; keep("pc.favOpen", favOpen ? "1" : "0"); paintFavs(); };
      el.querySelectorAll("[data-unfav]").forEach(b => { b.onclick = e => { e.stopPropagation(); C.toggleFav(b.dataset.unfav); }; });
      el.querySelectorAll("[data-fav]").forEach(n => { n.onclick = () => {
        const r = n.dataset.fav, sec = r.startsWith("unit:") || r.startsWith("group:") ? "units" : /^(server|worker|member):/.test(r) || r === "domain" ? "servers" : /^(person|grants):/.test(r) ? "access" : st.section;
        if (sec !== st.section) { st.section = sec; paintRail(); paintAside(); if (sec === "access") loadAccess(); }
        C.select(r);
      }; });
    }
    function favAlive(ref) { const u = parseUnit(ref); if (u) return !!u.row; if (String(ref).startsWith("server:")) return !!st.servers[ref.slice(7)]; return true; }
    function favIcon(ref) { const u = parseUnit(ref); if (u) return decorOf(ref).iconHtml || ic("x"); const k = String(ref).split(":")[0]; return ic({ server: "server", worker: "svcs", member: "server", group: "folder", person: "user", grants: "domain" }[k] || (ref === "domain" ? "domain" : "x")); }
    function favWhere(ref) { return /^(unit|group):/.test(ref) ? layouts()[0].label : /^(server|worker|member):/.test(ref) || ref === "domain" ? W.byServers : ""; }
    function menuOf(ref) {
      const kind = String(ref).split(":")[0];
      return (shell.menus[kind] || []).flatMap(fn => { try { return fn(ref, objectOf(ref)) || []; } catch (e) { return []; } });
    }
    function openMenu(e, items) {
      const m = $(".pc-menu"); m.innerHTML = ""; m.style.left = e.clientX + "px"; m.style.top = e.clientY + "px";
      items.forEach(it => { const b = document.createElement("button"); b.type = "button"; b.innerHTML = `<span class="tctx-lbl">${h(it.label)}</span>`; b.onclick = () => { m.classList.remove("open"); it.run(); }; m.appendChild(b); });
      m.classList.add("open"); setTimeout(() => document.addEventListener("click", () => m.classList.remove("open"), { once: true }), 0);
    }

    // -- the inspector ---------------------------------------------------------------------------------------
    // The card's head, as the product console draws it: the path to the object (the last link the object itself),
    // the star and full screen on the right, the tabs under it. A card writes its title as an <h1> and its tab bar
    // as nav.pc-tabs; dressing moves them into the head. Its h2 sections become cards (.card: .ch over .cb), now
    // and whenever a part of it is drawn again.
    function crumbsOf(ref) {
      const r = String(ref), srv = (domainOnly ? [] : [[W.byServers, "layout:servers"]]).concat(st.dom ? [[cap(W.domainWord || W.domain), "domain"]] : []);
      const u = parseUnit(r);
      if (u) {
        const a = aboutOf(u.sub);
        if (a && u.row) { const p = st.subs.find(x => x.name === a.sub), pr = p && (st.units[p.name] || []).find(x => String(x.id) === String(u.row[a.field])); if (pr) return crumbsOf(unitRef(p, pr.id)).concat([[label(p, pr), unitRef(p, pr.id)]]); }
        const tr = display(u.sub).tree || {}, g = tr.group_by; if (!g) return null;
        const v = u.row && Array.isArray(u.row[g]) && u.row[g].length ? String(u.row[g][0]) : "";
        if (!v) return [[cap(tr.no_group || W.noGroup), "group:" + u.sub.name + "/" + g + "/"]];
        const parts = tr.nested_by ? v.split(tr.nested_by).filter(Boolean) : [v];
        return parts.map((seg, i) => [seg, "group:" + u.sub.name + "/" + g + "/" + parts.slice(0, i + 1).join(tr.nested_by || "")]);
      }
      if (r.startsWith("group:")) {
        const m = /^group:([^/]+)\/([^/]+)\/(.*)$/.exec(r), sub = m && st.subs.find(x => x.name === m[1]); if (!sub) return [];
        const sep = (display(sub).tree || {}).nested_by, parts = sep ? m[3].split(sep).filter(Boolean) : [m[3]];
        return parts.slice(0, -1).map((seg, i) => [seg, "group:" + m[1] + "/" + m[2] + "/" + parts.slice(0, i + 1).join(sep || "")]);
      }
      if (r.startsWith("server:") || r.startsWith("member:") || r === "unplaced") return srv;
      if (r === "domain") return domainOnly ? [] : [[W.byServers, "layout:servers"]];
      if (r.startsWith("worker:")) { const n = Object.keys(st.servers).find(k => (st.servers[k].workers || []).some(w => w.worker === r.slice(7))); return n ? srv.concat([[n, "server:" + n]]) : srv; }
      if (/^(person|grants):/.test(r)) return [[cap(W.access), "section:access"]];
      return null;
    }
    function dress() {
      const sc = $(".pc-main"), hd = $(".pc-hd"); if (!sc || !hd) return;
      const top = sel => sc.querySelector(`:scope > ${sel}, :scope > .pc-card > ${sel}`);   // the card's own, or a page's in its host
      const h1 = top("h1");
      if (h1) {
        // the crumbs: the card's own (a page's card names its path as data), else what the module knows of the ref
        const own = h1.querySelector(".pc-crumbs"); let given = null;
        if (own) { try { given = JSON.parse(own.dataset.crumbs || "[]"); } catch (e) { given = []; } own.remove(); }
        const ref = st.sel, crumbs = given && given.length ? given : ref ? crumbsOf(ref) : null;
        const cur = h1.cloneNode(true); cur.querySelectorAll("small:not([class])").forEach(x => x.remove());   // the kind and number; a state word stays
        const fav = ref && C.isFav(ref);
        hd.innerHTML = `<div class="hd-act">${crumbs ? `<div class="cr hd-cr">${crumbs.map(([l, r]) => `<button type="button" class="cr-link" data-go="${h(r)}">${h(l)}</button><span class="cr-sep">/</span>`).join("")}<span class="cr-cur">${cur.innerHTML.trim()}</span></div>`
          : `<h1 style="flex:1;margin:0">${ref ? decorOf(ref).iconHtml : ""}${h1.innerHTML}</h1>`}<span class="hdacts pc-acts"></span>`
          + (ref ? `<button type="button" class="btn s fav-btn fav-only pc-star${fav ? " on" : ""}" title="${h(fav ? W.unstar : W.star)}" aria-pressed="${!!fav}">${fav ? "★" : "☆"}</button><button type="button" class="btn s pc-fullbtn" title="${h(W.full)}">${st.full ? "⤡" : "⤢"}</button>` : "") + `</div>`;
        h1.remove();
        // the page's actions on this kind of object (addAction): buttons in the head, before the star
        const acts = hd.querySelector(".pc-acts"), kind = ref ? String(ref).split(":")[0] : "";
        for (const fn of (shell.actions || {})[kind] || []) {
          let items; try { items = fn(ref, objectOf(ref)) || []; } catch (e) { items = []; }
          for (const it of items) { const b = document.createElement("button"); b.type = "button"; b.className = "btn s"; b.textContent = it.label; b.onclick = () => it.run(); acts.appendChild(b); }
        }
        sc.querySelectorAll(":scope > .pc-hdbtn, :scope > .pc-card > .pc-hdbtn").forEach(b => acts.appendChild(b));
        hd.querySelectorAll("[data-go]").forEach(b => { b.onclick = () => go(b.dataset.go); });
        const sb = hd.querySelector(".pc-star"); if (sb) sb.onclick = () => C.toggleFav(ref);
        const fb = hd.querySelector(".pc-fullbtn"); if (fb) fb.onclick = () => C.fullScreen();
      }
      const sub = top("p.pc-hdsub"); if (sub) hd.appendChild(sub);   // the card's subtitle, under its title
      const nav = top("nav.pc-tabs");
      if (nav) { nav.className = "tabs pc-tabs"; nav.querySelectorAll("button").forEach(b => b.classList.add("tab")); hd.appendChild(nav); }
      cardify(sc);
    }
    // A crumb: a layout of the panel, a section, or an object.
    function go(to) {
      if (to.startsWith("layout:")) { keep("pc.layout", to.slice(7)); st.section = to.slice(7); st.sel = null; paintRail(); paintAside(); paintMain(); return; }
      if (to.startsWith("section:")) return goSection(to.slice(8));
      const sec = /^(unit|group):/.test(to) ? "units" : /^(server|worker|member):/.test(to) || to === "domain" || to === "unplaced" ? "servers" : null;
      if (sec && sec !== st.section && !(sec === "servers" && st.section === "domain")) { st.section = sec; paintRail(); paintAside(); }
      C.select(to);
    }
    function cardify(root) {
      [...root.querySelectorAll("h2")].forEach(h2 => {
        const box = h2.parentElement; if (!box || !h2.isConnected) return;
        const ch = document.createElement("div"); ch.className = "ch"; ch.innerHTML = h2.innerHTML;
        const cb = document.createElement("div"); cb.className = "cb";
        if (box !== root && box.firstElementChild === h2 && !box.classList.contains("cb")) {
          // a box of its own (labels, drain, ...): it becomes the card
          box.classList.add("card");
          while (h2.nextSibling) cb.appendChild(h2.nextSibling);
          h2.replaceWith(ch); box.appendChild(cb);
        } else {
          // an h2 among others: it and what follows it, up to the next heading, become a card
          const card = document.createElement("div"); card.className = "card";
          h2.before(card); card.append(ch, cb);
          while (card.nextSibling && !(card.nextSibling.nodeType === 1 && /^H[12]$/.test(card.nextSibling.tagName))) cb.appendChild(card.nextSibling);
          h2.remove();
        }
      });
    }
    // the footer saves and cancels the selected object's form
    const setDirty = on => { $(".pc-save").disabled = !on; $(".pc-discard").disabled = !on; $(".pc-hint").textContent = on ? W.unsaved : W.hint; };
    const formOf = () => $(".pc-main form.pc-edit:not(.pc-new-f)");
    $(".pc-main").addEventListener("input", e => { if (e.target.closest && e.target.closest("form.pc-edit:not(.pc-new-f)")) setDirty(true); });
    $(".pc-main").addEventListener("change", e => { if (e.target.closest && e.target.closest("form.pc-edit:not(.pc-new-f)")) setDirty(true); });
    $(".pc-save").onclick = () => { const f = formOf(); if (f) f.requestSubmit(); };
    $(".pc-discard").onclick = () => { setDirty(false); paintMain(); C.toast(W.discarded); };
    // what is drawn later (a page's card after its request) is dressed too: its head moved up, its sections made cards
    if (typeof MutationObserver === "function") new MutationObserver(() => { const sc = $(".pc-main"); if (sc.querySelector(":scope > h1, :scope > .pc-card > h1")) { $(".pc-hd").innerHTML = ""; dress(); } else cardify(sc); }).observe($(".pc-main"), { childList: true, subtree: true });
    function paintMain() { $(".pc-hd").innerHTML = ""; setDirty(false); paintMainInner(); dress(); }
    // A poll repaints the card with the new data — but never under a person's hands: not while a field in it has
    // the focus or differs from what the row showed, not while a dialog is open. The scroll stays where it was.
    function pageOwnsCard() {
      const kind = String(st.sel || "").split(":")[0];
      return !!((shell.cards || {})[kind] || shell.sections.some(s => s.id === st.section) || ((shell.tabs[kind] || []).some(t => t.id === st.tab[kind])));
    }
    function refreshMain() {
      const el = $(".pc-main"); if (!el || (!st.sel && !domainOnly)) return;
      const a = document.activeElement;
      if (a && el.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName)) return;
      if ([...el.querySelectorAll("input,select,textarea")].filter(x => !x.readOnly && !x.disabled && x.type !== "hidden").some(x => x.dataset.orig !== undefined ? x.value !== x.dataset.orig : (x.type !== "checkbox" && x.type !== "search" && x.tagName !== "SELECT" && x.value !== ""))) return;
      if (!$(".pc-dialog").hidden || !$(".pc-login").hidden || st.topo || st.labelDraft) return;
      // a page's tab that says it is busy (busy(): something under way in it a repaint would cut) is left alone
      const kind = String(st.sel).split(":")[0], cur = (shell.tabs[kind] || []).find(t => t.id === st.tab[kind]);
      if (cur && typeof cur.busy === "function") { try { if (cur.busy()) return; } catch (e) { /* not busy */ } }
      const top = el.scrollTop;
      paintMain();
      el.scrollTop = top;
    }
    function paintMainInner() {
      const el = $(".pc-main");
      const own = shell.sections.find(s => s.id === st.section);
      if (own) { el.innerHTML = ""; const host = document.createElement("div"); host.className = "pc-card"; el.appendChild(host); own.render(host); return; }
      if (st.section === "journal") return paintJournal(el);
      const ref = st.sel;
      if (!ref) {
        el.innerHTML = `<h1>${h(W.pick)}</h1>`;
        if (st.section === "access" && C.may("admin", "domain")) {
          el.insertAdjacentHTML("beforeend", `<button type="button" class="btn s pc-newperson">${h(W.newPerson)}</button>`);
          el.querySelector(".pc-newperson").onclick = async () => {
            const v = await C.dialog(W.newPerson, [{ name: "name", label: W.name }, { name: "password", label: W.pass10, type: "password" }], W.add);
            if (v) accDo("POST", "/domain/users", { name: v.name.trim(), password: v.password });
          };
        }
        if (domainOnly) return paintDomain(el, "domain");
        if (st.section === "units" || st.section === "servers" || st.section === "domain") return paintRoot(el);
        return;
      }
      const u = parseUnit(ref);
      if (u) return paintUnit(el, ref, u);
      if (String(ref).startsWith("new:")) return paintNew(el, String(ref).slice(4));
      if (ref.startsWith("server:")) return paintServer(el, ref, ref.slice(7));
      if (ref.startsWith("worker:")) return paintWorker(el, ref, ref.slice(7));
      if (String(ref).startsWith("group:")) return paintGroup(el, ref);
      if (ref === "domain") return paintDomain(el, ref);
      if (ref === "unplaced") return paintUnplaced(el);
      if (ref.startsWith("member:")) return paintMember(el, ref, ref.slice(7));
      if (ref.startsWith("person:")) return paintPerson(el, ref, ref.slice(7));
      if (ref.startsWith("grants:")) return paintGrants(el, ref, ref.slice(7));
      const cardOf = (shell.cards || {})[String(ref).split(":")[0]];
      // a host of its own: what the page draws late (after its own request) lands in it, never in another card
      if (cardOf) { el.innerHTML = ""; const host = document.createElement("div"); host.className = "pc-card"; el.appendChild(host); try { cardOf(host, ref); } catch (e) { host.textContent = String(e); } return; }
      el.innerHTML = "";                                   // a ref nobody draws
    }
    // The page's tabs on a card: a tab bar — the module's own card is "general", each added tab one more. One
    // shows at a time; the choice is kept per kind of object while the page is open.
    function tabsOf(kind, el, ref, obj, opt) {
      opt = opt || {};
      const tabs = (shell.tabs[kind] || []).filter(t => t.id !== "general").concat(opt.extra || []);   // "general" replaces the module's card
      if (!tabs.length) return;
      const own = [...el.children].filter(c => c.tagName !== "H1");
      const bar = document.createElement("nav"); bar.className = "pc-tabs";
      const cur = tabs.some(t => t.id === st.tab[kind]) ? st.tab[kind] : "general";
      bar.innerHTML = `<button type="button" data-tab="general" class="${cur === "general" ? "on" : ""}">${h(opt.general || W.general)}</button>` + tabs.map(t => `<button type="button" data-tab="${h(t.id)}" class="${cur === t.id ? "on" : ""}">${h(t.label)}</button>`).join("");
      const h1 = el.querySelector("h1"); if (h1) h1.after(bar); else el.prepend(bar);
      own.forEach(c => { c.hidden = cur !== "general"; });
      for (const t of tabs) {
        const box = document.createElement("section"); box.className = "pc-tab"; box.dataset.tab = t.id; box.hidden = cur !== t.id; el.appendChild(box);
        if (cur === t.id) { try { t.render(box, ref, obj); } catch (e) { box.textContent = String(e); } }
      }
      bar.querySelectorAll("button").forEach(b => { b.onclick = () => { st.tab[kind] = b.dataset.tab; paintMain(); }; });
    }

    // One field, as the product console draws it: its title over the control (display.fields; its help as the
    // control's tip). Every control carries the field's value under its name, so the form reads them all alike
    // (formBody): a bool is a switch over a hidden checkbox; the field the tree groups by is the box of its groups
    // over a hidden input; another list is its items, comma-separated; a field with a set of values (enum) is a
    // select, its values in the words of display.options when it has them; a secret is an empty password field whose hint says whether one is set; a field
    // the page has an editor for is the editor's slot.
    const fieldTitle = (sub, name) => (display(sub).fields || {})[name] || name;
    const fldRo = (title, value) => `<div><label>${h(title)}</label><input type="text" value="${h(value ?? "")}" readonly disabled></div>`;
    function fieldInput(sub, f, row) {
      const d = display(sub), help = (d.field_help || {})[f.name], title = fieldTitle(sub, f.name), tip = help ? ` title="${h(help)}"` : "";
      const dis = C.may("edit", row ? unitRef(sub, row.id) : null) && !(row && f.fixed) ? "" : " disabled";
      const ed = row && f.fixed ? null : ((shell.editors || {}).unit || {})[f.name];
      const v = row ? (f.type === "list" ? (row[f.name] || []).join(", ") : (row[f.name] ?? "")) : "";
      if (f.type === "bool") {
        const on = row ? !!row[f.name] : !!f.default;
        return `<div class="ln ln-sw"><div>${h(title)}</div><div class="sw${on ? " on" : ""}" data-sw="${h(f.name)}"${tip}></div><input type="checkbox" name="${h(f.name)}" hidden${on ? " checked" : ""}${dis}></div>`;
      }
      if (ed) return `<div class="pc-field" style="grid-column:1/-1"${tip}><input type="hidden" name="${h(f.name)}" value="${h(v)}" data-orig="${h(v)}"><div class="pc-editor" data-editor="${h(f.name)}"></div></div>`;
      if (isSecret(f.name)) return `<div><label>${h(title)}</label><input type="password" name="${h(f.name)}" autocomplete="new-password" placeholder="${row ? h(row[f.name] ? W.setKeeps : W.notSet) : ""}"${tip}${dis}></div>`;
      if (f.type === "list" && f.name === (d.tree || {}).group_by) return groupsBox(sub, f, row, v, dis);
      if (f.type === "list") {
        const opts = f.name === "labels" ? [...new Set(Object.values(st.servers).flatMap(s2 => s2.labels || s2.labels_node || []))].sort() : [];
        return `<div><label>${h(title)}</label><input type="text" name="${h(f.name)}" value="${h(v)}" data-orig="${h(v)}"${opts.length ? ` list="pc-dl-${h(f.name)}"` : ""}${tip}${dis}>${opts.length ? `<datalist id="pc-dl-${h(f.name)}">${opts.map(o => `<option value="${h(o)}">`).join("")}</datalist>` : ""}</div>`;
      }
      // the values a field takes are the spec's (enum); display.options are only their words
      const vals0 = Array.isArray(f.enum) ? f.enum : f.schema && Array.isArray(f.schema.enum) ? f.schema.enum : null;
      if (vals0) {
        const words = (d.options || {})[f.name] || {}, cur = row ? String(row[f.name] ?? "") : String(f.default ?? "");
        const vals = vals0.map(String); if (cur && !vals.includes(cur)) vals.push(cur);
        const shown = cur || vals[0] || "";   // what the select shows is what the row has: not a change
        return `<div><label>${h(title)}</label><select name="${h(f.name)}" data-orig="${h(row ? shown : "")}"${tip}${dis}>${vals.map(x => `<option value="${h(x)}"${x === shown ? " selected" : ""}>${h(words[x] || x)}</option>`).join("")}</select></div>`;
      }
      const num = f.type === "int" || f.type === "float";
      return `<div><label>${h(title)}</label><input type="${num ? "number" : "text"}" name="${h(f.name)}" value="${h(v)}" data-orig="${h(v)}"${f.type === "float" ? ' step="any"' : ""}${!row && f.default != null ? ` placeholder="${h(f.default)}"` : ""}${tip}${dis}></div>`;
    }
    // The field the tree groups by: the groups the unit is in, each with «Remove», and a select of the others to add
    // it to; a new group is one more value (it lives while a unit carries it).
    function groupsBox(sub, f, row, v, dis) {
      const list = v.split(",").map(x => x.trim()).filter(Boolean), tr = display(sub).tree || {}, sep = tr.nested_by;
      const all = new Set();
      for (const x of [...(st.units[sub.name] || []).flatMap(u => Array.isArray(u[f.name]) ? u[f.name] : []), ...extraGroups(sub)]) { const p = sep ? String(x).split(sep).filter(Boolean) : [String(x)]; for (let i = 1; i <= p.length; i++) all.add(p.slice(0, i).join(sep || "")); }
      const others = [...all].filter(p => !list.includes(p)).sort();
      return `<div class="fold-box pc-groups" style="grid-column:1/-1" data-groups="${h(f.name)}"><label>${h(fieldTitle(sub, f.name))}</label><input type="hidden" name="${h(f.name)}" value="${h(v)}" data-orig="${h(v)}">
        ${list.map(p => `<div class="it fold-it"><span>${ic("folder")}</span><span style="flex:1;min-width:0">${h(p)}</span>${dis ? "" : `<button type="button" class="btn s" data-ungroup="${h(p)}">${h(cap(tr.remove || W.removeShort))}</button>`}</div>`).join("")
          || `<p class="sub" style="margin:0 0 8px">${h(tr.not_in || W.inNoGroup.replace("{g}", cap(tr.no_group || W.noGroup)))}</p>`}
        ${dis ? "" : `<div class="fold-add"><select class="pc-addgroup"${others.length ? "" : " disabled"}><option value="">${h(others.length ? tr.add_to || W.addToGroup + "…" : tr.no_others || W.noOtherGroups)}</option>${others.map(p => `<option value="${h(p)}">${h(p)}</option>`).join("")}</select><button type="button" class="btn s pc-newgroup">＋ ${h(tr.new_group || W.newGroup)}</button></div>`}</div>`;
    }
    function wireGroups(form) {
      form.querySelectorAll("[data-groups]").forEach(box => {
        const hid = box.querySelector('input[type="hidden"]');
        const set = list => { hid.value = [...new Set(list.filter(Boolean))].join(", "); hid.dispatchEvent(new Event("input", { bubbles: true })); redraw(); };
        const items = () => hid.value.split(",").map(x => x.trim()).filter(Boolean);
        const redraw = () => {
          const sub = st.subs.find(s => form.dataset.sub === s.name); if (!sub) return;
          const f = sub.spec.fields.find(x => x.name === box.dataset.groups);
          const tmp = document.createElement("div"); tmp.innerHTML = groupsBox(sub, f, null, hid.value, "");
          const nb = tmp.firstElementChild; nb.querySelector('input[type="hidden"]').replaceWith(hid); box.replaceWith(nb); box = nb; wire();
        };
        const wire = () => {
          box.querySelectorAll("[data-ungroup]").forEach(b => { b.onclick = () => set(items().filter(x => x !== b.dataset.ungroup)); });
          const sel = box.querySelector(".pc-addgroup"); if (sel) sel.onchange = () => { if (sel.value) set(items().concat([sel.value])); };
          const nb = box.querySelector(".pc-newgroup"); if (nb) nb.onclick = async () => { const r = await C.dialog(W.newGroup, [{ name: "name", label: W.newName }], W.add); if (r && r.name.trim()) set(items().concat([r.name.trim()])); };
        };
        wire();
      });
    }
    // A switch: on a unit that is, it is written at once (as the product console does); on a new one, it is the form's.
    function wireSwitches(form, sub, row) {
      form.querySelectorAll("[data-sw]").forEach(sw => {
        const cb = form.elements[sw.dataset.sw]; if (!cb || cb.disabled) return;
        sw.onclick = async () => {
          cb.checked = !cb.checked; sw.classList.toggle("on", cb.checked);
          if (!row) return;
          try { await C.api("PUT", sub.base + "/" + sub.spec.rows + "/" + encodeURIComponent(row.id), { [cb.name]: cb.checked }); C.toast(W.saved); await load(); }
          catch (err) { cb.checked = !cb.checked; sw.classList.toggle("on", cb.checked); C.toast(W.refused + ": " + err.message); }
        };
      });
    }
    function wireEditors(form, sub, ref, row) {
      const eds = (shell.editors || {}).unit || {};
      form.querySelectorAll("[data-editor]").forEach(host => {
        const name = host.dataset.editor, hid = form.elements[name], render = eds[name]; if (!render || !hid) return;
        try { render(host, ref, row, hid.value, v => { hid.value = v == null ? "" : String(v); hid.dispatchEvent(new Event("input", { bubbles: true })); }); } catch (e) { host.textContent = String(e); }
      });
    }
    // A form into a body: bools always; an empty input omitted (default on create, unchanged on edit); on edit a
    // field left as the row showed it is not sent (the row comes with its secrets masked); a secret that reads as
    // the mask is never sent.
    function formBody(sub, form, editing) {
      const out = {};
      for (const f of sub.spec.fields) {
        const el = form.elements[f.name]; if (!el) continue;
        if (f.type === "bool") { out[f.name] = el.checked; continue; }
        const v = el.value;
        if (v === "") continue;
        if (editing && el.dataset.orig !== undefined && v === el.dataset.orig) continue;
        if (isSecret(f.name) && v === MASK) continue;
        out[f.name] = f.type === "list" ? v.split(",").map(x => x.trim()).filter(Boolean) : f.type === "int" ? parseInt(v, 10) : f.type === "float" ? Number(v) : v;
      }
      return out;
    }
    // A unit's state in a word, and as a badge: running, waiting for a place, switched off, silent, or its phase.
    function stateOf(u) {
      if (u.enabled === false) return [W.stOff, "off", "var(--mu)"];
      if (!u.worker) return [W.stUnplaced, "off", "var(--rd)"];
      if (u.worker_state === "stale") return [W.stStale, "off", "var(--rd)"];
      if (u.phase === "failed") return [W.stFailed, "off", "var(--rd)"];
      if (u.phase === "running") return [W.stRunning, "", "var(--gn)"];
      return [W.stStarting, "", "var(--bl)"];
    }
    // Why a unit has no worker, from /unplaceable: the labels no live worker covers, or no live worker at all.
    function whyUnplaceable(sub, u) {
      const x = ((st.unplaceable || {})[sub.name] || []).find(y => String(y.id ?? y.ID) === String(u.id)); if (!x) return "";
      const labels = x.labels || x.Labels || [], live = x.workers_live ?? x.live ?? 0;
      return labels.length ? W.whyLabels.replace("{n}", live).replace("{l}", labels.join(", ")) : W.whyLive.replace("{n}", live);
    }
    // the page's words about a unit that the spec cannot say (addNote): warnings under its placement
    C.addNote = (kind, fn) => { (shell.notes = shell.notes || {})[kind] = ((shell.notes || {})[kind] || []).concat([fn]); return C; };
    const unitNotes = (ref, row) => ((shell.notes || {}).unit || []).flatMap(fn => { try { const t = fn(ref, row); return Array.isArray(t) ? t : t ? [t] : []; } catch (e) { return []; } }).filter(Boolean);
    const stateBadge = u => { const [w, c] = stateOf(u); return `<span class="bd${c ? " " + c : ""} pc-state">${h(w)}</span>`; };
    const card = (title, body, act) => `<div class="card"><div class="ch">${title}${act || ""}</div><div class="cb">${body}</div></div>`;
    // The general form's blocks (display.form: [{title, fields, state, placement, note}]), in order; without them, one
    // block with every field. A block's fields: the switches first, the rest in the grid; «placement» puts the
    // worker and server, the state and the controller's why in it; Delete is on the last block's head.
    function formCards(sub, row, ref) {
      const d = display(sub), byName = n => sub.spec.fields.find(f => f.name === n);
      const all = sub.spec.fields.filter(f => f.name !== sub.spec.id && !(!row && sub.spec.id === "numeric" && f.name === "id")).map(f => f.name);
      const groups = Array.isArray(d.form) && d.form.length ? d.form : [{ title: d.general || W.general, state: true, placement: true, fields: all }];
      const del = row && C.may("admin", ref) ? `<button type="button" class="btn s pc-del">${h(W.del)}</button>` : "";
      return groups.map((g, gi) => {
        const names = (g.fields || []).filter(n => n === "id" || all.includes(n));
        const bools = names.map(byName).filter(f => f && f.type === "bool");
        let grid = names.filter(n => n === "id" ? !!row : byName(n) && byName(n).type !== "bool").map(n => n === "id" ? fldRo(fieldTitle(sub, "id"), row.id) : fieldInput(sub, byName(n), row)).join("");
        // a row's own words, read only (status: [{field, since, title}]): what its worker says it is doing, and since when
        const status = row ? (g.status || []).filter(x => row[x.field] != null && row[x.field] !== "").map(x => {
          const w2 = ((d.options || {})[x.field] || {})[row[x.field]] || row[x.field], at = x.since ? +row[x.since] : 0;
          return fldRo(x.title || fieldTitle(sub, x.field), w2 + (at ? ` · ${W.sinceW} ${fmt(at)} (${dur(Math.max(0, Date.now() / 1000 - at))})` : ""));
        }).join("") : "";
        if (g.placement && row) grid = fldRo(W.workerServer, row.worker ? row.worker + " · " + (row.server || "—") : "—") + fldRo(W.state, stateOf(row)[0]) + status + grid;
        else if (status) grid = status + grid;
        const body = (g.state && row ? stateBadge(row) : "") + bools.map(f => fieldInput(sub, f, row)).join("")
          + (grid ? `<div class="g" style="margin-top:10px">${grid}</div>` : "")
          + (g.note ? `<p class="sub">${h(g.note)}</p>` : "")
          + (g.placement && row ? unitNotes(ref, row).map(t => `<div class="nt err" style="margin-top:10px">${h(t)}</div>`).join("") : "")
          + (g.placement && row && whyUnplaceable(sub, row) ? `<div class="nt err" style="margin-top:8px">${h(W.notPlacing)}: ${h(whyUnplaceable(sub, row))}</div>` : "")
          + (g.placement && row ? (row.last_error ? `<div class="nt err" style="margin-top:10px">${h(row.last_error)}</div>` : "") + `<p class="sub pc-why">${h(row.worker ? W.whyAsking : W.notPlacedYet)}</p>` : "");
        return card(h(g.title || ""), body, gi === groups.length - 1 ? del : "");
      }).join("");
    }
    async function paintUnit(el, ref, u) {
      const { sub, id, row } = u, r = row || {};
      el.innerHTML = `<h1>${h(label(sub, r.id != null ? r : { id }))} <small>${h(unitWord(sub, false))} #${h(id)}</small></h1><div class="pc-general"></div>`;
      // The general card: the page's own (addTab id "general" — for layout only, with unitForm inside) or the form.
      const general = el.querySelector(".pc-general"), own = (shell.tabs.unit || []).find(t => t.id === "general");
      if (own) { try { own.render(general, ref, row); } catch (e) { general.textContent = String(e); } }
      else C.unitForm(general, ref);
      // the unit's events and the person's marks: a tab of their own, unless the spec says the page shows them
      const evTab = display(sub).events === false ? [] : [{ id: "events", label: W.events, render: box => {
        box.innerHTML = card(h(W.events), `<div class="pc-row"><span class="pc-evstate"></span><select class="pc-evf"></select>
          ${C.may("edit", ref) ? `<form class="pc-mark pc-row"><input name="note" placeholder="${h(W.markPh)}"><button type="submit" class="btn s">${h(W.mark)}</button></form>` : ""}</div><ul class="pc-evlist"></ul>`);
        const mark = box.querySelector(".pc-mark");
        if (mark) mark.onsubmit = async e => {
          e.preventDefault();
          try { await C.api("POST", "/marks", { unit: sub.name + "/" + id, note: mark.elements.note.value }); mark.reset(); setTimeout(() => loadEvents(ref), 3500); }
          catch (err) { box.querySelector(".pc-evstate").textContent = W.refused + ": " + err.message; }
        };
        box.querySelector(".pc-evf").onchange = ev => { st.evfilter = ev.target.value; drawEvents(box); };
        loadEvents(ref);
      } }];
      tabsOf("unit", el, ref, row, { general: display(sub).general, extra: evTab });
      const w = await C.where(ref);
      const why = el.querySelector(".pc-why");
      if (why && st.sel === ref && r.worker) why.textContent = w && w.reason ? W.placement + ": " + w.reason : W.noReason;
    }
    // A new unit: the spec's fields by their types (defaults as hints), POST /<rows>; a numbered subsystem's
    // number is the server's. The new unit is selected when the console answers.
    function paintNew(el, name) {
      const sub = st.subs.find(x => x.name === name); if (!sub) { el.innerHTML = ""; return; }
      const rowsPath = sub.base + "/" + sub.spec.rows;
      el.innerHTML = `<h1>${h(W.newUnit)} ${h(unitWord(sub, false))}</h1>
        <form class="pc-edit pc-new-f" data-sub="${h(sub.name)}">${formCards(sub, null, null)}
          <div class="pc-row"><button type="submit" class="btn pri">${h(W.create)}</button></div><div class="nt err pc-err"></div></form>`;
      const form = el.querySelector("form");
      const gf = (display(sub).tree || {}).group_by;
      if (st.newInto && gf && form.elements[gf]) { form.elements[gf].value = st.newInto; const tmp = document.createElement("div"); tmp.innerHTML = groupsBox(sub, sub.spec.fields.find(f => f.name === gf), { [gf]: [st.newInto], id: "" }, st.newInto, ""); const box = form.querySelector(`[data-groups="${gf}"]`); if (box) { const nb = tmp.firstElementChild; nb.querySelector('input[type="hidden"]').replaceWith(form.elements[gf]); box.replaceWith(nb); } }
      wireGroups(form); wireSwitches(form, sub, null);
      form.onsubmit = async e => {
        e.preventDefault(); form.querySelector(".pc-err").textContent = "";
        try {
          const out = await C.api("POST", rowsPath, formBody(sub, form, false));
          await load(); C.toast(W.created);
          const id = out && (out.id ?? out.ID ?? (out.unit && out.unit.id));
          if (id != null) C.select(unitRef(sub, id)); else paintMain();
        } catch (err) { form.querySelector(".pc-err").textContent = W.refused + ": " + err.message; if (err.retry) C.toast(W.refused + ": " + err.message); }
      };
    }
    // The general form of a unit into host: its blocks, Delete as may() allows, the page's field editors in their
    // slots; the footer saves it. The page's own general card calls it for its fields.
    C.unitForm = (host, ref) => {
      const u = parseUnit(ref); if (!u) return null;
      const { sub, id, row } = u, r = row || {}, rowsPath = sub.base + "/" + sub.spec.rows;
      host.innerHTML = `<form class="pc-edit" data-sub="${h(sub.name)}">${formCards(sub, r, ref)}
        ${C.may("edit", ref) ? `<button type="submit" class="pc-save-in">${h(W.save)}</button>` : ""}<div class="nt err pc-err"></div></form>`;
      const form = host.querySelector(".pc-edit");
      wireGroups(form); wireSwitches(form, sub, r); wireEditors(form, sub, ref, row);
      form.onsubmit = async e => {
        e.preventDefault(); form.querySelector(".pc-err").textContent = "";
        // A secret bound to other fields (the spec's bound_to) is asked anew when one of them changes: the server
        // would refuse to send the one it keeps to the new value.
        const stale = staleSecrets(sub, form, r);
        if (stale.length) { form.querySelector(".pc-err").textContent = stale.map(n => fieldTitle(sub, n)).join(", ") + ": " + W.boundAnew; form.elements[stale[0]].focus(); return; }
        try { await C.api("PUT", rowsPath + "/" + encodeURIComponent(id), formBody(sub, form, true)); C.toast(W.saved); await load(); paintMain(); }
        catch (err) { form.querySelector(".pc-err").textContent = W.refused + ": " + err.message; C.toast(W.refused + ": " + err.message); }
      };
      const del = host.querySelector(".pc-del");
      if (del) del.onclick = async () => {
        if (!confirm(W.deleteQ + " " + label(sub, r) + "?")) return;
        try { await C.api("DELETE", rowsPath + "/" + encodeURIComponent(id)); st.sel = null; await load(); paintMain(); } catch (err) { form.querySelector(".pc-err").textContent = W.refused + ": " + err.message; }
      };
      return form;
    };
    function staleSecrets(sub, form, row) {
      return sub.spec.fields.filter(f => isSecret(f.name) && Array.isArray(f.bound_to) && row[f.name]).filter(f => {
        const el = form.elements[f.name], v = el ? el.value : "";
        if (v && v !== MASK) return false;
        return f.bound_to.some(b => { const x = form.elements[b]; return x && x.dataset.orig !== undefined && x.value !== x.dataset.orig; });
      }).map(f => f.name);
    }
    async function loadEvents(ref) {
      const u = parseUnit(ref); if (!u || st.sel !== ref) return;
      const el = $(".pc-main"), s = el.querySelector(".pc-evstate"); if (!s) return;
      const now = Date.now() / 1000;
      try {
        const r = await fetch(`/events?from=${now - 86400}&to=1e12&unit=${encodeURIComponent(u.sub.name + "/" + u.id)}`);
        if (r.ok) { const d = await r.json(); st.events = d.events || []; s.textContent = d.state || ""; s.className = "pc-evstate" + (d.state === "live" ? "" : " bad"); }
        else { st.events = []; s.textContent = W.noEvents + ": " + r.status; s.className = "pc-evstate bad"; }
      } catch (e) { st.events = []; s.textContent = W.noEvents; s.className = "pc-evstate bad"; }
      drawEvents(el);
    }
    function drawEvents(el) {
      const sel = el.querySelector(".pc-evf"), list = el.querySelector(".pc-evlist"); if (!sel || !list) return;
      const subs = [...new Set(st.events.map(e => e.subsystem))].sort();
      sel.innerHTML = `<option value="">${h(W.every)}</option>` + subs.map(s => `<option value="${h(s)}">${h(s)}</option>`).join("");
      sel.value = subs.includes(st.evfilter) ? st.evfilter : "";
      const shown = st.events.filter(e => !sel.value || e.subsystem === sel.value).slice().reverse();
      list.innerHTML = shown.map(e => `<li><span title="${h(e.kind)}">${h(fmt(e.t || e.ts))} <strong>${h(kindWord(e))}</strong></span> <small>${h(e.unit)}${e.of && e.of !== e.unit ? " · " + h(e.of) : ""}${eventNote(e) ? " · " + h(eventNote(e)) : ""}${e.server ? " · " + h(e.server) : ""}</small></li>`).join("");
    }
    // Nothing selected: the section's overview — what it holds; by servers, the cluster: its counts, the policy of
    // units on a server, the store's layout version (/schema) and who keeps it from rising, the drain under way.
    // «＋ <unit>»: a new unit of each subsystem the tree shows, from the head of the section and of a group (into it).
    const newBtns = group => C.may("edit", null) ? st.subs.filter(s => !aboutOf(s)).map(s => `<button type="button" class="btn s pc-hdbtn" data-new="${h(s.name)}"${group ? ` data-into="${h(group)}"` : ""}>＋ ${h(cap(unitWord(s, false)))}</button>`).join("") : "";
    const groupBtns = parent => C.may("edit", null) ? st.subs.filter(s => !aboutOf(s) && (display(s).tree || {}).group_by).map(s => { const tr = display(s).tree; return `<button type="button" class="btn s pc-hdbtn" data-newgroup="${h(s.name)}" data-parent="${h(parent || "")}">＋ ${h(cap(parent ? tr.new_sub || W.newSub : tr.new_root || W.newRoot))}</button>`; }).join("") : "";
    function wireNew(el) {
      el.querySelectorAll("[data-new]").forEach(b => { b.onclick = () => { st.newInto = b.dataset.into || ""; C.select("new:" + b.dataset.new); }; });
      el.querySelectorAll("[data-newgroup]").forEach(b => { b.onclick = () => { const sub = st.subs.find(x => x.name === b.dataset.newgroup); if (sub) newGroup(sub, b.dataset.parent); }; });
    }
    function paintRoot(el) {
      const r0 = st.subs[0], tops = st.subs.filter(s => !aboutOf(s)), nServers = Object.keys(st.servers).length;
      const count = s => `${(st.units[s.name] || []).length} ${display(s).units_count || unitWord(s, true)}`;
      el.innerHTML = `<h1>${h(cap((r0 && display(r0).section) || W.hwSection))}</h1><p class="sub pc-hdsub">${h(tops.map(count).join(" · ") + " · " + nServers + " " + W.serversInCluster)}</p>${st.section === "units" ? groupBtns("") + newBtns() : ""}`;
      wireNew(el);
      if (st.section === "units") {
        el.insertAdjacentHTML("beforeend", card(h(W.pickTitle), (r0 && (display(r0).tree || {}).pick_note) ? `<p class="sub">${h(display(r0).tree.pick_note)}</p>` : ""));
        return;
      }
      const sc = st.schema, procs = sc && sc.processes ? Object.entries(sc.processes) : [], stale = procs.filter(([, p]) => !p.live);
      const live = Object.values(st.servers).filter(x => x.resource === "live").length, pol = st.policy || {}, admin = C.may("admin", null);
      el.insertAdjacentHTML("beforeend", card(h(W.clusterW), `<div class="mx">${mc(W.serversN, nServers)}${mc(W.resOnlineN, live)}${st.subs.map(s => mc(cap(display(s).units_count || unitWord(s, true)), (st.units[s.name] || []).length)).join("")}</div>
        <div class="g" style="margin-top:10px"><div><label>${h(W.unitsOnServer)}</label><select class="pc-policy"${admin ? "" : " disabled"}>${["shared", "distinct"].map(v => `<option value="${v}"${pol.servers === v ? " selected" : ""}>${h(v + " — " + (v === "shared" ? W.policyShared : W.policyDistinct))}</option>`).join("")}</select></div>
          ${fldRo(W.schemaVer, sc ? `${sc.can_raise_to ?? "—"}${sc.builds ? " · " + W.buildsW + ": " + sc.builds.join(", ") : ""}` : "—")}</div>
        ${stale.length ? `<p class="sub">${h(W.silentProcs.replace("{p}", stale.map(([n]) => n).join(", ")))}</p>` : ""}
        ${st.drain && st.drain.draining ? `<p class="sub">${h(W.drainingNow)}: <b>${h(st.drain.draining)}</b> — ${h(st.drain.safe ? W.canStop : W.notAllMoved)}.</p>` : ""}`));
      const sel = el.querySelector(".pc-policy");
      if (sel) sel.onchange = async () => { try { await C.api("PUT", "/policy", { servers: sel.value }); await load(); paintMain(); C.toast(W.saved); } catch (err) { C.toast(W.refused + ": " + err.message); } };
    }
    // The units no worker carries, each with why when /unplaceable says; and every server's networks — the labels
    // placement reads.
    function paintUnplaced(el) {
      const list = st.subs.filter(s => !aboutOf(s)).flatMap(s => (st.units[s.name] || []).filter(u => !u.worker).map(u => ({ s, u }))), r0 = st.subs[0];
      el.innerHTML = `<h1>${h(cap(W.unplacedF))}</h1>
        ${card(h(cap(r0 ? unitWord(r0, true) : W.units) + " " + W.noWorkerSuffix), list.map(x => { const ref = unitRef(x.s, x.u.id), why = whyUnplaceable(x.s, x.u);
          return `<div class="it" data-ref="${h(ref)}"><span>${decorOf(ref).iconHtml || ic("x")}</span><span>${h(label(x.s, x.u))}<small>${h(stateOf(x.u)[0])}${why ? " · " + h(why) : ""}</small></span>${stateBadge(x.u)}</div>`; }).join("") || `<p class="sub">${h(W.allPlaced)}</p>`,
          `<span class="sub" style="font-weight:400">${list.length}</span>`)}
        <p class="sub">${h(W.unplacedNote)}</p>
        ${card(h(W.serversNets), Object.keys(st.servers).sort().map(n => { const L = labelsOf(st.servers[n]);
          return `<div class="it" data-ref="server:${h(n)}"><span>${ic("server")}</span><span>${h(n)}<small>${h(L.source === "console" ? W.srcConsole : L.source === "unknown" ? W.srcUnknown : W.srcNode)}</small></span><span>${L.source === "unknown" ? `<span class="sub">${h(W.unknownW)}</span>` : L.labels.length ? L.labels.map(l => `<span class="tag">${h(l)}</span>`).join(" ") : `<span class="sub">${h(W.noLabels)}</span>`}</span></div>`; }).join("") || `<p class="sub">${h(W.noServers)}</p>`)}`;
      el.querySelectorAll(".it[data-ref]").forEach(n => { n.onclick = () => go(n.dataset.ref); });
    }
    // The page's own blocks in a card's general view (addBlock): after the module's, in the order added.
    C.icon = name => ic(name);
    // The page's actions on a kind of object: fn(ref, obj) → [{label, run}], buttons in the card's head.
    C.addAction = (kind, fn) => { (shell.actions = shell.actions || {})[kind] = ((shell.actions || {})[kind] || []).concat([fn]); return C; };   // a named icon's markup, for the page's own rows
    C.addBlock = (kind, b) => { (shell.blocks = shell.blocks || {})[kind] = ((shell.blocks || {})[kind] || []).concat([b]); return C; };
    function pageBlocks(kind, el, ref, obj) {
      for (const b of (shell.blocks || {})[kind] || []) {
        const host = document.createElement("div"); host.className = "pc-block"; host.dataset.block = b.id || ""; el.appendChild(host);
        try { b.render(host, ref, obj); } catch (e) { host.textContent = String(e); }
      }
    }
    // Where the domain is held, and whether this cluster keeps a copy; moving it here when its holder is dead.
    function heldCard() {
      const hd2 = st.held; if (!hd2) return "";
      const r = hd2.holder, b = hd2.backup, here = r && r.holder === hd2.cluster;
      return card(h(cap(W.domainWord)), `<p>${h(W.domPlaced)} ${r ? (here ? `<b>${h(W.thisCluster)}</b> (${h(hd2.cluster)}) · ${h(W.termW)} ${h(r.term)}` : `<b>${h(r.holder)}</b> · ${h(W.termW)} ${h(r.term)}${r.url ? ` · <a href="${h(r.url)}" target="_blank" rel="noopener">${h(r.url)}</a>` : ""}`) : h(W.none)}</p>
        <p class="sub">${h(b ? W.backupKept.replace("{r}", b.pointer && b.pointer.rev).replace("{t}", b.pointer && b.pointer.term) : W.noBackupKept)}</p>
        ${here || !C.may("admin", "domain") ? "" : `<p class="sub">${h(W.moveHelp)}</p><div style="display:flex;justify-content:flex-end"><button type="button" class="btn s" data-a="move">${h(W.move)}</button></div>`}`);
    }
    // A subsystem's tables under a server (the spec's servers.show: [{table, by, title, columns}]): the rows whose `by` is
    // this server, the columns in the subsystem's words — unless the page covers that table with a block of its own
    // (addBlock({covers: "<sub>/<table>"})). The module does not know what the rows are.
    function serverTables(el, server) {
      const covered = new Set(((shell.blocks || {}).server || []).map(b => b.covers).filter(Boolean));
      for (const sub of st.subs) for (const t of ((sub.spec.servers || {}).show || [])) {
        if (!t || !t.table || covered.has(sub.name + "/" + t.table)) continue;
        const host = document.createElement("div"); host.className = "pc-show"; host.dataset.table = sub.name + "/" + t.table; el.appendChild(host);
        const cols = Array.isArray(t.columns) && t.columns.length ? t.columns : ["name"];
        const draw = rows => {
          host.innerHTML = card(h(cap(t.title || t.table)), rows.length ? `<table><tr>${cols.map(c => `<th>${h(fieldTitle(sub, c))}</th>`).join("")}</tr>${rows.map(r => `<tr>${cols.map(c => `<td>${h(isSecret(c) ? (r[c] ? MASK : "") : Array.isArray(r[c]) ? r[c].join(", ") : r[c] ?? "")}</td>`).join("")}</tr>`).join("")}</table>` : `<p class="sub">${h(W.noRows)}</p>`, `<span class="sub" style="font-weight:400">${rows.length}</span>`);
        };
        draw([]);
        getJSON(sub.base + "/" + t.table).then(d => { if (!host.isConnected) return; const all = Array.isArray(d) ? d : d && (d[t.table] || d.rows || d.configured) || []; draw(all.filter(r => String(r[t.by || "server"]) === server)); }).catch(() => {});
      }
    }
    const mc = (l, v) => `<div class="mc"><span>${h(l)}</span><b>${h(v)}</b></div>`;
    const gb = n => n ? (n / 1073741824).toFixed(1) + " " + W.gbW : "—";
    // A server: its resource and what it carries; drain, decommission, its labels; its workers; then the page's.
    function paintServer(el, ref, name) {
      const s = st.servers[name] || {}, workers = s.workers || [], r0 = st.subs[0];
      const held = workers.reduce((k, w) => k + carried(w.worker).length, 0), sp = s.space || {};
      el.innerHTML = `<h1>${h(name)} <small>${h(W.server)}</small></h1>
        ${card(h(W.serverCap), `<span class="bd${s.resource === "live" ? "" : " off"}">${h(W.resourceIs)}: ${h(s.resource || "—")}</span>
          ${st.drain && st.drain.draining === name ? ` <span class="bd off">${h(W.drainingBd)}</span>` : ""}
          ${s.placeable === false ? `<div class="nt err" style="margin-top:10px">${h(W.notPlaceable)}: ${h(s.why || "")}</div>` : ""}
          <div class="mx" style="margin-top:10px">${mc(W.workersN, workers.length)}${mc(r0 ? (display(r0).held || cap(unitWord(r0, true))) : W.units, held)}${sp.total ? mc(W.diskFree, gb(sp.free)) + mc(W.diskTotal, gb(sp.total)) : ""}</div>
          ${s.resource_url || s.build || s.events ? `<div class="g" style="margin-top:10px">${s.resource_url ? fldRo(W.resourceIs, s.resource_url) : ""}${s.build ? fldRo(W.buildW, s.build) : ""}${s.events ? fldRo(W.eventsOnDisk, s.events) : ""}</div>` : ""}
          ${s.resource_heard_at ? `<p class="sub" style="margin-top:8px">${h(W.heard)} ${h(fmt(s.resource_heard_at))}</p>` : ""}`)}
        ${heldCard()}
        <section class="pc-drain"></section><section class="pc-decom"></section><section class="pc-labels"></section>
        ${card(h(W.workersCap), workers.map(w => `<div class="it" data-ref="worker:${h(w.worker)}"><span>${ic("svcs")}</span><span>${h(w.worker)}<small>${h(w.load)}/${h(w.capacity)} · ${h(w.state)}${w.labels ? " · " + h(w.labels) : ""}</small></span>${w.idle_by_policy ? `<span class="bd mu">${h(W.idle)}</span>` : ""}</div>`).join("") || `<p class="sub">${h(W.noWorkers)}</p>`, `<span class="sub" style="font-weight:400">${workers.length}</span>`)}`;
      el.querySelectorAll(".it[data-ref]").forEach(n => { n.onclick = () => go(n.dataset.ref); });
      const mv = el.querySelector('[data-a="move"]');
      if (mv) mv.onclick = async () => {
        if (!C.confirm(W.move + "?", W.moveHelp)) return;
        try { const d = await C.api("POST", "/domain/move", {}); C.toast(d && d.sentence || W.saved); await load(); paintMain(); } catch (e) { C.toast(W.refused + ": " + e.message); }
      };
      paintLabels(el.querySelector(".pc-labels"), name, s);
      paintDrain(el.querySelector(".pc-drain"), name);
      paintDecom(el.querySelector(".pc-decom"), name, s);
      serverTables(el, name);
      pageBlocks("server", el, ref, s);
      tabsOf("server", el, ref, s, { general: W.overview });
    }
    // Labels: the administrator's word for the server (written here) over the node's; both shown when they differ.
    function labelsOf(s) {
      const node = s.labels_node || [...new Set((s.workers || []).flatMap(w => String(w.labels || "").split(",").filter(Boolean)))].sort();
      return { labels: s.labels || node, node, source: s.labels_source || "node" };
    }
    function paintLabels(box, name, s) {
      const L = labelsOf(s), admin = C.may("admin", "server:" + name);
      const draft = st.labelDraft && st.labelDraft.name === name ? st.labelDraft.value : L.labels.join(", ");
      const tags = L.source === "unknown" ? "" : (L.labels.length ? L.labels.map(l => `<span class="pc-tag">${h(l)}</span>`).join(" ") : h(W.noLabels));
      box.innerHTML = `<h2>${h(W.labelsTitle)}</h2><p class="sub">${h(W.labels)}</p><div>${tags}</div>
        <p class="pc-meta">${h(L.source === "console" ? W.labelsConsole : L.source === "unknown" ? W.labelsUnknown : W.labelsNode)}</p>
        ${L.source === "console" && L.node.join(",") !== L.labels.join(",") ? `<p class="pc-meta">${h(W.nodeSays)}: ${h(L.node.join(", ") || W.none)}</p>` : ""}
        ${admin ? `<div class="pc-row"><input class="pc-lab-in" value="${h(draft)}"><button type="button" class="btn s pc-lab-save">${h(W.save)}</button>${L.source === "console" ? `<button type="button" class="btn s pc-lab-back">${h(W.backToNode)}</button>` : ""}</div>` : ""}`;
      if (!admin) return;
      const inp = box.querySelector(".pc-lab-in");
      inp.oninput = () => { st.labelDraft = { name, value: inp.value }; };
      box.querySelector(".pc-lab-save").onclick = async () => {
        const labels = [...new Set(inp.value.split(/[,\s]+/).map(x => x.trim()).filter(Boolean))];
        const here = new Set((s.workers || []).map(w => w.worker)), has = new Set(labels);
        const lose = st.subs.flatMap(sub => (st.units[sub.name] || []).filter(u => u.worker && here.has(u.worker) && (u.labels || []).some(l => !has.has(l))).map(u => label(sub, u)));
        if ((lose.length || !labels.length) && !C.confirm(W.confirmQ, (labels.length ? labels.join(", ") : W.noLabels) + (lose.length ? "\n" + W.labelsLose + ": " + lose.slice(0, 5).join(", ") + (lose.length > 5 ? "…" : "") + "\n" + W.labelsMove : ""))) return;
        try { await C.api("PUT", "/servers/" + encodeURIComponent(name) + "/labels", { labels }); st.labelDraft = null; await load(); paintMain(); C.toast(W.saved); }
        catch (err) { C.toast(W.refused + ": " + err.message); }
      };
      const back = box.querySelector(".pc-lab-back");
      if (back) back.onclick = async () => {
        if (!C.confirm(W.backToNode + "?", L.node.join(", ") || W.none)) return;
        try { await C.api("DELETE", "/servers/" + encodeURIComponent(name) + "/labels"); st.labelDraft = null; await load(); paintMain(); }
        catch (err) { C.toast(W.refused + ": " + err.message); }
      };
    }
    // Drain: the server comes back. One at a time for the cluster.
    function paintDrain(box, name) {
      const d = st.drain || {}, on = d.draining === name, admin = C.may("admin", "server:" + name);
      if (!on) {
        box.innerHTML = `<h2>${h(W.drainTitle)}</h2><p class="pc-meta">${h(W.drainHelp)}</p>${admin ? `<button type="button" class="btn s pc-drain-go" ${d.draining ? "disabled" : ""}>${h(W.drain)}</button>${d.draining ? ` <small>${h(W.otherDraining)}: ${h(d.draining)}</small>` : ""}` : ""}`;
        const go = box.querySelector(".pc-drain-go");
        if (go) go.onclick = async () => {
          if (!C.confirm(W.drain + ": " + name + "?", W.drainHelp)) return;
          try { await C.api("POST", "/drain?server=" + encodeURIComponent(name)); await load(); paintMain(); } catch (err) { C.toast(W.refused + ": " + err.message); }
        };
        return;
      }
      const parts = Object.values(d.subsystems || {}).filter(p => p && p.draining);
      box.innerHTML = `<h2>${h(W.drainTitle)}</h2><p class="sub">${h(W.drainOn)}</p><p class="${d.safe ? "pc-ok" : "pc-bad"}">${h(d.safe ? W.drained : W.draining)}</p>
        ${parts.map(p => `<p class="pc-meta">${h(p.subsystem)}: ${h(p.units ?? 0)}${p.pending ? " · " + h(p.pending) : ""}</p>`).join("")}
        ${admin ? `<button type="button" class="btn s pc-drain-stop">${h(W.undrain)}</button>` : ""}`;
      const stop = box.querySelector(".pc-drain-stop");
      if (stop) stop.onclick = async () => { try { await C.api("DELETE", "/drain"); await load(); paintMain(); } catch (err) { C.toast(W.refused + ": " + err.message); } };
    }
    // Decommission: the server will not come back. Only a silent one; the refusal says why otherwise.
    function paintDecom(box, name, s) {
      if (s.decommissionable === undefined && s.decommission === undefined) { box.innerHTML = ""; return; }
      const d = s.decommission, lost = s.lost || [], admin = C.may("admin", "server:" + name);
      const who = d ? [d.by, fmt(d.at), d.why, d.gone ? W.goneMark : ""].filter(Boolean).join(" · ") : "";
      const canGone = !!s.decommission_may_confirm_gone && admin;
      const goneBox = canGone ? `<label class="pc-gone"><input type="checkbox" class="pc-gone-cb"> ${h(W.gone)}<small>${h(W.goneNote)}</small></label>` : "";
      const back = admin && d ? `<button type="button" class="btn s pc-decom-back">${h(W.decomBack)}</button>` : "";
      if (s.decommissioned) box.innerHTML = `<h2>${h(W.decomTitle)}</h2><p class="pc-bad">${h(W.decomDone)}</p><p class="pc-meta">${h(who)}</p>
        ${lost.length ? `<p class="pc-bad">${h(W.decomLost)}: ${lost.map(x => h(x.place) + (x.worker ? " (" + h(x.worker) + ")" : "")).join(", ")}</p>` : ""}${back}`;
      else if (d) box.innerHTML = `<h2>${h(W.decomTitle)}</h2><p class="pc-bad">${h(W.decomAsked)}</p><p class="pc-meta">${h(who)}</p>
        <p class="${s.decommission_refusal ? "pc-bad" : "pc-meta"}">${h(s.decommission_refusal ? W.decomAnswers + ": " + s.decommission_refusal : W.decomPass)}</p>
        ${canGone && !d.gone ? goneBox + `<button type="button" class="btn s pc-decom-go" disabled>${h(W.decom)}</button>` : ""}${back}`;
      else box.innerHTML = `<h2>${h(W.decomTitle)}</h2><p class="pc-meta">${h(W.decomForever)}</p>
        ${s.door_quiet ? `<p class="pc-bad">${h(W.doorQuiet)}</p>` : ""}
        ${s.decommission_warning ? `<p class="pc-meta">${h(s.decommission_warning)}</p>` : ""}
        ${s.decommissionable && admin ? `<button type="button" class="btn s pc-decom-go">${h(W.decom)}</button>`
          : canGone ? `<p class="pc-meta">${h(s.decommission_refusal || "")}</p>${goneBox}<button type="button" class="btn s pc-decom-go" disabled>${h(W.decom)}</button>`
          : `<p class="pc-meta">${h(W.decomNo)}: ${h(s.decommission_refusal || W.none)}</p>`}`;
      // The only refusal left is the server's door gone quiet: the operator may confirm the machine is gone.
      const cb = box.querySelector(".pc-gone-cb"), go = box.querySelector(".pc-decom-go");
      if (cb && go) cb.onchange = () => { go.disabled = !cb.checked; };
      if (go) go.onclick = async () => {
        const gone = !!(cb && cb.checked);
        if (!C.confirm(W.decom + ": " + name + "?", W.decomForever + (gone ? "\n" + W.goneNote : ""))) return;
        const body = gone ? { why: "", gone: true } : { why: "" };
        try { const out = await C.api("POST", "/servers/" + encodeURIComponent(name) + "/decommission", body); await load(); paintMain(); if (out && out.warning) C.toast(out.warning); }
        catch (err) {
          // a 409 that says only the door is quiet: offer the confirmation where the button was
          if (err.status === 409 && err.body && err.body.may_confirm_gone && !gone) { s.decommission_may_confirm_gone = true; paintDecom(box, name, s); C.toast(err.message); }
          else C.toast(W.refused + ": " + err.message);
        }
      };
      const b = box.querySelector(".pc-decom-back");
      if (b) b.onclick = async () => {
        if (!C.confirm(W.decomBack + ": " + name + "?")) return;
        try { await C.api("DELETE", "/servers/" + encodeURIComponent(name) + "/decommission"); await load(); paintMain(); } catch (err) { C.toast(W.refused + ": " + err.message); }
      };
    }
    function paintWorker(el, ref, name) {
      let info = null, server = null;
      for (const [n, s2] of Object.entries(st.servers)) for (const w of s2.workers || []) if (w.worker === name) { info = w; server = n; }
      const units = carried(name), r0 = st.subs[0];
      if (!info) { el.innerHTML = `<h1>${h(name)}</h1><p class="sub">${h(W.workerSilent)}</p>`; return; }
      el.innerHTML = `<h1>${h(name)} <small>${h(W.worker)}</small></h1>
        ${card(h(cap(W.worker)), `<span class="bd${info.state === "live" ? "" : " off"}">${h(info.state)}</span>
          <div class="mx" style="margin-top:10px">${mc(W.loadW, info.load)}${mc(W.capW, info.capacity)}${mc(W.freeW, Math.max(0, info.capacity - info.load))}</div>
          <div class="g" style="margin-top:10px">${fldRo(cap(W.server), server || "—")}${fldRo(W.labelsW, info.labels || "—")}</div>
          ${info.idle_by_policy ? `<p class="sub">${h(W.idleNote.replace("{p}", (st.policy && st.policy.servers) || ""))}</p>` : ""}
          ${info.server_unsaid ? `<div class="nt err" style="margin-top:8px">${h(W.serverUnsaid)}: ${h(info.server_unsaid)}</div>` : ""}`)}
        ${slotHtml(info)}
        ${card(h(W.holdsW + " " + (r0 ? unitWord(r0, true) : W.units)), units.map(x => `<div class="it" data-ref="${h(unitRef(x.s, x.u.id))}"><span>${decorOf(unitRef(x.s, x.u.id)).iconHtml || ic("x")}</span><span>${h(label(x.s, x.u))}<small>${h(stateOf(x.u)[0])}</small></span>${stateBadge(x.u)}</div>`).join("") || `<p class="sub">${h(W.carriesNone)}</p>`, `<span class="sub" style="font-weight:400">${units.length}</span>`)}`;
      el.querySelectorAll(".it[data-ref]").forEach(n => { n.onclick = () => go(n.dataset.ref); });
      pageBlocks("worker", el, ref, info);
      tabsOf("worker", el, ref, info);
    }
    // -- groups: a value of a list field (display.tree.group_by) as an object ---------------------------------------
    // group:<sub>/<field>/<value>; "" is "without a group". It exists while a unit carries the value — a new group is
    // a unit given a new value. Renaming rewrites the value in that field of every unit carrying it, each through
    // api() (a PUT of the list: sent again, it does the same), and says for which it was not done.
    function parseGroup(ref) {
      const m = /^group:([^/]+)\/([^/]+)\/(.*)$/.exec(String(ref)); if (!m) return null;
      const sub = st.subs.find(x => x.name === m[1]); if (!sub) return null;
      const field = m[2], value = m[3], all = st.units[sub.name] || [], sep = (display(sub).tree || {}).nested_by || "";
      const under = v => v === value || (sep && v.startsWith(value + sep));
      const inIt = all.filter(u => value === "" ? !(Array.isArray(u[field]) && u[field].length) : (u[field] || []).some(under));
      return { sub, field, value, inIt, all, sep, under };
    }
    async function setList(sub, u, field, list) {
      return C.api("PUT", sub.base + "/" + sub.spec.rows + "/" + encodeURIComponent(u.id), { [field]: list });
    }
    function paintGroup(el, ref) {
      const g = parseGroup(ref); if (!g) { el.innerHTML = ""; return; }
      const { sub, field, value, inIt, all } = g, edit = C.may("edit", null) && value !== "", tr = display(sub).tree || {}, sep = g.sep;
      // as the product console's folder: its contents (the groups right under it, then its own units) and the group
      // itself (its path, how many units it holds, renaming); «＋ <unit>» in the head makes one in it
      const own = value === "" ? inIt : inIt.filter(u => (u[field] || []).includes(value));
      const kids = value === "" ? [] : [...new Set([...all.flatMap(u => u[field] || []), ...extraGroups(sub)].filter(v => sep && v.startsWith(value + sep)).map(v => value + sep + v.slice(value.length + sep.length).split(sep)[0]))].sort();
      const under = p => all.filter(u => (u[field] || []).some(v => v === p || (sep && v.startsWith(p + sep)))).length;
      const leaf = value === "" ? cap(tr.no_group || W.noGroup) : (sep ? value.split(sep).pop() : value);
      const word = cap(display(sub).units_count || unitWord(sub, true));
      el.innerHTML = `<h1>${h(leaf)}</h1>${value === "" ? "" : groupBtns(value)}${newBtns(value)}
        ${card(h(value === "" ? cap(unitWord(sub, true)) + " " + (tr.no_group_suffix || W.inNoGroupSuffix) : tr.contents_title || W.groupContents), kids.map(p => `<div class="it" data-ref="group:${h(sub.name)}/${h(field)}/${h(p)}"><span>${ic("folder")}</span><span>${h(sep ? p.split(sep).pop() : p)}<small>${h(cap(tr.group_word || W.group))} · ${under(p)}</small></span></div>`).join("")
          + own.map(u => { const r = unitRef(sub, u.id); return `<div class="it" data-ref="${h(r)}"><span>${decorOf(r).iconHtml || ic("x")}</span><span>${h(label(sub, u))}<small>${h(stateOf(u)[0])}</small></span>${stateBadge(u)}${edit && (u[field] || []).includes(value) ? ` <button type="button" class="btn s" data-out="${h(u.id)}" title="${h(W.removeFrom)}">${h(W.removeShort)}</button>` : ""}</div>`; }).join("")
          || `<p class="sub">${h(W.groupEmpty)}</p>`, `<span class="sub" style="font-weight:400">${inIt.length}</span>`)}
        ${value === "" ? `<p class="sub">${h(W.groupHelp)}</p>` : card(h(cap(tr.group_word || W.group)), `<div class="g">${fldRo(W.pathW, value)}${fldRo(word + " " + W.insideW, inIt.length)}</div>
          <p class="sub">${h(W.unitsIn)}: ${inIt.length} · ${h(W.groupHelp)}</p>${sharedHint(sub, value)}
          ${edit ? `<div class="pc-row"><button type="button" class="btn s" data-a="rename">${h(W.renameGroup)}</button><button type="button" class="btn s" data-a="add">${h(W.addToGroup)}</button></div>` : ""}`)}`;
      el.querySelectorAll(".it[data-ref]").forEach(n => { n.onclick = e => { if (e.target.closest("[data-out]")) return; go(n.dataset.ref); }; });
      wireNew(el);
      pageBlocks("group", el, ref, g);
      el.querySelectorAll("[data-out]").forEach(b => { b.onclick = async () => {
        const u = inIt.find(x => String(x.id) === b.dataset.out); if (!u) return;
        try { await setList(sub, u, field, (u[field] || []).filter(x => x !== value)); await load(); paintMain(); } catch (e) { C.toast(W.refused + ": " + e.message); }
      }; });
      const ren = el.querySelector('[data-a="rename"]');
      if (ren) ren.onclick = async () => {
        const v = await C.dialog(W.renameGroup + ": " + value, [{ name: "to", label: W.newName, value }], W.renameGroup);
        const to = v && v.to.trim(); if (!to || to === value) return;
        const failed = [];
        for (const u of inIt) {
          try { await setList(sub, u, field, [...new Set((u[field] || []).map(x => x === value ? to : g.sep && x.startsWith(value + g.sep) ? to + x.slice(value.length) : x))]); }
          catch (e) { failed.push(label(sub, u) + ": " + e.message); }
        }
        await load();
        C.toast(failed.length ? W.notAll + " " + failed.length + ": " + failed.join("; ") : W.renamed);
        C.select("group:" + sub.name + "/" + field + "/" + (failed.length === inIt.length ? value : to));
      };
      const add = el.querySelector('[data-a="add"]');
      if (add) add.onclick = async () => {
        const out = all.filter(u => !inIt.includes(u));
        const v = await C.dialog(W.addToGroup + ": " + value, [{ name: "id", label: W.pickUnit, options: out.map(u => [String(u.id), label(sub, u)]) }], W.addToGroup);
        const u = v && out.find(x => String(x.id) === v.id); if (!u) return;
        try { await setList(sub, u, field, [...(u[field] || []), value]); await load(); paintMain(); } catch (e) { C.toast(W.refused + ": " + e.message); }
      };
      tabsOf("group", el, ref, g);
    }
    // -- the domain: who holds it, its members, its topology, its alarms, its keys --------------------------
    const domStale = () => !st.dom || st.dom.age == null || st.dom.age > 15;
    const topoNow = () => { const t = (st.dom && st.dom.topology) || {}; return { rev: t.rev || 0, centre: t.centre || "", star: t.star || [], via: t.via || {}, by: t.by || "", at: t.at || 0 }; };
    function memberBadge(m) {
      if (domStale()) return `<span class="bd wait">${h(W.domSilent)}${st.dom && st.dom.age != null ? " " + Math.round(st.dom.age) + " " + W.n.s : ""}</span>`;
      if (m.holder) return `<span class="bd">${h(W.readHere)}</span>`;
      if (m.state === "ok") return `<span class="bd">${h(W.publishes)}</span>`;
      return `<span class="bd off">${h(m.state === "never" ? W.never : W.silentFor + " " + Math.round(m.age || 0) + " " + W.n.s)}</span>`;
    }
    function topoTags(name, short) {
      const t = topoNow(), out = [];
      if (t.centre === name) out.push([W.centre, W.centreTip]);
      if (t.star.includes(name)) out.push([W.starW, W.starTip]);
      if (!short && t.via[name]) out.push([W.via + " " + t.via[name], W.viaTip]);
      return out.map(([a, b]) => `<span class="tag" title="${h(b)}">${h(a)}</span>`).join("");
    }
    function domAgeNote() {
      const v = st.dom; if (!v) return "";
      if (domStale()) return `<div class="nt err">${h(W.domSilentNote.replace("{a}", v.age != null ? Math.round(v.age) + " " + W.n.s : W.longAgo))}</div>`;
      if (v.complete === false) { const down = (v.members || []).filter(m => !m.holder && m.state !== "ok").map(m => m.name); return `<div class="nt err">${h(W.listIncomplete.replace("{m}", down.join(", ")))}</div>`; }
      return "";
    }
    // The domain: its holder in the head; the overview (who knocks, the alarms, the members, the topology, the
    // domain's page), its access, its keys.
    function paintDomain(el, ref) {
      const v = st.dom, admin = C.may("admin", "domain");
      if (!v) { el.innerHTML = `<h1>${h(cap(W.domainWord))}</h1>${card(h(cap(W.domainWord)), `<p class="sub">${h(W.noDomain)}</p>`)}`; return; }
      if (v.term && v.term.deposed) { el.innerHTML = `<h1>${h(cap(W.domainWord))}</h1><div class="pc-general">${termCard(v)}</div>`; wireTerm(el, v); return; }
      if (!domainOnly && st.domShared == null) loadDomShared().then(() => { if (st.sel === "domain") refreshMain(); });
      const list = v.member_list || { rev: 0 }, ms = v.members || [];
      const ks = v.knocking || [], a = st.alarms;
      const skip = ["t", "kind", "subsystem", "unit", "of", "member", "from_history", "class", "ongoing", "last_report", "alive_at", "alive_via"];
      el.innerHTML = `<h1>${h(cap(W.domainWord))}</h1><p class="sub pc-hdsub">${h(W.holderIs)} ${h(v.holder || "—")}; ${h(W.viewAge)} ${v.age != null ? Math.round(v.age) + " " + h(W.n.s) + " " + h(W.ago) : "—"}</p>
        <div class="pc-general">${domAgeNote()}${termCard(v)}
        ${ks.length ? card(h(cap(W.knocking)), ks.map((k, i) => `<div class="it" style="cursor:default"><span>${ic("server")}</span><span>${h(k.name)}<small>${h(W.knockTimes.replace("{n}", k.times).replace("{t}", fmt(k.last)))}${k.fingerprint ? " · " + h(W.fingerprint) + " <b>" + h(k.fingerprint) + "</b>" : ""}</small></span>${admin ? `<button type="button" class="btn s" data-admit="${i}">${h(W.admit)}</button>` : ""}</div>`).join("") + `<p class="sub">${h(W.knockNote)}</p>`) : ""}
        ${a ? card(`${h(cap(W.alarms))} <small class="sub" style="font-weight:400">· ${h(W.alarmsDay)}</small>`, (a.complete ? "" : `<p class="sub" style="color:var(--rd)">${h(a.sentence || "")}</p>`)
          + ((a.events || []).slice(0, 50).map(e => `<div class="it" style="cursor:default"><span>${ic("bell")}</span><span><b title="${h(e.kind)}">${h(kindWord(e))}</b> · ${h(e.of || e.unit || "")}<small>${h(fmt(e.t))} · ${h(e.member)}${eventNote(e) ? " · " + h(eventNote(e)) : ""} · ${h(Object.entries(e).filter(([k]) => !skip.includes(k)).map(([k, x]) => k + "=" + (typeof x === "object" ? JSON.stringify(x) : x)).join(" "))}</small></span></div>`).join("") || `<p class="sub">${h(cap(W.noAlarms))}.</p>`)) : ""}
        ${card(`${h(cap(W.members))} <small class="sub" style="font-weight:400">· ${h(list.rev ? W.byList + " " + list.rev : W.byConfig)}</small>`, ms.map(m => `<div class="it" data-ref="${m.holder ? "" : "member:" + h(m.name)}"><span>${decorOf("member:" + m.name).iconHtml || ic("server")}</span><span>${h(m.name)}${m.holder ? " · " + h(W.holderHere) : ""} ${topoTags(m.name)}<small>${h(m.holder ? W.readHere : m.state === "never" ? W.never : W.lastPub + " " + Math.round(m.age || 0) + " " + W.n.s + " " + W.ago)}</small></span>${memberBadge(m)}</div>`).join(""))}
        ${trustCard(v)}${unitsCard(v)}<div class="pc-shared">${sharedCard()}</div>${editsCard(v)}
        <div class="pc-topo"></div></div>`;
      wireTerm(el, v); wireUnits(el); wireShared(el.querySelector(".pc-shared"));
      el.querySelectorAll(".it[data-ref]").forEach(n => { if (n.dataset.ref) n.onclick = () => go(n.dataset.ref); });
      el.querySelectorAll("[data-admit]").forEach(b2 => { b2.onclick = async () => {
        const k = v.knocking[Number(b2.dataset.admit)];
        if (k.fingerprint && !C.confirm(W.admit + " " + k.name + "?", W.fingerprint + ": " + k.fingerprint + "\n" + W.fpCheck)) return;
        try { await C.api("POST", "/domain/members", k.fingerprint ? { name: k.name, fingerprint: k.fingerprint } : { name: k.name }); await load(); paintMain(); } catch (e) { C.toast(W.refused + ": " + e.message); }
      }; });
      paintTopo(el.querySelector(".pc-topo"));
      pageBlocks("domain", el.querySelector(".pc-general"), ref, v);
      if (v.url && !domainOnly) el.querySelector(".pc-general").insertAdjacentHTML("beforeend", card(h(W.domainPage), `<p class="sub">${h(W.domainPageNote)} <a href="${h(v.url)}" target="_blank" rel="noopener">${h(v.url)}</a></p>`));
      tabsOf("domain", el, ref, v, { general: W.overview, extra: [{ id: "access", label: W.accessTab, render: box => domAccess(box) }, { id: "keys", label: cap(W.keys), render: box => domKeys(box) }] });
    }
    // The holder: where the domain is held and at what term, who keeps its backup, handing it over. A deposed holder
    // says who holds it now and what it alone held after its last copy — each applied again only by a person.
    function termCard(v) {
      const t = v.term; if (!t) return "";
      const admin = C.may("admin", "domain");
      if (t.deposed) {
        const by = t.deposed_by || {}, left = t.stranded || [];
        const what = x => { try { const e = JSON.parse(x.value); return e.what || x.value; } catch (e) { return x.value; } };
        return `<div class="nt err">${h(W.deposedNote.replace("{h}", by.holder || "?").replace("{t}", by.term ?? "?"))} ${by.url ? `<a href="${h(by.url)}" target="_blank" rel="noopener">${h(by.url)}</a>` : ""}</div>`
          + (left.length ? card(h(W.strandedHead.replace("{t}", by.term ?? "?")), `<p class="sub">${h(W.strandedNote)}</p>` + left.map((x, i) => {
            const edit = String(x.path).startsWith("domain/pending/");
            return `<div class="it" style="cursor:default"><span>${ic("bolt")}</span><span>${h(String(x.path).replace("domain/pending/", W.editFor + " "))}<small>${h(what(x))}</small></span>${edit && admin ? `<button type="button" class="btn s" data-reapply="${i}">${h(W.reapplyOn.replace("{h}", by.holder || "?"))}</button>` : `<span class="sub">${h(W.redoOn.replace("{h}", by.holder || "?"))}</span>`}</div>`; }).join(""))
            : `<p class="sub">${h(W.nothingStranded.replace("{t}", by.term ?? "?"))}</p>`);
      }
      const r = t.record || {}, to = t.can_hand_to || [];
      return card(h(W.domTerm), `<div class="g">${fldRo(W.heldOn, r.holder || "—")}${fldRo(cap(W.term), t.term ?? "—")}${fldRo(cap(W.backupAtW), (t.backup_holders || []).join(", ") || W.noBackupYet)}</div>
        ${r.restored_from ? `<p class="sub">${h(W.restoredFrom.replace("{r}", r.restored_rev ?? "?").replace("{f}", r.restored_from))}</p>` : ""}
        ${to.length && admin ? `<div style="display:flex;justify-content:flex-end;margin-top:8px"><button type="button" class="btn s" data-a="handover">${h(W.handOver)}</button></div>` : ""}`);
    }
    function wireTerm(el, v) {
      const t = v.term || {}, by = t.deposed_by || {};
      el.querySelectorAll("[data-reapply]").forEach(b => { b.onclick = async () => {
        const x = (t.stranded || [])[Number(b.dataset.reapply)]; if (!x) return;
        try { await C.api("POST", "/domain/stranded/apply", { path: x.path, key: x.key }); C.toast(W.reapplied + " (" + (by.holder || "") + ")"); } catch (e) { C.toast(W.refused + ": " + e.message); }
      }; });
      const hb = el.querySelector('[data-a="handover"]');
      if (hb) hb.onclick = async () => {
        const c = await C.dialog(W.handOver, [{ name: "to", label: W.handTo, options: (t.can_hand_to || []).map(n => [n, n]), help: W.handNote }], W.handBtn);
        if (!c || !c.to) return;
        C.toast(W.handing.replace("{t}", c.to));
        try { const d = await C.api("POST", "/domain/handover", { to: c.to }); C.toast((d && d.sentence) || W.handed); await load(); paintMain(); } catch (e) { C.toast(W.notHanded + ": " + e.message); }
      };
    }
    // The domain's trust as it stands (fingerprints and revisions only): a member whose revision is below the set's,
    // or who presents another key than the one admitted, has not finished a rotation.
    function trustCard(v) {
      const t = v.trust; if (!t) return "";
      if (!t.installed) return card(h(W.trustW), `<p class="sub">${h(W.notInstalled)}</p>`);
      const ms = Object.entries(t.members || {}).sort(([a], [b]) => a.localeCompare(b));
      const behind = m => (m.keys_rev != null && m.keys_rev < t.rev) || (!!m.presented_key && m.presented_key !== m.admitted_key);
      return card(h(W.trustW), `<div class="g">${fldRo(cap(W.domainWord), t.domain || "—")}${fldRo(W.keysRev, t.rev ?? "—")}${fldRo(W.rootFp, t.root || "—")}${fldRo(W.currentKey, t.current || "—")}
          ${fldRo(W.issuingW, (t.issuing || []).length + ((t.revoked_issuing || []).length ? " · " + W.revokedW + " " + (t.revoked_issuing || []).length : ""))}${fldRo(W.holderKeys, t.holder_has_keys ? W.yesW : W.noW)}</div>
        <div style="margin-top:10px">${ms.map(([n, m]) => `<div class="it" style="cursor:default"><span>${ic("server")}</span><span>${h(n)}<small>${h(W.admittedKey)} ${h(m.admitted_key || "—")} · ${h(W.presentedKey)} ${h(m.presented_key || "—")} · ${h(W.holdsRev)} ${h(m.keys_rev ?? "—")}</small></span>${behind(m) ? `<span class="bd off">${h(W.rotating)}</span>` : ""}</div>`).join("")}</div>
        ${ms.some(([, m]) => behind(m)) ? `<p class="sub">${h(W.rotationNote)}</p>` : ""}`);
    }
    // The units each subsystem has on the domain (the view's units, by the specs' domain.ref and domain.view): the
    // ref, the cluster, where it runs, its state; a yes/no field the spec's domain.edit names is switched here.
    const U_STATE = () => ({ live: [W.uLive, ""], stale: [W.uStale, "wait"], configured: [W.uConfigured, "wait"], silent: [W.uSilent, "off"] });
    function unitsCard(v) {
      const all = Object.entries(v.units || {}); if (!all.length && !v.units) return "";
      const S = U_STATE();
      return card(h(W.domUnits), `<p class="sub">${h(W.domUnitsNote)}</p>` + (all.map(([name, list]) => {
        const sub = st.subs.find(x => x.name === name), title = sub ? cap(unitWord(sub, true)) : name;
        const edit = sub ? (((sub.spec.domain || {}).edit) || []).filter(f => ((sub.spec.fields || []).find(x => x.name === f) || {}).type === "bool") : [];
        return `<div class="pc-g" style="margin-top:10px">${h(title)} <span class="sub">${(list || []).length}</span></div>` + ((list || []).map(u => {
          const [w, c] = S[u.state] || [u.state || "—", ""], vw = u.view || {};
          const vals = Object.entries(vw).map(([k, x]) => (sub ? fieldTitle(sub, k) : k) + ": " + (typeof x === "object" ? JSON.stringify(x) : x)).join(" · ");
          const may = sub && C.may("edit", "unit:" + name + "/" + u.ref);
          const btns = edit.filter(f => typeof vw[f] === "boolean" && may && u.ref).map(f => `<button type="button" class="btn s" data-uedit="${h(JSON.stringify([name, u.ref, f, !vw[f]]))}">${h(vw[f] ? W.turnOff : W.turnOn)}${edit.length > 1 ? " · " + h(fieldTitle(sub, f)) : ""}</button>`).join("");
          return `<div class="it" style="cursor:default"><span>${ic("x")}</span><span>${h(u.ref || "—")}<small>${h(u.cluster)}${u.worker ? " · " + h(u.worker) : ""}${u.server ? " · " + h(u.server) : ""}${u.phase ? " · " + h(u.phase) : ""}${u.age != null ? " · " + h(Math.round(u.age)) + " " + h(W.n.s) : ""}${vals ? " · " + h(vals) : ""}</small></span><span style="display:flex;gap:6px;align-items:center">${btns}<span class="bd${c ? " " + c : ""}">${h(w)}</span></span></div>`;
        }).join("") || `<p class="sub">${h(W.none)}</p>`);
      }).join("") || `<p class="sub">${h(W.noUnitsDecl)}</p>`));
    }
    function wireUnits(el) {
      el.querySelectorAll("[data-uedit]").forEach(b => { b.onclick = async () => {
        const [name, ref, f, to] = JSON.parse(b.dataset.uedit), sub = st.subs.find(x => x.name === name); if (!sub) return;
        try { await C.api("PUT", "/domain/" + encodeURIComponent(name) + "/" + encodeURIComponent(sub.spec.rows) + "/" + encodeURIComponent(ref), { [f]: to }); C.toast(W.saved); await load(); } catch (e) { C.toast(W.refused + ": " + e.message); }
      }; });
    }
    // The domain's shared settings: the fields each spec shares with the domain (declared: domain.shared with their
    // types) — a list one value a line, a number, a yes/no; empty takes the domain's value away (null).
    function sharedCard() {
      const sh = st.domShared; if (!sh) return "";
      if (sh.error) return card(h(W.sharedW), `<p class="sub">${h(W.noShared)}</p>`);
      const d = sh.doc || {}, dl = sh.delivery || {}, dec = sh.declared || {}, admin = C.may("admin", "domain");
      const bad = (dl.silent || []).length || Object.keys(dl.refused || {}).length || Object.keys(dl.behind || {}).length;
      const input = (sub, f) => {
        const v = ((d.shared || {})[sub] || {})[f.name], nm = h(sub + "/" + f.name), dis = admin ? "" : " disabled";
        if (f.type === "list") { const t = Array.isArray(v) ? v.join("\n") : ""; return `<textarea rows="4" data-sh="${nm}" data-orig="${h(t)}"${dis}>${h(t)}</textarea>`; }
        if (f.type === "bool") { const t = v == null ? "" : String(v); return `<select data-sh="${nm}" data-orig="${h(t)}"${dis}>${[["", W.notSetW], ["true", W.yesW], ["false", W.noW]].map(([x, l]) => `<option value="${x}"${t === x ? " selected" : ""}>${h(l)}</option>`).join("")}</select>`; }
        const t = v == null ? "" : String(v); return `<input ${f.type === "int" || f.type === "float" ? 'type="number"' : 'type="text"'} data-sh="${nm}" data-orig="${h(t)}" value="${h(t)}"${dis}>`;
      };
      return card(h(W.sharedW), `<p class="sub">${h(W.sharedNote)}</p><p class="sub">${d.rev ? h(W.sharedRev.replace("{r}", d.rev).replace("{t}", d.term ?? "—").replace("{a}", fmt(d.at))) + (d.by ? " · " + h(d.by) : "") : h(W.neverPub)}</p>
        ${d.rev ? `<div class="nt${bad ? " err" : ""}" style="margin-top:8px">${h(dl.sentence || "")}${Object.entries(dl.refused || {}).map(([m, w]) => `<br>${h(m)}: ${h(w)}`).join("")}</div>` : ""}
        ${Object.entries(dec).map(([sub, fields]) => { const s2 = st.subs.find(x => x.name === sub);
          return `<div class="pc-g" style="margin-top:10px">${h(s2 ? cap(display(s2).section || s2.name) : sub)}</div><div class="g">${(fields || []).map(f => `<div><label>${h(s2 ? fieldTitle(s2, f.name) : f.name)}${f.type === "list" ? " — " + h(W.onePerLine) : ""}</label>${input(sub, f)}</div>`).join("")}</div>`; }).join("") || `<p class="sub">${h(W.noSharedDecl)}</p>`}
        ${st.sharedErr ? `<div class="nt err" style="margin-top:8px">${h(st.sharedErr)}</div>` : ""}
        ${admin && Object.keys(dec).length ? `<div style="display:flex;justify-content:flex-end;margin-top:8px"><button type="button" class="btn pri s" data-a="publish">${h(W.publishW)}</button></div>` : ""}`);
    }
    function wireShared(box) {
      const b = box && box.querySelector('[data-a="publish"]'); if (!b) return;
      b.onclick = async () => {
        const sh = st.domShared || {}, dec = sh.declared || {}, shared = {};
        for (const [sub, fields] of Object.entries(dec)) {
          shared[sub] = {};
          for (const f of fields || []) {
            const x = [...box.querySelectorAll("[data-sh]")].find(y => y.dataset.sh === sub + "/" + f.name); if (!x) continue;
            const raw = x.value, lines = raw.split("\n").map(y => y.trim()).filter(Boolean);
            shared[sub][f.name] = f.type === "list" ? (lines.length ? lines : null) : f.type === "bool" ? (raw === "" ? null : raw === "true")
              : f.type === "int" || f.type === "float" ? (raw === "" ? null : Number(raw)) : (raw === "" ? null : raw);
          }
        }
        try { const d = await C.api("PUT", "/domain/shared", { base_rev: Number((sh.doc || {}).rev) || 0, shared }); st.sharedErr = ""; C.toast(W.publishedRev.replace("{r}", d && d.rev)); }
        catch (e) { st.sharedErr = e.message; }
        box.querySelectorAll("[data-sh]").forEach(x => { x.dataset.orig = x.value; });
        await loadDomShared(); box.innerHTML = sharedCard(); wireShared(box);
      };
    }
    // The edits the domain keeps for its clusters: waiting for the cluster's next publication, or applied there.
    function editsCard(v) {
      if (!v.pending && !v.outcomes) return "";
      const rows = [];
      for (const [c, list] of Object.entries(v.pending || {})) for (const e of list || []) rows.push(`<div class="it" style="cursor:default"><span>${ic("server")}</span><span>${h(c)} · ${h(e.what || e.id || "")}<small>${h(W.takenAt)} ${h(fmt(e.at))}</small></span><span class="bd wait">${h(W.waitsPub)}</span></div>`);
      for (const [c, list] of Object.entries(v.outcomes || {})) for (const o of list || []) { const ok = o.status >= 200 && o.status < 300;
        rows.push(`<div class="it" style="cursor:default"><span>${ic("server")}</span><span>${h(c)} · ${h(o.what || o.id || "")}<small>${h(W.appliedAt)} ${h(fmt(o.at))}${o.error ? " · " + h(o.error) : ""}</small></span><span class="bd${ok ? "" : " off"}">${h(ok ? W.appliedW : W.refusedStatus.replace("{s}", o.status))}</span></div>`); }
      return card(h(W.editsW), `<p class="sub">${h(W.editsNote)}</p>` + (rows.join("") || `<p class="sub">${h(W.noEdits)}</p>`));
    }
    // The domain's access at a glance: its people and the clusters they have grants on; each opens in «Rights».
    async function domAccess(box) {
      if (!st.acc) { box.innerHTML = card(h(W.loading), ""); await loadAccess(); if (!box.isConnected) return; }
      const a = st.acc; if (!a) { box.innerHTML = card(h(W.refused), ""); return; }
      box.innerHTML = card(`${h(cap(W.people))} <small class="sub" style="font-weight:400">· ${a.users.length}</small>`, a.users.map(u => `<div class="it" data-ref="person:${h(u.name)}"><span>${ic("user")}</span><span>${h(u.name)}</span>${u.disabled ? `<span class="bd off">${h(W.disabledW)}</span>` : ""}</div>`).join(""))
        + card(h(cap(W.clusters)), accClusters().map(c => `<div class="it" data-ref="grants:${h(c)}"><span>${ic(c === "domain" ? "domain" : "server")}</span><span>${h(c === "domain" ? W.domainWord : c)}</span></div>`).join(""));
      box.querySelectorAll("[data-ref]").forEach(n => { n.onclick = () => { if (sectionList().some(s => s.id === "access")) { st.section = "access"; paintRail(); paintAside(); } C.select(n.dataset.ref); }; });
    }
    // The domain's keys: what the holder keeps under domain/, by family — the module names the platform's; a
    // subsystem's are its spec's part of the domain (domain.keys, their words display.keys); a key no family claims
    // is under «other keys». Read only.
    const KEY_FAMILIES = [
      { id: "members", keys: ["domain/members"], title: W.kfMembers, about: W.kfMembersAbout, absent: W.kfMembersAbsent },
      { id: "published", prefix: "domain/members/", title: W.kfPublished, about: W.kfPublishedAbout },
      { id: "reaches", keys: ["domain/reaches"], title: W.kfReaches, about: W.kfReachesAbout },
      { id: "topology", keys: ["domain/topology"], title: cap(W.topology), about: W.kfTopologyAbout },
      { id: "pending", prefix: "domain/pending/", title: W.kfPending, about: W.kfPendingAbout },
      { id: "outcomes", keys: ["domain/outcomes"], prefix: "domain/outcomes/", title: W.kfOutcomes, about: W.kfOutcomesAbout },
      { id: "view", keys: ["domain/view"], title: W.kfView, about: W.kfViewAbout },
    ];
    const keyFamilies = () => {
      const fromSpecs = st.subs.flatMap(s => ((s.spec.domain || {}).keys || []).map(f => ({ ...f, ...(((display(s).keys || {})[f.id]) || {}) })));
      const own = KEY_FAMILIES.filter(f => f.id !== "view"), view = KEY_FAMILIES.filter(f => f.id === "view");
      return [...own, ...fromSpecs, ...view];
    };
    const pretty = v => { if (typeof v !== "string") return JSON.stringify(v, null, 2); const t = v.trim(); if (t.startsWith("{") || t.startsWith("[")) { try { return JSON.stringify(JSON.parse(t), null, 2); } catch (e) { /* as it is */ } } return v; };
    async function domKeys(box) {
      box.innerHTML = card(h(W.loading), `<p class="sub">${h(W.keysAsking)}</p>`);
      let d; try { d = await getJSON("/domain/keys"); st.keys = d; } catch (e) { d = { error: e.message }; }
      if (!box.isConnected) return;
      if (d.error && !(d.vars || []).length && !(d.objects || []).length) { box.innerHTML = card(h(W.keysFailed), `<div class="nt err">${h(d.error)}</div>`); return; }
      const FAMS = keyFamilies(), famOf = k => (FAMS.find(f => (f.keys || []).includes(k) || (f.prefix && k.startsWith(f.prefix))) || { id: "other" }).id;
      const kb = n => n < 1024 ? n + " " + W.bW : (n / 1024).toFixed(1) + " " + W.kbW;
      const rows = [...(d.vars || []).map(v => { const items = Object.entries(v.items || {}).sort(([x], [y]) => x.localeCompare(y)), text = items.map(([, x]) => pretty(x)).join("\n");
          return { key: v.key, html: `<details class="dk-key"${text.length < 1500 ? " open" : ""}><summary><code>${h(v.key)}</code> <span class="sub">${h(W.kVar)} · ${h(W.kItems)}: ${items.length} · ${h(W.kIndex)} ${h(v.index || "—")}</span></summary>${items.length ? items.map(([k, x]) => `<div class="dk-item"><code>${h(k)}</code><pre class="dk-pre">${h(pretty(x))}</pre></div>`).join("") : `<p class="sub dk-item">${h(W.kEmpty)}</p>`}</details>` }; }),
        ...(d.objects || []).map(o => ({ key: o.key, html: `<details class="dk-key"${pretty(o.body).length < 1500 ? " open" : ""}><summary><code>${h(o.key)}</code> <span class="sub">${h(W.kObj)} · ${kb(o.size || 0)}${o.age != null ? " · " + h(o.age) + " " + h(W.n.s) + " " + h(W.ago) : ""}</span></summary><pre class="dk-pre" style="margin-left:14px">${h(pretty(o.body))}</pre></details>` }))];
      const fams = [...FAMS, { id: "other", title: W.kfOther, about: W.kfOtherAbout }].map(f => ({ ...f, rows: rows.filter(r => famOf(r.key) === f.id).sort((x, y) => x.key.localeCompare(y.key)) }));
      const shown = fams.filter(f => f.rows.length || f.absent), empty = fams.filter(f => !f.rows.length && !f.absent && f.id !== "other");
      box.innerHTML = `<p class="sub" style="margin:0 0 10px">${h(W.keysIntro)}</p>${d.error ? `<div class="nt err" style="margin-bottom:10px">${h(d.error)}</div>` : ""}
        <div class="dk-idx">${shown.map(f => `<button type="button" data-fam="${h(f.id)}">${h(f.title)}<small>${f.rows.length}</small></button>`).join("")}</div>
        ${shown.map(f => `<div id="pc-dk-${h(f.id)}">${card(`${h(f.title)} <small class="sub" style="font-weight:400">· ${f.rows.length ? f.rows.length + " " + h(W.kKeys) : h(W.kNone)}</small>`, `<p class="sub" style="margin:0 0 6px">${h(f.about || "")}</p>${f.rows.length ? f.rows.map(r => r.html).join("") : `<div class="nt dk-absent">${h(f.absent)}</div>`}`)}</div>`).join("")}
        ${empty.length ? `<p class="sub">${h(W.kNowEmpty)}: ${empty.map(f => h(f.title)).join(", ")}.</p>` : ""}`;
      box.querySelectorAll("[data-fam]").forEach(b => { b.onclick = () => { const t = box.querySelector("#pc-dk-" + b.dataset.fam); if (t && t.scrollIntoView) t.scrollIntoView({ block: "start" }); }; });
    }
    // Topology: the centre, the star relays (dialled from nowhere: they take their streams from the centre), and
    // through whom each member goes to the domain. A draft until written; the write names the revision it read.
    function paintTopo(box) {
      if (!box) return;
      const cur = st.topo || topoNow(), base = topoNow(), all = (st.dom.members || []), others = all.filter(m => !m.holder), admin = C.may("admin", "domain");
      const opt = (v2, c2, l) => `<option value="${h(v2)}" ${v2 === c2 ? "selected" : ""}>${h(l)}</option>`;
      const dis = admin ? "" : " disabled";
      box.innerHTML = card(h(cap(W.topology)), `<div class="g"><div><label>${h(cap(W.centre))}</label><select data-t="centre"${dis}>${opt("", cur.centre, W.none2)}${all.map(m => opt(m.name, cur.centre, m.name)).join("")}</select></div>
          ${fldRo(cap(W.rev), base.rev ? base.rev + (base.at ? " · " + fmt(base.at) : "") + (base.by ? " · " + base.by : "") : W.notWritten)}</div>
        <div style="margin-top:10px">${others.map(m => `<div class="it" style="cursor:default"><span>${decorOf("member:" + m.name).iconHtml || ic("server")}</span><span>${h(m.name)}<small>${m.reaches && m.reaches.length ? h(W.reaches) + " " + h(m.reaches.join(", ")) : h(W.noReaches)}</small></span>
          <span style="display:flex;gap:8px;align-items:center"><label class="sub" title="${h(W.starTip)}" style="white-space:nowrap"><input type="checkbox" data-tstar="${h(m.name)}" ${cur.star.includes(m.name) ? "checked" : ""}${cur.centre === m.name ? " disabled" : dis}> ${h(W.starW)}</label>
          <select style="width:170px" data-via="${h(m.name)}" title="${h(W.viaTip)}"${dis}>${opt("", cur.via[m.name] || "", W.direct)}${others.filter(o => o.name !== m.name && !cur.via[o.name]).map(o => opt(o.name, cur.via[m.name] || "", W.via + " " + o.name)).join("")}</select></span></div>`).join("") || `<p class="sub">${h(W.noOthers)}</p>`}</div>
        ${st.topoErr ? `<div class="nt err" style="margin-top:8px">${h(st.topoErr)}</div>` : ""}
        <p class="sub">${h(cap(W.topoHelp))}.</p>
        ${admin ? `<div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px"><button type="button" class="btn s" data-t="undo"${st.topo ? "" : " disabled"}>${h(W.cancel2)}</button><button type="button" class="btn pri s" data-t="save"${st.topo ? "" : " disabled"}>${h(W.writeW)}</button></div>` : ""}`);
      const draft = () => (st.topo = st.topo || JSON.parse(JSON.stringify(topoNow())));
      const sel = box.querySelector('[data-t="centre"]');
      sel.onchange = () => { const t = draft(); t.centre = sel.value; t.star = t.star.filter(x => x !== sel.value); paintTopo(box); };
      box.querySelectorAll("[data-tstar]").forEach(c => { c.onchange = () => { const t = draft(), n = c.dataset.tstar; t.star = c.checked ? [...new Set([...t.star, n])] : t.star.filter(x => x !== n); paintTopo(box); }; });
      box.querySelectorAll("[data-via]").forEach(c => { c.onchange = () => { const t = draft(); if (c.value) t.via[c.dataset.via] = c.value; else delete t.via[c.dataset.via]; paintTopo(box); }; });
      const undo = box.querySelector('[data-t="undo"]'); if (undo) undo.onclick = () => { st.topo = null; st.topoErr = ""; paintTopo(box); };
      const save = box.querySelector('[data-t="save"]');
      if (save) save.onclick = async () => {
        const t = st.topo; if (!t) return;
        try { const d = await C.api("PUT", "/domain/topology", { base_rev: base.rev, centre: t.centre || "", star: t.star, via: t.via }); st.topo = null; st.topoErr = ""; C.toast(W.saved + (d && d.rev ? " · " + W.rev + " " + d.rev : "")); await load(); paintMain(); }
        catch (e) { st.topoErr = e.message; paintTopo(box); }
      };
    }
    // A member of the domain: how it reaches the domain, what it sees, when it last published; taking it out.
    function paintMember(el, ref, name) {
      const m = ((st.dom && st.dom.members) || []).find(x => x.name === name) || { name };
      const t = topoNow(), via = t.via[name], admin = C.may("admin", "domain"), behind = ((st.dom && st.dom.members) || []).filter(x => t.via[x.name] === name).map(x => x.name);
      const lm = ((st.dom && st.dom.member_list) || {}).members || {}, how = lm[name];
      el.innerHTML = `<h1>${h(name)}</h1><p class="sub pc-hdsub">${h(decorTitle("member:" + name) || W.memberSub)}</p><div class="pc-general">${domAgeNote()}
        ${card(h(W.clusterW), `${memberBadge(m)}<div class="g" style="margin-top:10px">${fldRo(W.toDomain, via ? W.via + " " + via : W.direct)}${fldRo(W.seesNets, (m.reaches || []).join(", ") || W.noReaches)}
          ${behind.length ? fldRo(W.relayFor, behind.join(", ")) : ""}${fldRo(cap(W.lastPub), m.state === "never" ? W.never : Math.round(m.age || 0) + " " + W.n.s + " " + W.ago)}
          ${fldRo(cap(W.skew), m.state === "never" || m.skew == null ? "—" : (m.skew >= 0 ? W.behindBy : W.aheadBy) + " " + Math.abs(m.skew) + " " + W.n.s)}</div>
          ${m.error ? `<div class="nt err" style="margin-top:8px">${h(m.error)}</div>` : ""}<p class="sub">${h(W.memberNote)}</p>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px"><span class="sub">${h(how ? W.inDomain + " " + (how.how || "") + (how.since ? " · " + fmt(how.since) : "") : W.byConfigShort)}</span>
          ${admin && !m.holder ? `<button type="button" class="btn s" data-a="leave">${h(W.leave)}</button>` : ""}</div>`)}</div>`;
      const lv = el.querySelector('[data-a="leave"]');
      if (lv) lv.onclick = async () => {
        if (!C.confirm(W.leave + ": " + name + "?", W.leaveHelp)) return;
        try { await C.api("DELETE", "/domain/members/" + encodeURIComponent(name)); st.sel = "domain"; await load(); paintMain(); } catch (e) { C.toast(W.refused + ": " + e.message); }
      };
      pageBlocks("member", el.querySelector(".pc-general"), ref, m);
      tabsOf("member", el, ref, m);
    }
    // the title the page's decoration gives an object (a kind of server, say) — a card's subtitle
    function decorTitle(ref) {
      const kind = String(ref).split(":")[0];
      for (const fn of (shell.decor || {})[kind] || []) { try { const d = fn(ref, objectOf(ref)) || {}; if (d.title) return d.title; } catch (e) { /* none */ } }
      return "";
    }
    // -- access: the domain's people, their grants on each cluster and on the domain, break-glass ---------------
    // People live at the domain holder; grants on each cluster (and on the domain itself), carried there by its agent.
    async function loadAccess() {
      try {
        const [u, g, bg] = await Promise.all([getJSON("/domain/users"), getJSON("/domain/grants"), getJSON("/domain/break-glass")]);
        st.acc = { users: u.users || [], grants: g.grants || {}, glass: bg.clusters || {}, err: "" };
      } catch (e) { st.acc = { users: [], grants: {}, glass: {}, err: e.message }; }
      if (st.section === "access") { paintTree(); paintMain(); }
      emit("refresh", { access: st.acc });
    }
    const accClusters = () => [...new Set(["domain", ...Object.keys((st.acc && st.acc.grants) || {}), ...Object.keys((st.acc && st.acc.glass) || {})])].sort((a, b) => a === "domain" ? -1 : b === "domain" ? 1 : a.localeCompare(b));
    const capWord = c => ({ view: W.view, edit: W.edit, admin: W.admin })[c] || c;
    // A scope is "*", "labels:a,b", or "<kind>:<id>" for one unit (the kind is the grant's, not a word of the module).
    const scopeWord = sc => sc === "*" ? W.allUnits : sc.startsWith("labels:") ? W.byLabels + " " + sc.slice(7) : /^[a-z]+:/.test(sc) ? W.oneUnit + " " + sc.replace(/^[a-z]+:/, "") : sc;
    async function accDo(method, path, body) { try { await C.api(method, path, body); C.toast(W.saved); } catch (e) { C.toast(W.refused + ": " + e.message); } await loadAccess(); }
    function paintPerson(el, ref, name) {
      const a = st.acc || { users: [], grants: {} }, u = a.users.find(x => x.name === name) || { name };
      const lines = accClusters().flatMap(c => (a.grants[c] || []).map((l, i) => ({ c, l, i })).filter(x => x.l.subject === name));
      const admin = C.may("admin", "domain");
      el.innerHTML = `<h1>${h(name)} ${u.disabled ? `<small class="pc-bad">${h(W.disabledW)}</small>` : ""}</h1>
        <p class="pc-meta">${h(u.how === "oidc" ? W.howOidc : W.howPass)}${u.by ? " · " + h(W.by) + " " + h(u.by) : ""}</p>
        ${admin ? `<div class="pc-row">${u.how === "password" ? `<button type="button" data-a="pass">${h(W.setPass)}</button>` : ""}<button type="button" data-a="toggle">${h(u.disabled ? W.on : W.off)}</button><button type="button" data-a="del">${h(W.del)}</button></div>` : ""}
        <ul>${lines.map(x => `<li>${h(x.c === "domain" ? W.domainWord : x.c)} · ${h(capWord(x.l.cap))} · ${h(scopeWord(x.l.scope))}</li>`).join("") || `<li>${h(W.noGrants)}</li>`}</ul>`;
      const on = (a2, fn) => { const b2 = el.querySelector(`[data-a="${a2}"]`); if (b2) b2.onclick = fn; };
      on("pass", async () => { const v = await C.dialog(W.setPass + ": " + name, [{ name: "password", label: W.pass10, type: "password" }], W.save); if (v) accDo("PUT", "/domain/users/" + encodeURIComponent(name), { password: v.password }); });
      on("toggle", () => accDo("PUT", "/domain/users/" + encodeURIComponent(name), { disabled: !u.disabled }));
      on("del", () => { if (C.confirm(W.del + " " + name + "?", W.deletePerson)) { st.sel = null; accDo("DELETE", "/domain/users/" + encodeURIComponent(name)); } });
      tabsOf("person", el, ref, u);
    }
    function paintGrants(el, ref, cluster) {
      const a = st.acc || { users: [], grants: {}, glass: {} }, lines = a.grants[cluster] || [], admin = C.may("admin", "domain");
      const glass = a.glass[cluster];
      el.innerHTML = `<h1>${h(cluster === "domain" ? W.domainWord : cluster)}</h1>
        ${a.err ? `<p class="pc-bad">${h(a.err)}</p>` : ""}
        <ul>${lines.map((l, i) => `<li>${h(l.subject)} · ${h(capWord(l.cap))} · ${h(scopeWord(l.scope))}${admin ? ` <button type="button" data-rev="${i}">${h(W.revoke)}</button>` : ""}</li>`).join("") || `<li>${h(W.noGrants)}</li>`}</ul>
        ${admin ? `<div class="pc-row"><button type="button" data-a="grant">${h(W.grant)}</button>${cluster === "domain" ? "" : `<button type="button" data-a="glass">${h(W.glass)}</button>`}</div>` : ""}
        ${cluster === "domain" ? "" : `<p class="pc-meta">${h(glass ? W.glassSet + " " + fmt(glass.set_at) : W.glassNone)}</p>`}
        <p class="pc-meta">${h(W.grantNote)}</p>`;
      el.querySelectorAll("[data-rev]").forEach(b2 => { b2.onclick = () => {
        const i = Number(b2.dataset.rev); if (!C.confirm(W.revoke + ": " + lines[i].subject + " · " + cluster + "?")) return;
        accDo("PUT", "/domain/grants/" + encodeURIComponent(cluster), { lines: lines.filter((_, j) => j !== i) });
      }; });
      const g = el.querySelector('[data-a="grant"]');
      if (g) g.onclick = async () => {
        const v = await C.dialog(W.grant + ": " + (cluster === "domain" ? W.domainWord : cluster), [
          { name: "subject", label: W.who, options: a.users.filter(u => !u.disabled).map(u => [u.name, u.name]) },
          { name: "cap", label: W.what, options: [["view", W.view], ["edit", W.edit], ["admin", W.admin]] },
          { name: "scope", label: W.onWhat, value: "*", help: W.scopeHelp }], W.grant);
        if (v) accDo("PUT", "/domain/grants/" + encodeURIComponent(cluster), { lines: [...lines, { subject: v.subject, cap: v.cap, scope: (v.scope || "").trim() || "*" }] });
      };
      const gl = el.querySelector('[data-a="glass"]');
      if (gl) gl.onclick = async () => { const v = await C.dialog(W.glass + ": " + cluster, [{ name: "password", label: W.pass12, type: "password", help: W.glassNote }], W.save); if (v) accDo("PUT", "/domain/break-glass/" + encodeURIComponent(cluster), { password: v.password }); };
      tabsOf("grants", el, ref, { cluster, lines });
    }
    // The worker's slot — diagnostics only: the operator acts on servers, the controller on slots.
    // A worker's slot, for diagnosis (the operator decommissions SERVERS; workers are the controller's): released or
    // not, the lease's end, the volumes its process holds, hung or of unknown life — and a name another process holds.
    const fmtDay = t => t ? new Date(t * 1000).toLocaleString(W === WORDS.ru ? "ru-RU" : undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }) : "—";
    function slotHtml(w) {
      const c = w.name_conflict;
      const conflict = c ? `<div class="nt err" style="margin-top:8px">${h(W.conflictHead.replace("{h}", c.holder || "—"))}${c.holder_box ? " " + h(W.onMachine) + " " + h(c.holder_box) : ""}.${(c.contenders || []).map(x => `<br>· ${h(x.state === "nameless" ? W.slotNameless : x.state === "refused" ? W.slotRefused : x.state || "")} — ${h(x.hostname || x.box || "?")}${x.server ? " (" + h(x.server) + ")" : ""}${x.for_s != null ? ", " + h(W.alreadyW) + " " + h(dur(x.for_s)) : ""}`).join("")}<br>${h(W.nameAdvice2)}</div>` : "";
      if (w.released === undefined && w.hung === undefined && !w.presence_unknown) return conflict ? card(h(W.slotTitle), conflict) : "";
      const since = w.hung_since ? " " + W.sinceW + " " + fmtDay(w.hung_since) : "";
      return card(h(W.slotTitle), `${w.released ? `<span class="bd off">${h(W.slotReleased)}</span>` : w.hung ? `<span class="bd off">${h(W.slotHung)}</span>` : w.presence_unknown ? `<span class="bd off">${h(W.slotUnknown)}</span>` : ""}
        <div class="g" style="margin-top:8px">${fldRo(W.leaseTill, w.slot_garbled ? W.leaseGarbled : w.slot_until == null ? "—" : fmtDay(w.slot_until))}${fldRo(W.volumesW, (w.holds || []).join(", ") || "—")}</div>
        ${w.hung ? `<div class="nt err" style="margin-top:8px">${h(W.hungNote.replace("{s}", since))}</div>` : ""}
        ${w.presence_unknown && !w.hung ? `<div class="nt err" style="margin-top:8px">${h(W.unknownNote.replace("{s}", since).replace("{p}", w.presence_unknown))}</div>` : ""}
        ${w.slot_garbled ? `<div class="nt err" style="margin-top:8px">${h(W.garbledNote)}</div>` : ""}
        ${conflict}
        ${w.released ? `<p class="sub" style="margin-top:8px">${h(W.releasedNote)}</p>` : ""}
        <p class="sub" style="margin-top:8px">${h(W.workersOutNote)}</p>`);
    }
    async function paintJournal(el) {
      el.innerHTML = `<h1>${h(W.journal)}</h1><ul class="pc-evlist"></ul>`;
      const now = Date.now() / 1000;
      try {
        const d = await getJSON(`/events?from=${now - 86400}&to=${now}`);
        const list = (Array.isArray(d) ? d : d.events || []).slice(-200).reverse();
        el.querySelector(".pc-evlist").innerHTML = list.map(e => `<li><span title="${h(e.kind)}">${h(fmt(e.t || e.ts))} <strong>${h(kindWord(e))}</strong></span> <small>${h(e.unit)}${e.of && e.of !== e.unit ? " · " + h(e.of) : ""}${eventNote(e) ? " · " + h(eventNote(e)) : ""}</small></li>`).join("") || `<li>${h(W.noEvents)}</li>`;
      } catch (e) { el.querySelector(".pc-evlist").innerHTML = `<li class="bad">${h(e.message)}</li>`; }
    }

    // -- the session -------------------------------------------------------------------------------------------
    function showLogin(why) {
      const url = st.session && st.session.login_url;
      $(".pc-login-w").textContent = url ? W.loginAt + url : W.noHolder;
      $(".pc-login-e").textContent = why || W.needLogin; show($(".pc-login"), true);
      setTimeout(() => { const f = root.querySelector(glassMode ? ".pc-glass-f input" : ".pc-login-f input"); if (f) f.focus(); }, 50);
    }
    $(".pc-login-f").onsubmit = async e => {
      e.preventDefault();
      const f = e.target, url = st.session && st.session.login_url;
      try {
        if (!url) throw new Error("no login door");
        const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user: f.elements.user.value.trim(), password: f.elements.password.value }) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.detail || d.error || String(r.status));
        const s = await fetch("/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: d.token }) });
        if (!s.ok) throw new Error(String(s.status));
        f.elements.password.value = ""; show($(".pc-login"), false); await loadSession(); await load();
      } catch (err) { $(".pc-login-e").textContent = err.message; }
    };
    async function loadSession() {
      try { const r = await fetch("/session"); st.session = r.ok ? await r.json() : { open: true }; } catch (e) { st.session = { open: true }; }
      if (st.session && st.session.open === false && !st.session.user) showLogin("");
      paintHeader();
    }

    // -- data --------------------------------------------------------------------------------------------------
    async function loadSpecs() {
      const subs = [];
      const rootSpec = await getJSON("/spec");
      if (rootSpec && rootSpec.rows) subs.push({ name: rootSpec.name, base: "", spec: rootSpec });   // the holder has no root (§10a)
      try {
        const m = await getJSON("/mounts");
        for (const [n, spec] of Object.entries(m.mounts || {})) if (spec && spec.rows) subs.push({ name: spec.name || n, base: "/" + n, spec });
      } catch (e) { /* one console, one spec */ }
      const want = opts.subsystems;
      st.subs = Array.isArray(want) ? subs.filter(s => want.includes(s.name)) : subs;
    }
    async function load() {
      if (domainOnly) return loadHolder();
      for (const sub of st.subs) {
        try {
          const d = await getJSON(sub.base + "/" + sub.spec.rows);
          if (sub === st.subs[0]) st.loadErr = null;
          const by = {};
          for (const c of d.configured || []) by[c.id] = { ...c, phase: "silent", worker_state: "stale" };
          for (const r of d.rows || []) by[r.id] = { ...by[r.id], worker_state: undefined, ...r };   // heard of: its own word on staleness
          st.units[sub.name] = Object.values(by).sort((a, b) => (typeof a.id === "number" ? a.id - b.id : String(a.id).localeCompare(String(b.id))));
        } catch (e) { st.units[sub.name] = st.units[sub.name] || []; if (sub === st.subs[0]) st.loadErr = e.message; }
      }
      try { const d = await getJSON("/servers"); st.servers = d.servers || {}; st.policy = d.policy || {}; } catch (e) { /* no servers to show */ }
      pruneLocalGroups();
      st.unplaceable = {};
      for (const sub of st.subs) { try { const d = await getJSON(sub.base + "/unplaceable"); st.unplaceable[sub.name] = Array.isArray(d) ? d : (d && d.units) || []; } catch (e) { st.unplaceable[sub.name] = []; } }
      // [course leads] the groups a spec shares with the domain: its group_by field among domain.shared
      const shared = {};
      for (const sub of st.subs) {
        const g = (display(sub).tree || {}).group_by; if (!g || !((sub.spec.domain || {}).shared || []).includes(g)) continue;
        try { const d = await getJSON("/domain/shared/" + encodeURIComponent(sub.name)), f = (d.fields || {})[g] || {}; shared[sub.name] = { groups: Array.isArray(f.groups) ? f.groups : [], rev: d.rev }; }
        catch (e) { /* no domain here: no shared groups */ }
      }
      st.shared = shared;
      try { const d = await getJSON("/drain"); st.drain = d || st.drain; } catch (e) { /* a console with no drain */ }
      try { st.schema = await getJSON("/schema"); } catch (e) { st.schema = null; }
      try { st.dom = await getJSON("/domain"); } catch (e) { st.dom = null; }
      if (st.dom) { try { st.alarms = await getJSON("/domain/alarms"); } catch (e) { st.alarms = null; } }
      await loadDomShared();
      try { st.held = await getJSON("/domain/held"); } catch (e) { st.held = null; }
      await loadGauges();
      paintHeader();
      // the same data is the same picture: an idle poll touches neither the tree nor the card (no flicker, the scroll,
      // the hover, the selection stay); a card or tab of the page's own is its data's, refreshed as it says
      const fp = JSON.stringify([st.units, st.servers, st.policy, st.dom, st.alarms, st.held, st.drain, st.unplaceable, st.schema, st.loadErr, st.shared, st.domShared]);   // [course leads] st.shared
      const same = fp === st.fp; st.fp = fp;
      if (!same) { const t = $(".pc-tree"), top = t ? t.scrollTop : 0; paintTree(); if (t) t.scrollTop = top; }
      if (!same || pageOwnsCard()) refreshMain();
      emit("refresh", { units: st.units, servers: st.servers, domain: st.dom });
    }

    // At the holder: the domain's view, its alarms, its shared settings — nothing of a cluster's.
    async function loadHolder() {
      try { st.dom = await getJSON("/domain"); st.loadErr = null; } catch (e) { st.dom = null; st.loadErr = e.message; }
      if (st.dom) { try { st.alarms = await getJSON("/domain/alarms"); } catch (e) { st.alarms = null; } }
      await loadDomShared();
      paintHeader();
      const fp = JSON.stringify([st.dom, st.alarms, st.domShared, st.loadErr]), same = fp === st.fp; st.fp = fp;
      if (!same) { const t = $(".pc-tree"), top = t ? t.scrollTop : 0; paintTree(); if (t) t.scrollTop = top; refreshMain(); }
      emit("refresh", { domain: st.dom });
    }
    // The shared settings of the domain (GET /domain/shared: {doc, delivery, declared}) — read while the domain's card
    // is what a person looks at.
    async function loadDomShared() {
      if (!st.dom || (!domainOnly && st.sel !== "domain")) { st.domShared = null; return; }
      try { st.domShared = await getJSON("/domain/shared"); } catch (e) { st.domShared = { error: e.message }; }
    }

    C.ready = (async () => {
      if (keep("pc.layout") === "servers" && !domainOnly) st.section = "servers";
      paintRail();
      await loadSession();
      try { await loadSpecs(); } catch (e) { st.loadErr = e.message; }
      paintRail(); paintAside();
      await load();
      paintMain();
      setPoll(opts.poll_s != null ? opts.poll_s : keep("pc.poll") != null ? keep("pc.poll") : 5);
      setInterval(() => { if (st.sel && parseUnit(st.sel)) loadEvents(st.sel); }, 5000);
      return C;
    })();
    return C;
  }

  window.PlatformConsole = { version: VERSION, mount };
})();
