#!/usr/bin/env python3
"""Последовательный прогон модели P/09 (Quint). Строго по одному процессу.

Запуск: JAVA_HOME=/opt/quint/jdk PATH=/opt/quint/jdk/bin:$PATH python3 run.py [--only id1,id2] [--dir каталог]
Без --only пишет results.tsv и run.log рядом с собой; с --only — в --dir (пробы).
Перед каждым запуском проверяется HOLD; при его наличии прогон завершается с пометкой.
Apalache: один сервер на порту 18827 с -Xmx4g, запускается здесь, останавливается по PID.
"""
import argparse, json, os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
HOLD = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p09q/HOLD"
APALACHE_JAR = os.path.expanduser("~/.quint/apalache-dist-0.62.1/apalache/lib/apalache.jar")
PORT = 18827

R = "rust"; A = "apalache"
def run(id, module, inv, kind, tool, steps, samples, expect, file, overrides="", step=None, order=None):
    return dict(id=id, module=module, invariant=inv, kind=kind, tool=tool, max_steps=steps, samples=samples,
                overrides=overrides, expect=expect, file=file, step=step or "step", order=order or [])

K = "keeper_backup.qnt"; T = "relay_turn.qnt"; TM = "timing.qnt"; O = "outcomes.qnt"
RUNS = [
 # --- Б1, С11, С14 (хранитель)
 run("k01","keeper_head_only","TakenHasParts","property",R,12,20000,"violated",K,"RULE=head_only (09.1:590,1525) MAXH=2"),
 run("k02","keeper_head_only","HandoverTargetComplete","property",R,12,20000,"violated",K,"RULE=head_only"),
 run("k03","keeper_head_only","RestoreAfterLoss","property",R,12,20000,"violated",K,"RULE=head_only"),
 run("k04","keeper_head_only","TakenBehindObject","property",R,15,30000,"ok",K,"RULE=head_only"),
 run("k05","keeper_all_parts","TakenHasParts","property",R,15,30000,"ok",K,"RULE=all_parts (08.8:204)"),
 run("k06","keeper_all_parts","HandoverTargetComplete","property",R,15,30000,"ok",K,"RULE=all_parts"),
 run("k07","keeper_all_parts","RestoreAfterLoss","property",R,15,30000,"ok",K,"RULE=all_parts"),
 run("k08","keeper_all_parts","LastCopyServable","property",R,15,30000,"violated",K,"RULE=all_parts, порядок 09.1:1525: объект раньше частей"),
 run("k09","keeper_parts_first","LastCopyServable","control",R,15,30000,"ok",K,"RULE=parts_first (гипотеза)"),
 run("k10","keeper_parts_first","TakenHasParts","control",R,15,30000,"ok",K,"RULE=parts_first"),
 run("k11","keeper_head_only","witHeadOnlyHandover","witness",R,14,40000,"violated",K,"порядок: объект, строка, передача, потеря без частей",order=["writeObject","writeTaken","proceedHandover","loseHolder"]),
 run("k12","keeper_all_parts","witAllPartsTaken","witness",R,14,40000,"violated",K,"порядок: части, строка, передача",order=["fetchPart","fetchPart","writeTaken","proceedHandover"]),
 run("k13","keeper_mut_somepart","TakenHasParts","mutant",R,12,20000,"violated",K,"мутант RULE=some_part"),
 run("k14","keeper_mut_count","TakenHasParts","mutant",R,12,20000,"violated",K,"мутант RULE=count_only (части другой головы засчитаны)"),
 run("k15","keeper_mut_eager","TakenHasParts","mutant",R,14,30000,"violated",K,"мутант CLEANUP=eager"),
 run("k16","keeper_disk_text","KeeperDiskBounded","property",R,40,20000,"violated",K,"CLEANUP=none (09.1:54), MAXH=7, BACKUP_HEADS=5",step="stepDisk"),
 run("k17","keeper_disk_ctrl","KeeperDiskBounded","control",R,40,20000,"ok",K,"CLEANUP=referenced (гипотеза), MAXH=7",step="stepDisk"),
 run("k18","keeper_disk_text","witDisk","witness",R,40,20000,"violated",K,"MAXH=7: головы и части копятся",step="stepDisk",order=["newHead","movePointer","fetchPart","writeObject","writeTaken"]),
 run("k19","keeper_all_parts","witTaken","control",R,12,20000,"violated",K,"достижимость строки при all_parts",order=["fetchPart","fetchPart","writeTaken"]),
 run("k23","keeper_all_parts","witCopyReplaced","witness",R,16,60000,"violated",K,"порядок: подтверждена голова 1, объект заменён неполной головой 2",order=["fetchPart","fetchPart","writeTaken","newHead","movePointer","writeObject"]),
 run("k20","keeper_all_parts","TakenHasParts","property",A,12,0,"ok",K,"RULE=all_parts; Apalache"),
 run("k21","keeper_head_only","TakenHasParts","property",A,8,0,"violated",K,"RULE=head_only; Apalache"),
 run("k22","keeper_parts_first","LastCopyServable","control",A,12,0,"ok",K,"RULE=parts_first; Apalache"),
 # --- С7, С6 (очередь реле)
 run("t01","relay_text","DoorOnlyActive","property",R,60,200000,"violated",T,"DOOR_RULE=text (09.2:57,09.1:739), TURN 45/10",step="stepDoor"),
 run("t02","relay_text","NoStaleObserved","property",R,60,200000,"violated",T,"DOOR_RULE=text",step="stepDoor"),
 run("t03","relay_text","witStaleObserved","witness",R,60,300000,"violated",T,"порядок: взял, пауза, чужой взял, возврат, потеря увидена, POST 200",order=["takeTurn","pause","takeTurn","resume","lossObserved","memberPost"],step="stepDoor"),
 run("t04","relay_close","NoStaleObserved","control",R,60,200000,"ok",T,"DOOR_RULE=close (гипотеза)",step="stepDoor"),
 run("t05","relay_close","NoStaleUnobserved","property",R,60,200000,"violated",T,"DOOR_RULE=close: остаётся окно до наблюдения",step="stepDoor"),
 run("t06","relay_text","GuardNoLateWrite","property",R,30,100000,"ok",T,"охрана включена"),
 run("t07","relay_mut_noguard","GuardNoLateWrite","mutant",R,24,60000,"violated",T,"мутант GUARD_ON=false"),
 run("t08","relay_text","HandoverBound","property",R,45,100000,"ok",T,"stepBound; граница TURN_TERM+2*TURN_RENEW",step="stepBound"),
 run("t09","relay_mut_slowwait","HandoverBound","mutant",R,45,60000,"violated",T,"мутант WAIT_X=2",step="stepBound"),
 run("t10","relay_text","NoDroppedOnSigterm","property",R,24,40000,"violated",T,"STOP_RULE=text (09.1:1402): принятая работа брошена"),
 run("t11","relay_drain","NoDroppedOnSigterm","control",R,24,40000,"ok",T,"STOP_RULE=drain (гипотеза)"),
 run("t12","relay_text","witDropped","witness",R,20,40000,"violated",T,"порядок: приём работы, SIGTERM",order=["takeTurn","acceptWork","sigterm"]),
 run("t13","relay_text","witReleaseLost","witness",R,20,40000,"violated",T,"порядок: продление не подтверждено, SIGTERM конфликт, очередь не снята",order=["renew","sigtermConflict"]),
 run("t14","relay_text","witWaiterTook","witness",R,45,100000,"violated",T,"порядок: kill держателя, время, перехват ожидающим",step="stepKill",order=["takeTurn","kill","tick","takeTurn"]),
 run("t15","relay_text","OneActiveByRow","property",R,30,60000,"ok",T,""),
 run("t16","relay_text","witServed","control",R,20,40000,"violated",T,"достижимость 200 у истинно активной двери",order=["takeTurn","memberPost"]),
 run("t17","relay_text","GuardNoLateWrite","property",A,12,0,"ok",T,"Apalache"),
 run("t18","relay_text","HandoverBound","property",A,16,0,"ok",T,"stepBound; Apalache",step="stepBound"),
 # --- С3 (проход)
 run("p01","pass_seq_0","GapBelowLost","control",R,40,5,"ok",TM,"N_SILENT=0"),
 run("p02","pass_seq_14","GapBelowLost","property",R,60,5,"ok",TM,"N_SILENT=14, последовательно"),
 run("p03","pass_seq_15","GapBelowLost","property",R,60,5,"violated",TM,"N_SILENT=15, последовательно"),
 run("p04","pass_seq_15","MarkFresh","property",R,60,5,"violated",TM,"N_SILENT=15"),
 run("p05","pass_seq_14","MarkFresh","property",R,60,5,"ok",TM,"N_SILENT=14"),
 run("p05b","pass_end_14","GapBelowLost","property",R,60,5,"violated",TM,"N_SILENT=14, PERIOD=from_end (every от конца прохода)"),
 run("p06","pass_par_60","GapBelowLost","control",R,60,5,"ok",TM,"N_SILENT=60, параллельно"),
 run("p07","pass_par_60","MarkFresh","control",R,60,5,"ok",TM,"N_SILENT=60, параллельно"),
 run("p08","pass_seq_16","witGapOver","witness",R,60,5,"violated",TM,"порядок: последовательное следование, затем отчёт позднее LOST_AFTER",order=["waitNext","followOne","followOne","sendReport"]),
 run("p09","pass_seq_0","witSent","control",R,10,5,"violated",TM,"достижимость отчёта",order=["waitNext","sendReport"]),
 # --- С8 (часы)
 run("c01","clock_asof_nojump","AsOfNotFuture","control",R,20,40000,"ok",TM,"J=0"),
 run("c02","clock_asof_nojump","ReachedFresh","control",R,20,40000,"ok",TM,"J=0"),
 run("c03","clock_asof_nojump","RevokeBound","control",R,20,40000,"ok",TM,"J=0"),
 run("c04","clock_asof_text","AsOfNotFuture","property",R,20,40000,"violated",TM,"RULE=text, J=7200 (параметр)"),
 run("c05","clock_asof_text","ReachedFresh","property",R,20,40000,"violated",TM,"RULE=text"),
 run("c06","clock_asof_text","RevokeBound","property",R,24,60000,"violated",TM,"RULE=text"),
 run("c07","clock_asof_text","witFutureAsOf","witness",R,20,40000,"violated",TM,"порядок: скачок вперёд, ответ, возврат",order=["jumpForward","carry","jumpBack"]),
 run("c08","clock_asof_text","witStaleSkip","witness",R,20,60000,"violated",TM,"порядок: скачок, запись, возврат, время, ответ без записи",order=["jumpForward","carry","jumpBack","tick","carry"]),
 run("c09","clock_asof_clamp","AsOfNotFuture","control",R,20,40000,"ok",TM,"RULE=clamp (гипотеза)"),
 run("c10","clock_asof_clamp","RevokeBound","control",R,24,60000,"violated",TM,"RULE=clamp: снятие будущего as_of не закрывает обещание срока"),
 run("c10b","clock_asof_mono","AsOfNotFuture","control",R,20,40000,"ok",TM,"RULE=mono (гипотеза)"),
 run("c10c","clock_asof_mono","RevokeBound","control",R,24,60000,"ok",TM,"RULE=mono"),
 run("c11","clock_asof_nojump","witCarry","control",R,8,5000,"violated",TM,"достижимость ответа"),
 run("c12","alarm_nojump","AlarmBound","control",R,40,60000,"ok",TM,"J=0, проверка фронта раз в секунду"),
 run("c13","alarm_text","AlarmBound","property",R,40,100000,"violated",TM,"RULE=wall (09.1:640,643), J=20 (параметр)"),
 run("c14","alarm_text","ToNotFuture","property",R,30,60000,"violated",TM,"RULE=wall"),
 run("c15","alarm_text","witAlarmStuck","witness",R,40,100000,"violated",TM,"порядок: скачок, тревога, сборка, возврат, тревога, зависание",order=["jumpForward","alarmEvent","pageBuilt","jumpBack","alarmEvent","tick"]),
 run("c16","alarm_mono","AlarmBound","control",R,40,100000,"ok",TM,"RULE=mono (гипотеза)"),
 run("c17","alarm_mut_nocheck","AlarmBound","mutant",R,20,30000,"violated",TM,"мутант: тик без проверки фронта"),
 run("c18","alarm_nojump","witPageBuilt","control",R,15,20000,"violated",TM,"достижимость сборки страницы",order=["alarmEvent","pageBuilt"]),
 # --- С12 (шторм)
 run("s01","storm_sync_200","BurstWithinRate","control",R,10,5,"ok",TM,"N=200, синхронно"),
 run("s02","storm_sync_201","BurstWithinRate","property",R,10,5,"violated",TM,"N=201, синхронно (класс server: нет разброса, 09.1:270)"),
 run("s03","storm_uni_1000","BurstWithinRate","control",R,10,5,"ok",TM,"N=1000, равномерно"),
 run("s04","storm_uni_1001","BurstWithinRate","property",R,10,5,"violated",TM,"N=1001, равномерно"),
 run("s05","storm_sync_201","PerMemberBounded","property",R,10,5,"ok",TM,"не более 2 POST на члена (09.1:1437)"),
 run("s06","storm_sync_201","witBurst","witness",R,10,5,"violated",TM,"порядок: потеря пометок, секунда с когортой",order=["loseMarks","second"]),
 run("s07","storm_sync_200","witFired","control",R,10,5,"violated",TM,"достижимость когорты",order=["loseMarks","second"]),
 # --- С14 (отчёт, правки)
 run("o01","report_text","ConfirmedMatches","property",R,18,60000,"ok",O,"BASE_CHECK=true (acc:296)"),
 run("o02","report_text","BaseNotAhead","property",R,18,60000,"ok",O,""),
 run("o03","report_mut_nobase","ConfirmedMatches","mutant",R,16,60000,"violated",O,"мутант: шаг 3 выключен"),
 run("o04","report_text","witRebaseConverge","witness",R,18,80000,"violated",O,"порядок: потеря ответа на дельту, rebase, целое подтверждено",order=["sendDeltaLost","rebase","sendWholeOk"]),
 run("o05","report_text","ConfirmedMatches","property",A,10,0,"ok",O,"Apalache"),
 run("o06","edit_text","AtMostOnce","property",R,16,60000,"violated",O,"KEEP=86400 (06 const)"),
 run("o07","edit_inf","AtMostOnce","control",R,16,60000,"ok",O,"KEEP=10^9 (контроль без истечения)"),
 run("o08","edit_inf","witSaved","witness",R,12,20000,"violated",O,"порядок: применено, ответ потерян, сохранённый ответ",order=["appliedLost","savedAnswer"]),
 run("o09","edit_text","witAppliedTwice","witness",R,16,60000,"violated",O,"порядок: применено, истечение KEEP, повторное исполнение",order=["appliedLost","tick","reapplied"]),
 # --- Дополнительные строки: k23, t03, t09 основного прогона не совпали (см. отчёт); исходные строки оставлены.
 run("k23r","keeper_all_parts","witCopyReplaced","witness",R,16,60000,"violated",K,"k23 с порядком без лишнего newHead: подтверждение головы 1, затем указатель и объект головы 2",order=["fetchPart","fetchPart","writeTaken","movePointer","writeObject"]),
 run("t03r","relay_text","witStaleObserved","witness",R,60,300000,"violated",T,"t03 с существенным порядком: resume может идти до перехвата",step="stepDoor",order=["takeTurn","pause","takeTurn","lossObserved","memberPost"]),
 run("t08r","relay_text","HandoverBound","property",R,45,200000,"ok",T,"граница при kill держателя, фокусный шаг",step="stepKill"),
 run("t09r","relay_mut_slowwait","HandoverBound","mutant",R,45,200000,"violated",T,"мутант WAIT_X=2 на том же шаге, что t08r",step="stepKill"),
]
FIELDS = ["id","module","invariant","kind","tool","max_steps","samples","overrides","expect","actual","match","secs","file"]

