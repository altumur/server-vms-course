#!/usr/bin/env python3
"""Сверка якорей отчёта с байтами среза 491b4282: подстрока в указанной строке файла."""
import subprocess, sys

S = "491b42822c64d74a3054be183ad50d4b9d875f03"
A91 = "Platform/09-agent/spec/09.1-agent.norms.md"
A92 = "Platform/09-agent/spec/09.2-agent.norms.md"
TR = "Platform/common/contracts/turn.md"
ACC = "Platform/common/contracts/accept.md"
EV = "Platform/common/contracts/event-journal.md"
F09 = "Platform/09-agent/forms/runtime-constants.tsv"
F08 = "Platform/08-domain/forms/runtime-constants.tsv"
F06 = "Platform/06-console/forms/runtime-constants.tsv"
A1 = "Platform/09-agent/acceptance/1/README.md"
N88 = "Platform/08-domain/spec/08.8-domain.norms.md"
N84 = "Platform/08-domain/spec/08.4-domain.norms.md"
N810 = "Platform/08-domain/spec/08.10-domain.norms.md"
N67 = "Platform/06-console/spec/06.7-console.norms.md"
N61 = "Platform/06-console/spec/06.1-console.norms.md"
ANCHORS = [
 (A91,54,"domain/backups/part-<part>-<rev>` (put)"),
 (A91,197,"the base is the former one"),
 (A91,270,"class server — after every"),
 (A91,360,"the moment when"),
 (A91,361,"it does not go"),
 (A91,396,"it does not go back"),
 (A91,443,"Idempotency-Key — key"),
 (A91,458,"retry:"),
 (A91,517,"domain/reached: {ts}"),
 (A91,518,"it does not go back"),
 (A91,520,"no more often than"),
 (A91,590,"then the row domain/backup-taken"),
 (A91,591,"nobody throws away the backup copy"),
 (A91,639,"once a second the agent reads only the front"),
 (A91,640,"of the row > to of the last page"),
 (A91,643,"rebuild:"),
 (A91,729,"release:"),
 (A91,731,"guard:"),
 (A91,739,"does not run the agent pass"),
 (A91,740,"does not open the relay door"),
 (A91,1397,"holder is this instance"),
 (A91,1399,"foreign and its version has not changed for ≥ TURN_TERM"),
 (A91,1402,"SIGTERM at the active one"),
 (A91,1437,"409 rebase → last_rev = 0"),
 (A91,1443,"no answer → the next pass"),
 (A91,1468,"GET /api/held of each console of CLUSTERS (deadline 3 s"),
 (A91,1525,"write the object domain/backup, then the row domain/backup-taken"),
 (A91,1723,"P/09.1-30"),
 (A91,735,"written only by the active one"),
 (A92,57,"the door is opened only by the active agent"),
 (A92,60,"order: a connection refusal or 503 standby — the next one"),
 (A92,92,"hold:"),
 (A92,133,"200 — the holder's carry"),
 (TR,32,"TURN_TERM: 45"),
 (TR,33,"TURN_RENEW: 10"),
 (TR,46,"not changed for ≥ `TURN_TERM`"),
 (TR,51,"Every `TURN_RENEW`"),
 (TR,56,"do not repeat on a conflict"),
 (TR,58,"An unknown outcome"),
 (TR,88,"**Races.**"),
 (TR,98,"NOT a fence"),
 (ACC,218,"class server does not get it"),
 (ACC,289,"one at a time"),
 (ACC,296,"409 rebase"),
 (ACC,302,"MARK_REFRESH"),
 (ACC,306,"otherwise → generation"),
 (EV,216,"nondecreasing event stamps"),
 (A1,40,"`LOST_AFTER` 45 s"),
 (N84,233,"as_of + GRANT_LIFETIME"),
 (N84,898,"no later than `GRANT_LIFETIME` from `as_of`"),
 (N88,173,"the pass checks the pointers"),
 (N88,176,"the keeper pulls the parts"),
 (N88,187,"The keeper's agent"),
 (N88,203,"a part lives while one of the BACKUP_HEADS"),
 (N88,204,"writes domain/backup-taken when it has all parts of the head"),
 (N88,206,"behind:"),
 (N88,321,"a backup copy with force"),
 (N88,322,"wait for the report of to"),
 (N88,745,"do not write taken"),
 (N810,94,"makes it effective"),
 (N67,70,"the pointer `domain/backup-taken`"),
 (N67,335,"404 — no part"),
 (N61,182,"DONE_ANSWER_KEEP from the moment"),
 (N61,700,"409 `in flight`"),
 (N61,704,"An answer `< 500`"),
 (N61,711,"Continuation"),
 (N61,783,"unknown outcome"),
 (F09,3,"REPORT_EVERY"),(F09,7,"FRESH_EVERY"),(F09,15,"URGENT_GAP"),
 (F08,18,"GRANT_LIFETIME"),(F08,36,"REPORT_RATE"),(F08,49,"BACKUP_HEADS"),
 (F06,32,"CLAIM_TAKEOVER_AFTER"),(F06,33,"DONE_ANSWER_KEEP"),
 (ACC,37,"an object of the holder"),(A92,246,"the members send the whole by 409 `rebase`"),
 (A91,53,"`domain/backup`"),
 (A91,1521,"sha256 of the text of doc"),(A91,1524,"revoked_issuer"),(A91,334,"member_want"),(A91,442,"For every edit of the answer"),
 (N67,331,"answer:"),(N810,95,"backup copies domain/backups/rev-*"),(A91,1396,"read domain/agent-turn"),
]
def main():
    ok = bad = 0
    cache = {}
    for (path, line, sub) in ANCHORS:
        if path not in cache:
            data = subprocess.run(["git", "show", f"{S}:{path}"], check=True, capture_output=True).stdout
            cache[path] = data.split(b"\n")
        text = cache[path][line - 1].decode("utf-8")
        if sub in text:
            ok += 1
        else:
            bad += 1
            print(f"MISS {path}:{line} ~ {sub!r}\n  got: {text[:200]}")
    print(f"anchors ok={ok} miss={bad}")
    sys.exit(1 if bad else 0)
if __name__ == "__main__":
    main()
