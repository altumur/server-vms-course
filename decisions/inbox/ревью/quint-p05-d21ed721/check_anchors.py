#!/usr/bin/env python3
"""Сверка якорей отчёта по байтам среза d21ed721 (git show)."""
import subprocess, sys
PIN = "d21ed721d0c5690cbbf151a77d0fe2f366b34215"
ROOT = "/home/pilot/review103-claude-adr0130-p05-quint"
N = "Platform/05-resource/spec/05-resource.norms.md"
E = "Platform/common/contracts/event-journal.md"
T = "Platform/common/contracts/tombstone.md"
P = "Platform/common/contracts/production-obligations.md"
V = "Platform/common/vectors/production-obligations/README.md"
FM = "Platform/05-resource/forms/README.md"
S = "Platform/05-resource/acceptance/seams.tsv"
C = "Platform/05-resource/forms/runtime-constants.tsv"
A = [
 (N,29,"Q6"),(N,70,"strictly greater"),(N,78,"before the answer of the write"),(N,224,"Equality deletes"),
 (N,288,"only while the pass hangs"),(N,299,"every PASS_EVERY from the end of the pass"),
 (N,370,"exceeding it gives pass_stalled in the next heartbeat"),(N,371,"diagnostic threshold"),
 (N,383,"RESTORE_RETRY"),(N,384,"doubling up to RESTORE_RETRY_MAX"),(N,524,"only while the pass is hung"),
 (N,819,"PUT /mirror"),(N,968,"inclusive deadline"),(N,984,"mirror"),(N,985,"consecutive failures"),
 (N,986,"pass_stalled"),(N,300,"retain → usage"),(N,368,"PULSE_LIMIT is a finite"),(N,991,"Races."),(N,268,"HEARTBEAT_EVERY"),
 (E,154,"logical wall-clock write stamp"),(E,216,"Q6"),
 (T,82,"by the same action"),(P,9,"dependency waits"),(P,11,"qualification inputs"),(V,19,"Q6"),
 (FM,40,"disk durability"),(FM,58,"controlled wall clock"),
 (C,5,"HEARTBEAT_EVERY"),(C,6,"PASS_EVERY"),(C,7,"PEER_FAILS"),(C,8,"RESTORE_RETRY"),(C,9,"RESTORE_RETRY_MAX"),
 (S,52,"s50"),(S,3,"s01"),(S,69,"s67"),(S,50,"s48"),(S,31,"s29"),
]
bad = 0
cache = {}
for f,l,kw in A:
    if f not in cache:
        cache[f] = subprocess.run(["git","-C",ROOT,"show",f"{PIN}:{f}"],capture_output=True,check=True).stdout.decode("utf-8").split("\n")
    line = cache[f][l-1]
    if kw not in line:
        bad += 1
        print("НЕТ",f,l,repr(kw),line[:140])
print("anchors",len(A),"mismatch",bad)
sys.exit(1 if bad else 0)
