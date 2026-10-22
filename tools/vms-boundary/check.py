#!/usr/bin/env python3
"""Граница комплекта VMS (ADR-0090 доп. (1), (6) п. 8, (7) п. 4): что сессии VMS вправе коммитить.

  check.py staged                 pre-commit: ветка vms/<тема>, пути индекса — из белого списка сессии
  check.py msg <файл сообщения>    commit-msg: трейлер `Session: <сессия>` этой сессии
  check.py range <a>..<b> [--tree] вехи «Архитектора»: каждый коммит диапазона; с --tree (pre-push) ещё и
                                  каждый коммит несёт трейлер сессии дерева

Сессия дерева — `git config vms.session` (ставит install.sh). Диапазон проверяется и без сессии: коммит с трейлером
`Session:` сессии VMS (sessions.txt) — только пути её белого списка; любой коммит, задевающий `Source/vms/`, — отказ
(байты свидетеля заморожены со старта, их не правит никто). Граница — от ошибки, не от умысла (`--no-verify`).
"""

import re
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPEN = ("VMS/", "М10B_ServerVMS/", "М12A_Domain/", "М12B_DomainVMS/", "М13_Observability/", "М14_VendorVMS/")
INBOX = re.compile(r"decisions/inbox/[0-9]{4}-[0-9]{2}-[0-9]{2}-(?:запрос-vms|решение-владельца-vms)-[^/]+\.md")
FROZEN = "Source/vms/"


def nfc(text):
    return unicodedata.normalize("NFC", text)


def git(*args, check=True):
    out = subprocess.run(["git", *args], capture_output=True, check=False)
    if check and out.returncode:
        raise SystemExit(f"vms-boundary: git {' '.join(args)}: {out.stderr.decode(errors='replace').strip()}")
    return out.stdout.decode()


def sessions():
    return [nfc(line.strip()) for line in (HERE / "sessions.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def own_log(session):
    return "ХОД-" + session.replace(" ", "-") + ".md"


def allowed(path, session):
    """Путь, который сессия VMS вправе менять (белый список доп. (1) с правками доп. (2), (6) п. 8)."""
    path = nfc(path)
    return path.startswith(OPEN) or path == own_log(session) or bool(INBOX.fullmatch(path))


def paths_of(diff):
    return [nfc(p) for p in diff.split("\0") if p]


def session_of_tree():
    session = nfc(git("config", "--get", "vms.session", check=False).strip())
    if not session:
        raise SystemExit("vms-boundary: у дерева нет vms.session — поставьте хуки tools/vms-boundary/install.sh <сессия>")
    if session not in sessions():
        raise SystemExit(f"vms-boundary: {session!r} нет в tools/vms-boundary/sessions.txt")
    return session


def staged():
    session = session_of_tree()
    branch = git("symbolic-ref", "--short", "-q", "HEAD", check=False).strip()
    errors = []
    if not branch.startswith("vms/"):
        errors.append(f"коммит сессии VMS идёт с ветки vms/<тема>, а не {branch or 'отсоединённой HEAD'}")
    for path in paths_of(git("diff", "--cached", "--name-only", "--no-renames", "-z")):
        if not allowed(path, session):
            errors.append(f"закрытый путь для «{session}»: {path}")
    return errors


def message(path):
    session = session_of_tree()
    text = Path(path).read_text(encoding="utf-8")
    said = trailers(text)
    if session not in said:
        return [f"нет трейлера «Session: {session}» (ADR-0090 доп. (1)); есть: {said or 'ни одного'}"]
    if len(said) > 1:
        return [f"в коммите один трейлер Session, а их {said}"]
    return []


def trailers(text):
    parsed = subprocess.run(["git", "interpret-trailers", "--parse"], input=text.encode(), capture_output=True).stdout
    return [nfc(m.group(1).strip()) for m in re.finditer(r"(?m)^Session:\s*(.+)$", parsed.decode())]


def commit_range(spec, tree=None):
    errors = []
    known = set(sessions())
    for sha in git("rev-list", "--no-merges", spec).split():
        said = trailers(git("log", "-1", "--format=%B", sha))
        paths = paths_of(git("diff-tree", "--no-commit-id", "--name-only", "--no-renames", "-r", "-z", sha))
        short = sha[:9]
        for path in paths:
            if path.startswith(FROZEN):
                errors.append(f"{short}: Source/vms/ заморожен со старта VMS (ADR-0090 доп. (7) п. 4): {path}")
        if tree is not None and said != [tree]:
            errors.append(f"{short}: коммит дерева «{tree}» несёт один трейлер «Session: {tree}», а не {said or 'ни одного'}")
        for session in said:
            if session not in known:
                continue
            for path in paths:
                if not allowed(path, session):
                    errors.append(f"{short}: закрытый путь для «{session}»: {path}")
    return errors


def main(argv):
    if len(argv) >= 2 and argv[1] == "staged":
        errors = staged()
    elif len(argv) == 3 and argv[1] == "msg":
        errors = message(argv[2])
    elif len(argv) == 3 and argv[1] == "range":
        errors = commit_range(argv[2])
    elif len(argv) == 4 and argv[1] == "range" and argv[3] == "--tree":
        errors = commit_range(argv[2], session_of_tree())
    else:
        print(__doc__)
        return 2
    for error in errors:
        print("vms-boundary:", error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
