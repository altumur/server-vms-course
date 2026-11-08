#!/usr/bin/env python3
"""Прогоны моделей P/05 (Quint/Apalache). Запуск: python3 run.py [фильтр id по подстроке]."""
import csv, os, re, subprocess, sys, time
HOME = os.path.dirname(os.path.abspath(__file__))
HOLD = "/tmp/claude-1001/-home-pilot-review103-claude/60fca57e-e559-4968-b357-48ce230bae06/scratchpad/ev0130p05q/HOLD"
ENDPOINT = "localhost:8833"
ENV = dict(os.environ, JAVA_HOME="/opt/quint/jdk", PATH="/opt/quint/jdk/bin:" + os.environ["PATH"])

PASS_BASE = dict(PASS_EVERY=600, PEER_FAILS=3, NB=6, PEERS_N=2, BUDGET=10, EXPIRY_FAIL="true", REFUSAL_FAIL="false",
                 REFUSE_HEAD=0, KINDS='Set("HANG")', PER_CALL="false", STEP_BUDGET=0, PASS_BOUND=60,
                 MUT_NO_SKIP="false", MUT_KEEP_SKIP="false")
RET_BASE = dict(TERM=86400, MODE='"LETTER"', JUMPS="Set(0)", ALLOWED=0, CAN_APPEND="false", WRITTEN_WATERMARK="false",
                MUT_STRICT="false", MUT_EARLY="false", MUT_NO_MONO="false", MAX_JUMPS=99)
CR_BASE = dict(BARRIER="false", ORDER='"ANY"')
RY_BASE = dict(RETRY=10, RETRY_MAX=600, STARTS="Set(0)", JITTER="Set(0)", MAX_ATTEMPTS=8)
ST_BASE = dict(HB=10, L=20, DURS="Set(19, 21, 40)", BLOCK_HB="false")

# (id, модуль модели, база, overrides, инвариант, kind, tool, steps, samples, expect)
C = []
def c(i, f, base, ov, inv, kind, steps, expect, tool="apalache", samples=0):
    C.append(dict(id=i, f=f, base=base, ov=ov, inv=inv, kind=kind, steps=steps, expect=expect, tool=tool, samples=samples))

