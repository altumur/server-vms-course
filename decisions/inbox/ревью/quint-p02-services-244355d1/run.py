#!/usr/bin/env python3
"""Прогоны модели Quint P/02 «службы и запуск» (срез 244355d1).

Запуск: python3 run.py  (инструменты: quint 0.33.0, Apalache 0.62.1).
Не более двух процессов Apalache одновременно, Xmx ≤ 4 ГБ; порты 8855/8856.
Перед запуском каждого прогона проверяется файл HOLD; вывод — runs/<id>.log,
results.tsv, run.log. Исполняются только свои модели (*.qnt этого каталога).
"""
import concurrent.futures, os, re, subprocess, sys, time, threading

HERE = os.path.dirname(os.path.abspath(__file__))
HOLD = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p02q/HOLD"
SRC_TRACES = "../../../../Platform/02-installer/forms/rollout-poll.traces.tsv"
PORTS = [8855, 8856]
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk",
           PATH="/opt/quint/jdk/bin:" + os.environ["PATH"], JVM_ARGS="-Xmx3g", NO_COLOR="1")

# id,file,main,invariant,kind,tool,max_steps,samples,expect, overrides(комментарий)
R = []
def add(fid, file, main, inv, kind, tool, steps, samples, expect, note):
    R.append(dict(id=fid, file=file, main=main, inv=inv, kind=kind, tool=tool,
                  steps=steps, samples=samples, expect=expect, note=note))

W = "workerstart.qnt"
add("WS01", W, "ws_a", "inv_noKill", "property", "verify", 8, 0, "violated", "С1 START_WAIT у программы от exec, TS=90, чтение≤срока")
add("WS02", W, "ws_b", "inv_noKill", "control", "verify", 14, 0, "holds", "контроль: START_WAIT от старта юнита (exec), TS=90")
add("WS03", W, "ws_c", "inv_noKill", "property", "verify", 8, 0, "violated", "С1 последнее чтение за START_WAIT на 30 (READ_OVER=TS−START_WAIT), база юнита")
add("WS04", W, "ws_c0", "inv_noKill", "control", "verify", 12, 0, "holds", "контроль: READ_OVER=29 — на границу нет")
add("WS05", W, "ws_d", "inv_noKill", "property", "verify", 8, 0, "violated", "С1 flock без срока (pres:32) при TS=90")
add("WS06", W, "ws_e", "inv_noKill", "property", "verify", 8, 0, "violated", "граница: TS=120, база exec — ничья в пользу kill")
add("WS07", W, "ws_f", "inv_noKill", "control", "verify", 14, 0, "holds", "контроль: TS=121, база exec — минимальный безопасный срок")
add("WS08", W, "ws_g", "inv_noKill", "control", "verify", 14, 0, "holds", "контроль: TS=∞, база unit, flock ограничен — нет kill")
add("WS09", W, "ws_n", "inv_nobodyNotKilled", "property", "verify", 10, 0, "violated", "С2 nobody без READY до TS=90")
add("WS10", W, "ws_nr", "inv_nobodyNotKilled", "control", "verify", 14, 0, "holds", "контроль: READY=1 при входе в цикл nobody")
add("WS11", W, "ws_ni", "inv_nobodyNotKilled", "control", "verify", 14, 0, "holds", "контроль: TS=∞ в ветке nobody")
add("WS12", W, "ws_n", "killsLT2", "witness", "verify", 18, 0, "violated", "С2 цикл перезапусков nobody: ≥2 убийства сроком")
add("WS13", W, "ws_h", "inv_activatingBound", "property", "verify", 8, 0, "violated", "С1/С2 TS=∞ + flock без срока: activating без предела")
add("WS14", W, "ws_hb", "inv_activatingBound", "control", "verify", 12, 0, "holds", "контроль: TS=∞, но flock≤60 — activating конечен")
add("WS15", W, "ws_b", "notReady", "witness", "verify", 10, 0, "violated", "достижимость Ready")
add("WS16", W, "ws_b", "notExit1", "witness", "verify", 8, 0, "violated", "достижимость exit 1 по START_WAIT")
add("WS17", W, "ws_b", "notExit2", "witness", "verify", 8, 0, "violated", "достижимость exit 2")
add("WS18", W, "ws_n", "notNobody", "witness", "verify", 10, 0, "violated", "достижимость nobody")
add("WS19", W, "ws_m1", "inv_readyAfterCapture", "mutant", "verify", 10, 0, "violated", "мутант: READY=1 до захвата имени")
add("WS20", W, "ws_m2", "inv_exit1Deadline", "mutant", "verify", 8, 0, "violated", "мутант: конец START_WAIT не соблюдён")
add("WS21", W, "ws_m3", "inv_noRestartAfter2", "mutant", "verify", 10, 0, "violated", "мутант: перезапуск после exit 2")
add("WS22", W, "ws_a", "inv_exit1Deadline", "property", "verify", 12, 0, "holds", "exit 1 не позже START_WAIT+READ_OVER своей базы")
add("WS23", W, "ws_b", "inv_exit1Deadline", "property", "verify", 12, 0, "holds", "то же, база unit")
add("WS24", W, "ws_n", "inv_readyAfterCapture", "property", "verify", 12, 0, "holds", "READY только после захвата имени")
add("WS25", W, "ws_b", "inv_noRestartAfter2", "property", "verify", 12, 0, "holds", "exit 2 не перезапускает")

