"""P01.247: fill the pair's hashes into the attempt-7 drafts (task-attempt7.draft.json, CONTROL-TASK-attempt7.draft.md).
Only the <PAIR_*> marks change; any other byte stays. Refuses a malformed hash and a mark left unfilled.
Run: python3 -I fill_pair.py --m <M commit, 40 hex> --passport-sha256 <64 hex> [--passport <local copy of PASSPORT-M.json>] <out dir>
With --passport the file's sha256 must equal --passport-sha256 and its text must name the M commit."""
import argparse, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = {"task-attempt7.draft.json": "task-attempt7.json", "CONTROL-TASK-attempt7.draft.md": "CONTROL-TASK-attempt7.md"}

ap = argparse.ArgumentParser()
ap.add_argument("--m", required=True)
ap.add_argument("--passport-sha256", required=True)
ap.add_argument("--passport")
ap.add_argument("out")
a = ap.parse_args()
if not re.fullmatch(r"[0-9a-f]{40}", a.m):
    sys.exit("--m: 40 lowercase hex expected")
if not re.fullmatch(r"[0-9a-f]{64}", a.passport_sha256):
    sys.exit("--passport-sha256: 64 lowercase hex expected")
if a.passport:
    b = open(a.passport, "rb").read()
    if hashlib.sha256(b).hexdigest() != a.passport_sha256:
        sys.exit("--passport: sha256 differs from --passport-sha256")
    if a.m.encode() not in b:
        sys.exit("--passport: the passport does not name the M commit")
marks = {"<PAIR_M_SHA12>": a.m[:12], "<PAIR_M_SHA>": a.m, "<PAIR_M_PASSPORT_SHA256>": a.passport_sha256}
os.makedirs(a.out, exist_ok=True)
for src, dst in DRAFTS.items():
    text = open(os.path.join(HERE, src), encoding="utf-8").read()
    for k, v in marks.items():          # no mark is a substring of another mark
        text = text.replace(k, v)
    left = sorted(set(re.findall(r"<PAIR_[A-Z0-9_]+>", text)))
    if left:
        sys.exit(f"{src}: marks left unfilled: {left}")
    if dst.endswith(".json"):
        t = json.loads(text)
        assert t["specs_sha"] == a.m and t["seed_files"]["SPEC_VERSION"] == a.m + "\n"
        assert t["stages"]["m_passport"]["sha256"] == a.passport_sha256
    p = os.path.join(a.out, dst)
    open(p, "w", encoding="utf-8").write(text)
    print(hashlib.sha256(text.encode()).hexdigest(), p)