# Проход и mirror (C1, M1)
c("p01a-hang-nobudget","p05_pass",PASS_BASE,dict(BUDGET=0,PASS_BOUND=6000),"inv_passBounded","property",16,"violated")
c("p01b-hang-nobudget-gap","p05_pass",PASS_BASE,dict(BUDGET=0,PASS_BOUND=6000),"inv_retainGap","property",16,"violated")
c("p01w-hung-reach","p05_pass",PASS_BASE,dict(BUDGET=0,PASS_BOUND=6000),"wit_hung","witness",8,"violated")
c("p02a-budget-expfail","p05_pass",PASS_BASE,dict(),"inv_passBounded","property",34,"holds")
c("p02b-budget-expfail-gap","p05_pass",PASS_BASE,dict(),"inv_retainGap","property",34,"holds")
c("p02w-tight","p05_pass",PASS_BASE,dict(),"wit_tight","witness",20,"violated")
c("p02w2-twopasses","p05_pass",PASS_BASE,dict(),"wit_twoPasses","witness",34,"violated")
c("p02c-consulted-control","p05_pass",PASS_BASE,dict(),"inv_consulted","control",34,"holds")
c("p03a-budget5-expfail","p05_pass",PASS_BASE,dict(BUDGET=5,PASS_BOUND=30),"inv_passBounded","property",34,"holds")
c("p03w-budget5-tight","p05_pass",PASS_BASE,dict(BUDGET=5,PASS_BOUND=30),"wit_tight","witness",20,"violated")
c("p04-bound-sensitivity","p05_pass",PASS_BASE,dict(PASS_BOUND=59),"inv_passBounded","control",20,"violated")
c("p05-expiry-not-failure","p05_pass",PASS_BASE,dict(EXPIRY_FAIL="false"),"inv_passBounded","property",24,"violated")
c("p06-slow-success","p05_pass",PASS_BASE,dict(KINDS='Set("SLOW")'),"inv_passBounded","property",24,"violated")
c("p07-percall-hang-ok","p05_pass",PASS_BASE,dict(KINDS='Set("HANG","OK")',PER_CALL="true"),"inv_passBounded","property",26,"violated")
c("p08a-stepbudget-fix","p05_pass",PASS_BASE,dict(KINDS='Set("HANG","SLOW","OK")',PER_CALL="true",STEP_BUDGET=60,PASS_BOUND=70),"inv_passBounded","control",34,"holds")
c("p08w-stepbudget-completes","p05_pass",PASS_BASE,dict(KINDS='Set("HANG","SLOW","OK")',PER_CALL="true",STEP_BUDGET=60,PASS_BOUND=70),"wit_completedPass","witness",30,"violated")
c("p09a-healthy-bound0","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',PASS_BOUND=0),"inv_passBounded","control",34,"holds")
c("p09w-healthy-twopasses","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',PASS_BOUND=0),"wit_twoPasses","witness",34,"violated")
c("p10-m1-letter-refusecount","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',REFUSE_HEAD=3,REFUSAL_FAIL="true",BUDGET=10),"inv_behindCopied","property",14,"violated")
c("p11a-m1-refuse-notcounted","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',REFUSE_HEAD=3,REFUSAL_FAIL="false"),"inv_behindCopied","property",20,"holds")
c("p11w-m1-completed","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',REFUSE_HEAD=3,REFUSAL_FAIL="false"),"wit_completedPass","witness",20,"violated")
c("p12-m1-head2-control","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',REFUSE_HEAD=2,REFUSAL_FAIL="true"),"inv_behindCopied","control",20,"holds")
c("p12w-m1-head2-completed","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',REFUSE_HEAD=2,REFUSAL_FAIL="true"),"wit_completedPass","witness",20,"violated")
c("m01-noskip","p05_pass",PASS_BASE,dict(MUT_NO_SKIP="true"),"inv_passBounded","mutant",24,"violated")
c("m02-keepskip","p05_pass",PASS_BASE,dict(MUT_KEEP_SKIP="true"),"inv_consulted","mutant",24,"violated")
c("m03-noskip-nb3-control","p05_pass",PASS_BASE,dict(MUT_NO_SKIP="true",NB=3),"inv_passBounded","control",34,"holds")

# retain (C15)
c("r01a-letter-nojump-q6","p05_retain",RET_BASE,dict(),"inv_noEarly","property",8,"holds")
c("r01b-letter-nojump-s50","p05_retain",RET_BASE,dict(),"inv_s50","property",8,"holds")
c("r01c-letter-nojump-s49","p05_retain",RET_BASE,dict(),"inv_s49","property",8,"holds")
c("r01w1-removed","p05_retain",RET_BASE,dict(),"wit_removed","witness",8,"violated")
c("r01w2-boundary-eq","p05_retain",RET_BASE,dict(),"wit_boundaryEq","witness",8,"violated")
c("r01w3-below","p05_retain",RET_BASE,dict(),"wit_retainBelow","witness",8,"violated")
c("r02-letter-forward-q6","p05_retain",RET_BASE,dict(JUMPS="Set(0,86400)"),"inv_noEarly","property",8,"violated")
c("r02w-jumped","p05_retain",RET_BASE,dict(JUMPS="Set(0,86400)"),"wit_jumped","witness",4,"violated")
c("r03-letter-back-then-correct","p05_retain",RET_BASE,dict(JUMPS="Set(0,-600,600)",CAN_APPEND="true"),"inv_noEarlyNetZero","property",12,"violated")
c("r03c-letter-back-no-append-control","p05_retain",RET_BASE,dict(JUMPS="Set(0,-600,600)",CAN_APPEND="false"),"inv_noEarlyNetZero","control",8,"holds")
c("r04a-letter-qualified-eps1jump","p05_retain",RET_BASE,dict(JUMPS="Set(0,1)",ALLOWED=1,MAX_JUMPS=1),"inv_noEarly","control",10,"holds")
c("r04b-letter-qualified-eps-unbounded","p05_retain",RET_BASE,dict(JUMPS="Set(0,1)",ALLOWED=1),"inv_noEarly","control",10,"violated")
c("r05a-defer-forward-q6","p05_retain",RET_BASE,dict(MODE='"DEFER"',JUMPS="Set(0,86400)"),"inv_noEarly","property",10,"holds")
c("r05b-defer-forward-s50","p05_retain",RET_BASE,dict(MODE='"DEFER"',JUMPS="Set(0,86400)"),"inv_s50","property",10,"violated")
c("r05w-defer-removes-after-term","p05_retain",RET_BASE,dict(MODE='"DEFER"',JUMPS="Set(0,86400)"),"wit_removedAfterTerm","witness",10,"violated")
c("r06a-defer-seam-controlled","p05_retain",RET_BASE,dict(MODE='"DEFER"'),"inv_s50","control",10,"holds")
c("r06b-defer-seam-q6","p05_retain",RET_BASE,dict(MODE='"DEFER"'),"inv_noEarly","control",10,"holds")
c("r06w-defer-seam-removes","p05_retain",RET_BASE,dict(MODE='"DEFER"'),"wit_removedAfterTerm","witness",10,"violated")
c("r07w-defer-back-removes","p05_retain",RET_BASE,dict(MODE='"DEFER"',JUMPS="Set(0,-600,600)",CAN_APPEND="true"),"wit_removedAfterTerm","witness",12,"violated")
c("r07-defer-back-correct","p05_retain",RET_BASE,dict(MODE='"DEFER"',JUMPS="Set(0,-600,600)",CAN_APPEND="true"),"inv_noEarly","control",12,"holds")
c("r08-watermark-not-enough","p05_retain",RET_BASE,dict(JUMPS="Set(0,-600,600)",CAN_APPEND="true",WRITTEN_WATERMARK="true"),"inv_noEarly","control",12,"violated")
c("rm1-strict","p05_retain",RET_BASE,dict(MUT_STRICT="true"),"inv_s50","mutant",8,"violated")
c("rm2-early","p05_retain",RET_BASE,dict(MUT_EARLY="true"),"inv_s49","mutant",8,"violated")
c("rm3-defer-no-mono","p05_retain",RET_BASE,dict(MODE='"DEFER"',JUMPS="Set(0,86400)",MUT_NO_MONO="true"),"inv_noEarly","mutant",8,"violated")

# Сбой при записи (C17, M6)
c("k01-letter-no-barrier","p05_crash",CR_BASE,dict(),"inv_ackDurable","property",6,"violated")
c("k02a-barrier-fix","p05_crash",CR_BASE,dict(BARRIER="true"),"inv_ackDurable","property",10,"holds")
c("k02w-barrier-ack-crash","p05_crash",CR_BASE,dict(BARRIER="true"),"wit_ackThenCrash","witness",8,"violated")
c("k03-order-any","p05_crash",CR_BASE,dict(),"inv_noResurrect","property",8,"violated")
c("k04a-body-first","p05_crash",CR_BASE,dict(ORDER='"BODY_FIRST"'),"inv_noResurrect","property",12,"holds")
c("k04w1-rewrite-done","p05_crash",CR_BASE,dict(ORDER='"BODY_FIRST"'),"wit_rewriteDone","witness",8,"violated")
c("k04w2-crash-mid","p05_crash",CR_BASE,dict(ORDER='"BODY_FIRST"'),"wit_crashMid","witness",8,"violated")
c("k05-tomb-first-mut","p05_crash",CR_BASE,dict(ORDER='"TOMB_FIRST"'),"inv_noResurrect","mutant",8,"violated")

# Повторы restore (C18)
c("t01a-together","p05_retry",RY_BASE,dict(),"inv_alwaysTogether","property",12,"holds")
c("t01b-gap","p05_retry",RY_BASE,dict(),"inv_gapPreserved","property",12,"holds")
c("t01w-coincide","p05_retry",RY_BASE,dict(),"wit_coincide","witness",10,"violated")
c("t02a-offset-gap","p05_retry",RY_BASE,dict(STARTS="Set(0,5)"),"inv_gapPreserved","property",16,"holds")
c("t02w-offset","p05_retry",RY_BASE,dict(STARTS="Set(0,5)"),"wit_nonzeroGap","witness",12,"violated")
c("t03-jitter-mut-together","p05_retry",RY_BASE,dict(JITTER="Set(0,3)"),"inv_alwaysTogether","mutant",10,"violated")
c("t04-jitter-mut-gap","p05_retry",RY_BASE,dict(JITTER="Set(0,3)"),"inv_gapPreserved","mutant",10,"violated")

# PULSE_LIMIT и пульс
c("s01-rules-conflict","p05_stall",ST_BASE,dict(),"inv_rulesAgree","property",12,"violated")
c("s01b-rules-conflict-strict","p05_stall",ST_BASE,dict(),"inv_rulesAgreeStrict","property",12,"violated")
c("s01w-shown","p05_stall",ST_BASE,dict(),"wit_shown","witness",12,"violated")
c("s02-visible-bound","p05_stall",ST_BASE,dict(),"inv_visible","property",16,"holds")
c("s02w-running-past-edge","p05_stall",ST_BASE,dict(),"wit_runningPastEdge","witness",16,"violated")
c("s02m-hb-blocked","p05_stall",ST_BASE,dict(BLOCK_HB="true"),"inv_visible","mutant",16,"violated")
c("s03-no-exceed-control","p05_stall",ST_BASE,dict(DURS="Set(19)"),"inv_rulesAgree","control",12,"holds")
c("s03w-short-completes","p05_stall",ST_BASE,dict(DURS="Set(19)"),"wit_noExceed","witness",10,"violated")

# симулятор rust для быстрого сверху-вниз (не доказательство, контроль непротиворечия шагов на длинных трассах)
c("sim01-budget-long","p05_pass",PASS_BASE,dict(PASS_BOUND=60),"inv_passBounded","control",400,"holds",tool="rust",samples=2000)
c("sim02-m1-long","p05_pass",PASS_BASE,dict(KINDS='Set("OK")',REFUSE_HEAD=2,REFUSAL_FAIL="true"),"inv_behindCopied","control",400,"holds",tool="rust",samples=2000)

FILTER = sys.argv[1] if len(sys.argv) > 1 else ""

def args2(cfg):
    return ", ".join(f"{k}={v}" for k, v in cfg.items() if not k.startswith("__"))

def ov_string(ov):
    return ";".join(f"{k}={str(v).replace(chr(34),'')}" for k, v in sorted(ov.items()))

def main():
    os.makedirs(os.path.join(HOME, "cfg"), exist_ok=True)
    for item in C:
        cfg = dict(item["base"]); cfg.update(item["ov"])
        item["mod"] = "cfg_" + item["id"].replace("-", "_")
        item["cfgfile"] = "cfg/" + item["id"] + ".qnt"
        with open(os.path.join(HOME, item["cfgfile"]), "w", encoding="utf-8") as w:
            w.write(f'// Конфигурация запуска {item["id"]} (генерируется run.py)\nmodule {item["mod"]} {{\n  import {item["f"]}({args2(cfg)}).* from "../{item["f"]}"\n}}\n')
    rows = []
    path = os.path.join(HOME, "results.tsv")
    logp = os.path.join(HOME, "run.log")
    os.makedirs(os.path.join(HOME, "runs"), exist_ok=True)
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                existing[r["id"]] = r
    with open(logp, "a", encoding="utf-8") as lg:
        for item in C:
            if FILTER and not re.search(FILTER, item["id"]):
                continue
            if os.path.exists(HOLD):
                lg.write("HOLD: остановка новых запусков\n"); print("HOLD"); break
            i = item["id"]
            out = os.path.join(HOME, "runs", i + ".log")
            if item["tool"] == "apalache":
                cmd = ["quint", "verify", item["cfgfile"], "--main=" + item["mod"], "--invariant=" + item["inv"],
                       "--max-steps=" + str(item["steps"]), "--server-endpoint=" + ENDPOINT, "--verbosity=1"]
            else:
                cmd = ["quint", "run", item["cfgfile"], "--main=" + item["mod"], "--invariant=" + item["inv"],
                       "--max-steps=" + str(item["steps"]), "--max-samples=" + str(item["samples"]),
                       "--backend=rust", "--verbosity=1"]
            t = time.time()
            try:
                r = subprocess.run(cmd, cwd=HOME, env=ENV, capture_output=True, text=True, timeout=400)
                text = r.stdout + r.stderr
            except subprocess.TimeoutExpired as e:
                text = "TIMEOUT\n" + str(e.stdout or "") + str(e.stderr or "")
            secs = round(time.time() - t, 1)
            with open(out, "w", encoding="utf-8") as o:
                o.write(" ".join(cmd) + "\n" + text)
            if "No violation found" in text:
                actual = "holds"
            elif "[violation]" in text or "Invariant violated" in text:
                actual = "violated"
            elif "TIMEOUT" in text:
                actual = "timeout"
            else:
                actual = "error"
            row = dict(id=i, module=item["f"], invariant=item["inv"], kind=item["kind"], tool=item["tool"],
                       max_steps=item["steps"], samples=item["samples"],
                       overrides=ov_string(item["ov"]) or "base", expect=item["expect"], actual=actual,
                       match=str(actual == item["expect"]).lower(), secs=secs, file=item["f"] + ".qnt")
            existing[i] = row
            lg.write(f"{time.strftime('%H:%M:%S', time.gmtime())} {i} {item['inv']} {actual} expect={item['expect']} {secs}s\n"); lg.flush()
            print(i, actual, "expect", item["expect"], secs, flush=True)
    cols = ["id","module","invariant","kind","tool","max_steps","samples","overrides","expect","actual","match","secs","file"]
    order = [it["id"] for it in C]
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        wr.writeheader()
        for i in order:
            if i in existing:
                wr.writerow(existing[i])

if __name__ == "__main__":
    main()