T = "workertimer.qnt"
add("WT01", T, "wt_a", "inv_passBounded", "property", "verify", 8, 0, "violated", "С4 3 номера × START_MAX 90 > период 60")
add("WT02", T, "wt_a", "inv_opsFresh", "property", "verify", 8, 0, "violated", "С4 данные действия старше минуты")
add("WT03", T, "wt_a", "inv_serial", "control", "verify", 12, 0, "holds", "контроль: oneshot+таймер — проходы не параллельны")
add("WT04", T, "wt_a", "inv_noStartWhileUncertain", "control", "verify", 12, 0, "holds", "контроль: uncertain занят (правило 5)")
add("WT05", T, "wt_b", "inv_passBounded", "control", "verify", 12, 0, "holds", "контроль: 3 × 20 = период (STOP/START=20)")
add("WT06", T, "wt_b", "inv_opsFresh", "control", "verify", 12, 0, "holds", "контроль: то же, данные свежи")
add("WT07", T, "wt_c", "inv_opsFresh", "control", "verify", 12, 0, "holds", "контроль: перепроверка возраста перед каждым действием (не норма)")
add("WT08", T, "wt_d", "inv_passBounded", "property", "verify", 8, 0, "violated", "С4 чтение /metrics без срока")
add("WT09", T, "wt_e", "inv_passBounded", "control", "verify", 12, 0, "holds", "контроль: --no-block (не норма)")
add("WT10", T, "wt_e", "inv_opsFresh", "control", "verify", 12, 0, "holds", "контроль: --no-block, свежие данные")
add("WT11", T, "wt_m1", "inv_noStartWhileUncertain", "mutant", "verify", 14, 0, "violated", "мутант: план игнорирует uncertain")
add("WT12", T, "wt_m2", "inv_serial", "mutant", "verify", 8, 0, "violated", "мутант: два механизма (таймер и рука) параллельно")
add("WT13", T, "wt_a", "notAct", "witness", "verify", 8, 0, "violated", "достижимость действия")
add("WT14", T, "wt_b", "notCompleted", "witness", "verify", 14, 0, "violated", "достижимость двух завершённых проходов")

