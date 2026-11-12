# PREPARED ONLY. Execute through the representative/ops103 after their authorization.
set -euo pipefail
# P01.254 delivery (as P02.26 / P01.121.1 + P01.131.2): new M 847ac9d1 with PASSPORT-M.json, new J-input 2fc27202. Runs as root (representative). Prepared, not run.
# Only new directories; existing M, J-inputs, work and results are inventoried before and after and must not change.
P=/home/pilot/run-p01254-pair-20261112-r3; R=/srv/b11-isolation
MS=$P/pair-298e28fda4b9/M.git; MC=847ac9d1fb36bd1153450f99ddc4805c2609877e; MT=ebb5e05f2afc373a6e85b56ffd747f2d1b5d04dc; MREF=refs/heads/model
PM=$P/passport/PASSPORT-M-847ac9d1fb36.json; PMSHA=6bd5488d483ac38d848cbe21eed7099b91729dec3efa2234b766bd872cf96c8f
JS=$P/ji-298e28fda4b9; JC=2fc272022ff073aaa75ce6dac1b953286c0d8b3d; JT=519b33a006a188dbd80af4ebdc95f92e521aa6aa; JREF=refs/heads/judge-input
JPSHA=f148e74fde90d8c0d748156869e603cddd7fb4e7087ea87ac8bbbff74fe996ed
MD=$R/model-specs/$MC; JD=$R/judge-input/$JC
G() { git -c safe.directory='*' "$@"; }
for d in "$MD" "$JD"; do [ ! -e "$d" ] || { echo "EXISTS $d"; exit 3; }; done
[ "$(sha256sum $JS/PASSPORT-JI.json | cut -d' ' -f1)" = $JPSHA ]; [ "$(sha256sum $PM | cut -d' ' -f1)" = $PMSHA ]; echo passports_ok
[ "$(G --git-dir=$MS rev-parse $MREF)" = $MC ]; [ "$(G --git-dir=$MS rev-parse $MC^{tree})" = $MT ]; [ "$(G --git-dir=$MS for-each-ref --format='%(refname)')" = $MREF ]; [ ! -e $MS/hooks ]; echo "M source ok"
[ "$(G --git-dir=$JS/JI.git rev-parse $JREF)" = $JC ]; [ "$(G --git-dir=$JS/JI.git rev-parse $JC^{tree})" = $JT ]; [ "$(G --git-dir=$JS/JI.git for-each-ref --format='%(refname)')" = $JREF ]; [ ! -e $JS/JI.git/hooks ]; echo "JI source ok"
inv(){ find "$@" -printf '%p %m %U %G %s %T@\n' 2>/dev/null | sort | sha256sum | cut -c1-16; }
BEFORE=$(for d in $R/model-specs/* $R/judge-input/* $R/model-work $R/cycle-results $R/hidden-*; do echo "$d $(inv $d)"; done)
PAR="$(stat -c '%U:%G %a' $R/model-specs $R/judge-input)$(getfacl -cp $R/model-specs $R/judge-input | sha256sum)"
TV=$(sha256sum < /etc/b11-isolation/trial-views.tsv)
# --- M (root:root 755/444, no ACL, as 1e07365a/d5bd29dd) + PASSPORT-M.json readable by cycle and model (P01.131.2)
install -d -o root -g root -m 755 "$MD"
cp -a --no-preserve=ownership $MS "$MD/M.git"
mkdir "$MD/tree"; G --git-dir="$MD/M.git" -c tar.umask=022 archive --format=tar $MC | tar -x -C "$MD/tree" --no-same-owner --no-same-permissions
install -o root -g root -m 444 $PM "$MD/PASSPORT-M.json"
chown -R root:root "$MD"; find "$MD" -type d -exec chmod 755 {} +; find "$MD/M.git" -type f -exec chmod 444 {} +; find "$MD/tree" -type f -perm /111 -exec chmod 555 {} +; find "$MD/tree" -type f ! -perm /111 -exec chmod 444 {} +
setfacl -R -b "$MD"
# --- J-input (root:b11-engine 750/440, ACL u:minimax:rX, as f11bf34d)
install -d -o root -g b11-engine -m 750 "$JD"
cp -a --no-preserve=ownership $JS/JI.git "$JD/JI.git"
mkdir "$JD/tree"; G --git-dir="$JD/JI.git" -c tar.umask=022 archive --format=tar $JC | tar -x -C "$JD/tree" --no-same-owner --no-same-permissions
chown -R root:b11-engine "$JD"; find "$JD" -type d -exec chmod 750 {} +; find "$JD/JI.git" -type f -exec chmod 440 {} +; find "$JD/tree" -type f -perm /111 -exec chmod 550 {} +; find "$JD/tree" -type f ! -perm /111 -exec chmod 440 {} +
setfacl -R -m u:minimax:rX "$JD"
echo "hooks_in_delivery M=$(ls -d $MD/M.git/hooks 2>/dev/null | wc -l) JI=$(ls -d $JD/JI.git/hooks 2>/dev/null | wc -l)"
for s in "$MD/M.git" "$MD/tree" "$JD/JI.git" "$JD/tree"; do echo "${s#$R/} d: $(find $s -type d -printf '%m %U:%G\n' | sort | uniq -c | tr '\n' ';') f: $(find $s -type f -printf '%m %U:%G\n' | sort | uniq -c | tr '\n' ';') l: $(find $s -type l | wc -l)"; done
stat -c '%U:%G %a %n' "$MD" "$MD/PASSPORT-M.json" "$JD" | sed "s#$R/##"
AFTER=$(for d in $(echo "$BEFORE" | cut -d' ' -f1); do echo "$d $(inv $d)"; done)
[ "$BEFORE" = "$AFTER" ] && echo "existing_unchanged yes" || { echo "existing_unchanged NO"; diff <(echo "$BEFORE") <(echo "$AFTER") || true; exit 1; }
[ "$PAR" = "$(stat -c '%U:%G %a' $R/model-specs $R/judge-input)$(getfacl -cp $R/model-specs $R/judge-input | sha256sum)" ] && echo "parents_unchanged yes" || { echo "parents_unchanged NO"; exit 1; }
[ "$TV" = "$(sha256sum < /etc/b11-isolation/trial-views.tsv)" ] && echo "trial_views_unchanged yes" || { echo "trial_views_unchanged NO"; exit 1; }
echo "J 0b34ab1b in new M objects: $(G --git-dir=$MD/M.git cat-file -e 0b34ab1bee38b72451cbcb4466feea6ab96d8da0 2>/dev/null && echo PRESENT || echo absent)"
python3 -B $P/delivery/verify.py | tee $P/delivery/verify.out
python3 -B $P/operator/check_m_passport.py $MD/PASSPORT-M.json $MD/tree $MC | tee $P/delivery/passport-on-stand.out
echo ok
