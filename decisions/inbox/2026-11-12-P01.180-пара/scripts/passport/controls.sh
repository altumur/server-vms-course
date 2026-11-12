#!/bin/bash
# P01.180: controls of the M passport (as P02.26 passport/controls.out); spec roots from git archive of M and J.
set -u
W=/home/pilot/run-p01180-pair-20261112; P=$W/pair-41a9493fb08c; M=be48405e645b49985d35efc42b6d61c2f304c4d8; J=605f12bb9b4664e5e7e9517722fcf5464faf219b
PP=$W/passport/PASSPORT-M-${M:0:12}.json; CK="python3 -I $W/operator/check_m_passport.py"
T=$(mktemp -d "$W/passport/ctl.XXXX")
mk() { mkdir -p "$T/$1"; git --git-dir="$2" archive --format=tar "$3" | tar -x -C "$T/$1"; }
run() { echo "== $1"; shift; "$@" > "$T/out" 2>&1; rc=$?; head -4 "$T/out"; n=$(wc -l < "$T/out"); [ "$n" -gt 4 ] && tail -1 "$T/out"; echo "exit $rc"; }
mk m "$P/M.git" $M; run "M as is (want OK, exit 0)" $CK "$PP" "$T/m" $M
mk j "$P/J.git" $J; run "J (want red: not in the M passport)" $CK "$PP" "$T/j" $M
mk bad "$P/M.git" $M
printf 'x' >> "$T/bad/Platform/01-store/forms/stages.tsv"
rm "$T/bad/Platform/01-store/forms/code-rules.tsv"
ln -s stages.tsv "$T/bad/Platform/01-store/forms/link.md"
run "byte change, missing file, symlink (want red)" $CK "$PP" "$T/bad" $M
mk extra "$P/M.git" $M
git --git-dir="$P/J.git" show $J:Platform/01-store/forms/extra.scenarios.tsv > "$T/extra/Platform/01-store/forms/extra.scenarios.tsv"
run "extra J-only extra.scenarios.tsv (want red)" $CK "$PP" "$T/extra" $M
run "wrong M bf8462085c08 of P02.26 (want red)" $CK "$PP" "$T/m" bf8462085c08c5cd5f6b4cce3ca3580ebd74ffae
rm -rf "$T"