def log(line, fh):
    print(line, flush=True)
    fh.write(line + "\n"); fh.flush()

def apalache_running(pid):
    return pid is not None and os.path.exists(f"/proc/{pid}")

def own_apalache_pids():
    out = subprocess.run(["ps", "-u", os.environ.get("USER", "pilot"), "-o", "pid=,args="], capture_output=True, text=True).stdout
    return [int(l.split()[0]) for l in out.splitlines() if "apalache.jar" in l and "server" in l]

def start_server(outdir, lg):
    pids = own_apalache_pids()
    if pids:
        log(f"# найден свой java apalache.jar: {pids} — не стартую сервер", lg)
        return None
    srv_log = open(os.path.join(outdir, "apalache-server.log"), "w")
    p = subprocess.Popen(["java", "-Xmx4g", "-jar", APALACHE_JAR, "server", f"--port={PORT}"], stdout=srv_log, stderr=subprocess.STDOUT, cwd=outdir, start_new_session=True)
    time.sleep(6)
    if p.poll() is not None:
        log("# сервер Apalache не поднялся", lg)
        return None
    log(f"# сервер Apalache PID {p.pid}, порт {PORT}, -Xmx4g", lg)
    return p

def stop_server(p, lg):
    if p is None: return
    try:
        os.kill(p.pid, signal.SIGTERM); p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.kill(p.pid, signal.SIGKILL)
    log(f"# сервер Apalache {p.pid} остановлен", lg)