S = "socketact.qnt"
add("SA01", S, "sa_a", "inv_code2NoRestart", "property", "verify", 6, 0, "violated", "С5 сокет запускает службу после кода 2")
add("SA02", S, "sa_a", "inv_opStopHolds", "property", "verify", 6, 0, "violated", "С5 окно оператора нарушено сокетом")
add("SA03", S, "sa_a", "inv_sockNotFailed", "property", "verify", 6, 0, "violated", "С5 TriggerLimit переводит сокет в failure")
add("SA04", S, "sa_a", "inv_restartPrevent2", "control", "verify", 10, 0, "holds", "контроль: путь Restart= кодом 2 закрыт (A1 не затрагивает)")
add("SA05", S, "sa_nosock", "inv_code2NoRestart", "control", "verify", 10, 0, "holds", "контроль: без активации сокета A1 не нарушено")
add("SA06", S, "sa_nosock", "inv_opStopHolds", "control", "verify", 10, 0, "holds", "контроль: без активации сокета окно держится")
add("SA07", S, "sa_fix2", "inv_code2NoRestart", "control", "verify", 10, 0, "holds", "контроль: код 2 останавливает сокеты (вариант лечения)")
add("SA08", S, "sa_fixop", "inv_opStopHolds", "control", "verify", 10, 0, "holds", "контроль: стоп оператора охватывает .socket")
add("SA09", S, "sa_notrig", "inv_sockNotFailed", "control", "verify", 8, 0, "holds", "контроль: TriggerLimit выключен")
add("SA10", S, "sa_m1", "inv_restartPrevent2", "mutant", "verify", 8, 0, "violated", "мутант: Restart= перезапускает код 2")
add("SA11", S, "sa_a", "notFailed2", "witness", "verify", 6, 0, "violated", "достижимость exit 2")
add("SA12", S, "sa_a", "notRunning", "witness", "verify", 6, 0, "violated", "достижимость работающей службы")

P = "rolloutsteps.qnt"
add("RS01", P, "rs_read", "inv_barrierWithinWait", "property", "verify", 10, 0, "violated", "С6 чтение барьера без срока — ROLLOUT_WAIT превышается")
add("RS02", P, "rs_bound", "inv_barrierWithinWait", "control", "verify", 10, 0, "holds", "контроль: чтение обрезается остатком ROLLOUT_WAIT (не норма)")
add("RS03", P, "rs_a", "inv_noEnableBeforeEnd", "control", "verify", 12, 0, "holds", "контроль: W2C_HOLD удерживает включение до конца (норма)")
add("RS04", P, "rs_m1", "inv_noEnableBeforeEnd", "mutant", "verify", 10, 0, "violated", "мутант: на повторе HOLD считают как при первой установке")
add("RS05", P, "rs_a", "inv_doneAfterBarrier", "control", "verify", 12, 0, "holds", "контроль: Done только с барьером в этой попытке")
add("RS06", P, "rs_m2", "inv_doneAfterBarrier", "mutant", "verify", 10, 0, "violated", "мутант: повтор завершается без барьера")
add("RS07", P, "rs_a", "notDone", "witness", "verify", 10, 0, "violated", "достижимость Done")
add("RS08", P, "rs_a", "notRepeated", "witness", "verify", 12, 0, "violated", "достижимость повтора")

B = "pollbound.qnt"
add("PB01", B, "pb_ok", "inv_seen", "property", "verify", 1, 0, "holds", "02.4:530 простой 2 с замечен пачкой: DOWN=2.00")
add("PB02", B, "pb_ok201", "inv_seen", "control", "verify", 1, 0, "holds", "контроль: простой 2.01 с")
add("PB03", B, "pb_198", "inv_seen", "mutant", "verify", 1, 0, "violated", "мутант (RestartSec короче): простой 1.98 с не замечается")
add("PB06", B, "pb_199", "inv_seen", "control", "verify", 1, 0, "holds", "контроль: простой 1.99 с — граница целочисленной сетки (см. отчёт)")
add("PB04", B, "pb_short", "inv_seen", "mutant", "verify", 1, 0, "violated", "мутант: RestartSec=1, простой 1.00 с")
add("PB05", B, "pb_ok", "inv_sanity", "witness", "verify", 1, 0, "holds", "наблюдения не пусты (невакуумность)")

