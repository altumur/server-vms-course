"""Fill the accepted P01.247 drafts and check their delta against P01.251/P01.181.

Usage: python3 -I build_task.py <M commit> <local M passport> <task evidence dir>
This prepares files only; no task or candidate is launched.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
INBOX = HERE.parent
M, passport_arg, evidence_arg = sys.argv[1:4]
passport, evidence = Path(passport_arg), Path(evidence_arg)
sha = hashlib.sha256(passport.read_bytes()).hexdigest()
draft = INBOX / "2026-11-11-P01.247-задание-попытки-7-черновик"
argv = [sys.executable, "-I", str(draft / "fill_pair.py"), "--m", M,
        "--passport-sha256", sha, "--passport", str(passport), str(HERE)]
subprocess.run(argv, check=True)
task = json.loads((HERE / "task-attempt7.json").read_bytes())
# P01.254 note, 2026-11-12T09:08:23Z; P01.260 accepted at 10:46:33Z.
task["miniswe_design_max"] = 32000
task["miniswe_plan_idle_steps"] = 3
(HERE / "task-attempt7.json").write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n")


def spec_only_control(text):
    """Owner decision ADR-0133(76): Opus receives M and its task, without check."""
    lines = []
    for line in text.splitlines():
        if line.startswith("This is generation only."):
            line = ("This is generation only. Write and run your own build, tests and checks inside your working tree. "
                    "The finished candidate is judged separately after generation. Do not replace required product behavior "
                    "with adapter answers or hard-coded examples. All implementation, auxiliary code and tests are your work. "
                    "SPEC_VERSION identifies the immutable M input.")
        elif line.startswith("For each learning stage,"):
            line = ("For each learning stage, implement its stated goal and norms. The source stage names/goals/norm references "
                    "define the progression. Keep the full implementation and tests coherent across all eleven stages. "
                    "Use the public pinned Go dependencies with the supplied offline module cache. Produce a buildable complete "
                    "candidate and tests exercising its behavior; tests that only check a stub are insufficient for your implementation goal.")
        elif line.startswith("- The command `check`"):
            continue
        elif line.startswith("- If, by your reading of M, a gate"):
            line = "- If M is silent or ambiguous, record the place, question and your choice in work/GUESSES.md, then continue."
        elif "The lesson files a generator is given in full at the start are:" in line:
            line = line.replace("The lesson files a generator is given in full at the start are:",
                                "Read these files in M; read each norms file by its Index:")
        elif line.startswith("Working notes and work rules ("):
            line = 'Working notes and work rules (work/ is "$WORK"):'
        lines.append(line)
    result = "\n".join(lines) + "\n"
    assert "The command `check`" not in result and "a gate demands" not in result
    return result


control = HERE / "CONTROL-TASK-attempt7.md"
control.write_text(spec_only_control(control.read_text()))
assert (HERE / "PROMPT-attempt7.txt").read_bytes() == task["prompt"].encode()
expected = {"/name", "/specs", "/specs_sha", "/seed_files/SPEC_VERSION",
            "/stages/m_passport/path", "/stages/m_passport/sha256",
            "/miniswe_design_max", "/miniswe_plan_idle_steps"}


def flatten(value, path=""):
    if isinstance(value, dict):
        return {k: v for name, child in value.items()
                for k, v in flatten(child, path + "/" + name).items()}
    return {path: value}


checks, rows = {}, []
for old_id, old_dir in [("P01.251", "2026-11-12-P01.251-пара-и-задание"),
                        ("P01.181", "2026-11-12-P01.181-задание-попытки-7")]:
    previous = INBOX / old_dir
    old = json.loads((previous / "task-attempt7.json").read_bytes())
    a, b = flatten(old), flatten(task)
    changed = {k: {"before": a.get(k), "after": b.get(k)}
               for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    assert set(changed) == expected, changed
    assert old["prompt"] == task["prompt"]
    old_control = (previous / "CONTROL-TASK-attempt7.md").read_bytes()
    new_control = (HERE / "CONTROL-TASK-attempt7.md").read_bytes()
    assert spec_only_control(old_control.replace(old["specs_sha"].encode(), M.encode()).decode()).encode() == new_control
    checks[old_id] = {"changed_fields": changed, "prompt_equal": True,
                      "control_SPEC_VERSION_and_owner_ADR0133_76": True}
    rows += [f"| {old_id} | `{k}` | `{json.dumps(v['before'], ensure_ascii=False)}` | "
             f"`{json.dumps(v['after'], ensure_ascii=False)}` |"
             for k, v in sorted(changed.items())]

assert task["generation_only"] is True
assert not ({"judge", "judge_profile", "judge_input", "j_input"} & task.keys())
assert task["max_input_tokens"] == 150000000 and task["max_active_hours"] == 24
assert task["stall_rounds"] == 3
assert task["miniswe_steps"] == 60 and task["miniswe_round_max_input_tokens"] == 6000000
assert task["miniswe_plan_steps"] == 30
assert task["miniswe_plan_round_max_input_tokens"] == 6000000
assert task["miniswe_plan_round"] is True and task["miniswe_stable_prefix"] is True
assert task["miniswe_design_max"] == 32000 and task["miniswe_plan_idle_steps"] == 3
assert all(task["stages"][key] is True for key in
           ["norm_trace", "norm_trace_mutation", "norm_trace_mode", "stage_tests", "profile_probe"])
files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
         [HERE / "task-attempt7.json", HERE / "CONTROL-TASK-attempt7.md", HERE / "PROMPT-attempt7.txt"]}
result = {"task": "P01.254", "M": M, "passport": str(passport), "passport_sha256": sha,
          "fill_pair_argv": argv, "comparisons": checks, "files_sha256": files, "OK": True}
(evidence / "TASK-CHECK.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
lines = ["# P01.254 — привязка задания попытки 7", "",
         "`fill_pair.py` P01.247 изменил шесть полей привязки пары. Затем по note Архитектора",
         "добавлены `miniswe_design_max: 32000` и `miniswe_plan_idle_steps: 3`: P01.260 принята до среза.",
         "Против P01.251 и P01.181 изменены ровно восемь полей; все остальные значения JSON совпадают.", "",
         "| Основа | Поле | До | После |", "|---|---|---|---|", *rows, "",
         "`PROMPT-attempt7.txt` побайтно прежний. CONTROL: новый SPEC_VERSION и исполнение ADR-0133 доп. (76):",
         "сняты команда `check` и обратная связь ворот; контроль Opus получает M и задание, пишет свои проверки сам.",
         "Список файлов теперь назван чтением из M, без обещания вставить все тексты в начальный запрос.",
         "Бюджет 150 млн входа с кэшем / 24 часа, 11 этапов, правила окончания и прежние пределы раундов сохранены.",
         "J и суд в задание генерации не входят. Данные для нового движка — J-вход пары этой задачи.", "",
         "Дифф с попыткой 6 и основания параметров —",
         "[таблица P01.181](../2026-11-12-P01.181-задание-попытки-7/DIFF-attempt6-attempt7.md).", "",
         "Полная машинная сверка полей — `/home/pilot/run-p01254-task-20261112/TASK-CHECK.json`.", ""]
(HERE / "DIFF-TASK.md").write_text("\n".join(lines))
print(json.dumps({"OK": True, "files_sha256": files}, indent=1))
