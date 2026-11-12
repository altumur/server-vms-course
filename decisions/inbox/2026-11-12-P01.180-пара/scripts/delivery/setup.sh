set -eu
# P01.180 delivery (as P02.26 / P01.121.1 + P01.131.2): new M be48405e with PASSPORT-M.json, new J-input 9daca227. Runs as root (representative). Prepared, not run.
# Only new directories; existing M, J-inputs, work and results are inventoried before and after and must not change.
P=/home/pilot/run-p01180-pair-20261112; R=/srv/b11-isolation
MS=$P/pair-41a9493fb08c/M.git; MC=be48405e645b49985d35efc42b6d61c2f304c4d8; MT=6bee0529ff68211f23f7622cd79786b708be95d0; MREF=refs/heads/model
PM=$P/passport/PASSPORT-M-be48405e645b.json; PMSHA=0b44f9e2e20cda6f4a2ad5dbab58ae93f346bd96cf559bad9a14e38e2c42ef01
JS=$P/ji-41a9493fb0; JC=9daca227dbc08ce3d4a14c6d47c6ea3f94e55034; JT=8df57f6ee415205c4db08d99013214c7ec27b39d; JREF=refs/heads/judge-input
JPSHA=e4f43d403a2a2093e4b3fd72f1cc59c4b00f9a803c807c16684322d8a715766d
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
[ "$BEFORE" = "$AFTER" ] && echo "existing_unchanged yes" || { echo "existing_unchanged NO"; diff <(echo "$BEFORE") <(echo "$AFTER") || true; }
[ "$PAR" = "$(stat -c '%U:%G %a' $R/model-specs $R/judge-input)$(getfacl -cp $R/model-specs $R/judge-input | sha256sum)" ] && echo "parents_unchanged yes" || echo "parents_unchanged NO"
[ "$TV" = "$(sha256sum < /etc/b11-isolation/trial-views.tsv)" ] && echo "trial_views_unchanged yes" || echo "trial_views_unchanged NO"
echo "J 605f12bb in new M objects: $(G --git-dir=$MD/M.git cat-file -e 605f12bb9b4664e5e7e9517722fcf5464faf219b 2>/dev/null && echo PRESENT || echo absent)"
python3 -B $P/delivery/verify.py | tee $P/delivery/verify.out
python3 -B $P/operator/check_m_passport.py $MD/PASSPORT-M.json $MD/tree $MC | tee $P/delivery/passport-on-stand.out
echo ok