def check_order(itf_path, order):
    if not order: return ""
    with open(itf_path) as f:
        data = json.load(f)
    actions = []
    for st in data.get("states", []):
        for k, v in st.items():
            if k.endswith("lastAction"):
                actions.append(v)
    i = 0
    for a in actions:
        if i < len(order) and a == order[i]:
            i += 1
    if i == len(order):
        return ""
    return "ORDER-MISS: нет последовательности " + ">".join(order) + " в " + ">".join(actions[:40])

def run_one(r, srv, outdir, lg):
    itf = os.path.join(outdir, "runs", f"{r['id']}.itf.json")
    runlog = os.path.join(outdir, "runs", f"{r['id']}.out")
    os.makedirs(os.path.dirname(itf), exist_ok=True)
    path = os.path.join(HERE, r["file"])
    if r["tool"] == R:
        cmd = ["quint","run","--backend=rust",f"--main={r['module']}",f"--init=init",f"--step={r['step']}",
               f"--max-steps={r['max_steps']}",f"--max-samples={max(1,r['samples'])}",f"--invariant={r['invariant']}",f"--out-itf={itf}",path]
        tmo = 900
    else:
        cmd = ["quint","verify",f"--main={r['module']}",f"--init=init",f"--step={r['step']}",f"--max-steps={r['max_steps']}",
               f"--invariant={r['invariant']}",f"--server-endpoint=localhost:{PORT}",f"--out-itf={itf}",path]
        tmo = 1200
    t0 = time.time()
    try:
        pr = subprocess.run(cmd, capture_output=True, text=True, timeout=tmo, cwd=HERE)
        out = pr.stdout + pr.stderr
        code = pr.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + (e.stderr or "") if isinstance(e.stdout, str) else "timeout"
        code = None
    secs = round(time.time() - t0, 1)
    with open(runlog, "w") as f:
        f.write(" ".join(cmd) + "\n" + (out or "") + f"\n[exit {code}]\n")
    if code is None:
        actual = "timeout"
    elif code == 0:
        actual = "ok"
    elif ("violat" in (out or "").lower()) or "[violation]" in (out or ""):
        actual = "violated"
    else:
        actual = "error"
    note = ""
    if actual == "violated" and r.get("order") and os.path.exists(itf):
        note = check_order(itf, r["order"])
    match = (actual == r["expect"]) and not note
    return actual, match, secs, note

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--dir", default="")
    args = ap.parse_args()
    trial = bool(args.only)
    outdir = args.dir or HERE if trial else HERE
    os.makedirs(outdir, exist_ok=True)
    runs = RUNS
    if args.only:
        ids = set(args.only.split(","))
        runs = [r for r in RUNS if r["id"] in ids]
    lg = open(os.path.join(outdir, "run.log"), "a")
    results_path = os.path.join(outdir, "results.tsv")
    if not os.path.exists(results_path):
        with open(results_path, "w") as f:
            f.write("\t".join(FIELDS) + "\n")
    done = set()
    with open(results_path) as f:
        for line in f.read().splitlines()[1:]:
            done.add(line.split("\t")[0])
    srv = None
    srv_needed = any(r["tool"] == A and r["id"] not in done for r in runs)
    try:
        log(f"# старт {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} запусков {len(runs)} каталог {outdir}", lg)
        if srv_needed:
            srv = start_server(outdir, lg)
            if srv is None:
                log("# Apalache не запущен; строки apalache будут error", lg)
        for r in runs:
            if r["id"] in done:
                continue
            if os.path.exists(HOLD):
                log(f"# HOLD обнаружен перед {r['id']}: прогон прерван, строки дальше не исполнены", lg)
                break
            if r["tool"] == A and srv is None:
                actual, match, secs, note = "error", False, 0.0, "сервер Apalache не запущен"
            else:
                actual, match, secs, note = run_one(r, srv, outdir, lg)
            row = dict(r); row["actual"] = actual; row["match"] = "yes" if match else "no"; row["secs"] = secs
            row["overrides"] = (row["overrides"] + (" | " + note if note else "")).strip()
            row["max_steps"] = r["max_steps"]
            with open(results_path, "a") as f:
                f.write("\t".join(str(row.get(k, "")) for k in FIELDS) + "\n")
            log(f"{r['id']}\t{r['module']}\t{r['invariant']}\t{r['kind']}\t{r['tool']}\t{actual}\t{'OK' if match else 'MISMATCH'}\t{secs}s {note}", lg)
    finally:
        if srv is not None:
            stop_server(srv, lg)
        log(f"# конец {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", lg)
        lg.close()

if __name__ == "__main__":
    main()