M = "rolloutpoll.qnt"
SIM = 20000
add("RP01", M, "rp_3f", "inv_machine", "property", "run", 60, SIM, "holds", "8 инвариантов машины (machine: invariants)")
add("RP02", M, "rp_3f", "inv_pollBounded", "property", "run", 60, SIM, "holds", "опрос закрывается не позже ROLLOUT_WAIT")
add("RP03", M, "rp_3f", "inv_lastAnswerThisBatch", "property", "run", 60, SIM, "holds", "живой — только по ответу этого батча (late ignored)")
add("RP04", M, "rp_3f", "inv_aliveReplyLive", "property", "run", 60, SIM, "holds", "живой — только по живому ответу")
add("RP05", M, "rp_3f", "inv_oneReadPerBatch", "property", "run", 60, SIM, "holds", "одно чтение целей на батч")
add("RP06", M, "rp_3f", "inv_lateCommitIgnored", "property", "run", 60, SIM, "holds", "поздний commit игнорируется")
add("RP07", M, "rp_3f", "inv_passQuorum", "property", "run", 60, SIM, "holds", "pass только при живых ≥ quorum+1")
add("RP08", M, "rp_3f", "notPassed", "witness", "run", 60, SIM, "violated", "достижимость passed")
add("RP09", M, "rp_3f", "notRefused", "witness", "run", 60, SIM, "violated", "достижимость refused")
add("RP10", M, "rp_3f", "notBreakAll", "witness", "run", 60, SIM, "violated", "достижимость обрыва всех")
add("RP11", M, "rp_3f", "notExpired", "witness", "run", 60, SIM, "violated", "достижимость wait_expired")
add("RP12", M, "rp_m1", "inv_aliveReplyLive", "mutant", "run", 60, SIM, "violated", "мутант: любой ответ живой")
add("RP13", M, "rp_m2", "inv_lastAnswerThisBatch", "mutant", "run", 60, SIM, "violated", "мутант: ответ чужой пачки учтён")
add("RP14", M, "rp_m3", "inv_lateCommitIgnored", "mutant", "run", 60, SIM, "violated", "мутант: read_expired не снимает чтение")
add("RP15", M, "rp_m4", "inv_pollBounded", "mutant", "run", 60, SIM, "violated", "мутант: нет wait_expired")
add("RP16", M, "rp_m5", "inv_passQuorum", "mutant", "run", 60, SIM, "violated", "мутант: судья quorum без запаса")

# Сверка трасс: одна строка на файл (44 трассы канона), негативный контроль — мутант в трассах.
add("TR01", "rolloutpoll_traces.qnt", "rolloutpoll_traces", "traces(44)", "control", "test", 0, 1, "holds", "трассы канона rollout-poll.traces.tsv (44)")
add("TR02", "runs/rolloutpoll_traces_m1.qnt", "rolloutpoll_traces", "traces(44)", "control", "test", 0, 1, "violated", "негативный контроль: трассы на мутанте 1 (любой ответ живой)")
add("TR03", "runs/rolloutpoll_traces_m2.qnt", "rolloutpoll_traces", "traces(44)", "control", "test", 0, 1, "violated", "чувствительность трасс: мутант 2 (ответ чужой пачки учтён); ожидание не подтвердилось, см. отчёт")
add("TR04", "runs/rolloutpoll_traces_m3.qnt", "rolloutpoll_traces", "traces(44)", "control", "test", 0, 1, "violated", "чувствительность трасс: мутант 3 (read_expired не снимает чтение)")
add("TR05", "runs/rolloutpoll_traces_m4.qnt", "rolloutpoll_traces", "traces(44)", "control", "test", 0, 1, "violated", "чувствительность трасс: мутант 4 (нет wait_expired)")
add("TR06", "runs/rolloutpoll_traces_m5.qnt", "rolloutpoll_traces", "traces(44)", "control", "test", 0, 1, "violated", "чувствительность трасс: мутант 5 (судья без запаса)")

lock = threading.Lock()
results = {}
WORK = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p02q/apalache-work"
free_ports = list(PORTS)
port_cv = threading.Condition(lock)

def acquire_port():
    with port_cv:
        while not free_ports:
            port_cv.wait()
        return free_ports.pop()

def release_port(p):
    with port_cv:
        free_ports.append(p)
        port_cv.notify()

def run_one(r):
    if os.path.exists(HOLD):
        results[r["id"]] = ("skip-hold", 0)
        return
    log = os.path.join(HERE, "runs", r["id"] + ".log")
    t0 = time.time()
    actual = "error"
    if r["tool"] == "verify":
        p = acquire_port()
        try:
            cmd = ["quint", "verify", "--main=" + r["main"], "--max-steps=%d" % r["steps"],
                   "--invariant=" + r["inv"], "--server-endpoint=localhost:%d" % p]
            if r["main"].startswith("rp_"):
                cmd += ["--init=initAll", "--step=stepAll"]
            cmd += [os.path.join(HERE, r["file"])]
            # cwd вне проекта: _apalache-out и tmp не попадают в коммит.
            out = subprocess.run(cmd, cwd=WORK, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1200)
            txt = out.stdout
            if "No violation found" in txt and out.returncode == 0:
                actual = "holds"
            elif "Found an issue" in txt or "counterexample" in txt.lower():
                actual = "violated"
            else:
                actual = "error"
        finally:
            release_port(p)
    elif r["tool"] == "run":
        cmd = ["quint", "run", "--main=" + r["main"], "--backend=rust", "--max-steps=%d" % r["steps"],
               "--max-samples=%d" % r["samples"], "--invariant=" + r["inv"], "--seed=0x" + "%x" % 0x1234ABCD]
        if r["main"].startswith("rp_"):
            cmd += ["--init=initAll", "--step=stepAll"]
        cmd += [r["file"]]
        out = subprocess.run(cmd, cwd=HERE, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1200)
        txt = out.stdout
        if "No violation found" in txt:
            actual = "holds"
        elif "Found an issue" in txt:
            actual = "violated"
    else:  # test
        cmd = ["quint", "test", "--main=" + r["main"], "--match=tr_", "--max-samples=1", r["file"]]
        out = subprocess.run(cmd, cwd=HERE, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
        txt = out.stdout
        m = re.search(r"(\d+) passing", txt)
        f = re.search(r"(\d+) failed", txt)
        if out.returncode == 0 and m and int(m.group(1)) == 44:
            actual = "holds"
        elif f and int(f.group(1)) > 0:
            actual = "violated"
    secs = round(time.time() - t0, 1)
    with open(log, "w", encoding="utf8") as fh:
        fh.write(" ".join(cmd) + "\n" + txt)
    results[r["id"]] = (actual, secs)

def main():
    os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
    # Генерация трасс и мутантов трасс
    src = os.path.join(HERE, SRC_TRACES)
    if not os.path.exists(src):
        src = "/home/pilot/review103-claude-adr0130-p02-quint/Platform/02-installer/forms/rollout-poll.traces.tsv"
    os.makedirs(WORK, exist_ok=True)
    muts = [("runs/rolloutpoll_traces_m%d.qnt" % m, m) for m in (1, 2, 3, 4, 5)]
    for name, m in [("rolloutpoll_traces.qnt", 0)] + muts:
        subprocess.check_call(["python3", os.path.join(HERE, "gen_traces.py"), src, os.path.join(HERE, name), str(m)], env=ENV)
    # В runs/* импорт относительно ../rolloutpoll.
    for name, _ in muts:
        p = os.path.join(HERE, name)
        t = open(p, encoding="utf8").read().replace('from "./rolloutpoll"', 'from "../rolloutpoll"')
        open(p, "w", encoding="utf8").write(t)
    # verify — не более двух параллельно; run/test — в том же пуле.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(run_one, R))
    with open(os.path.join(HERE, "results.tsv"), "w", encoding="utf8") as tsv, \
         open(os.path.join(HERE, "run.log"), "w", encoding="utf8") as lg:
        tsv.write("id\tmodule\tinvariant\tkind\ttool\tmax_steps\tsamples\toverrides\texpect\tactual\tmatch\tsecs\tfile\n")
        bad = 0
        for r in R:
            actual, secs = results.get(r["id"], ("not-run", 0))
            match = "yes" if actual == r["expect"] else "NO"
            if match == "NO":
                bad += 1
            line = "\t".join([r["id"], r["main"], r["inv"], r["kind"], r["tool"], str(r["steps"]), str(r["samples"]), r["note"], r["expect"], actual, match, str(secs), r["file"]])
            tsv.write(line + "\n")
            lg.write(line + "\n")
        lg.write("mismatch=%d total=%d\n" % (bad, len(R)))
    print("mismatch", bad, "of", len(R))

if __name__ == "__main__":
    main()
