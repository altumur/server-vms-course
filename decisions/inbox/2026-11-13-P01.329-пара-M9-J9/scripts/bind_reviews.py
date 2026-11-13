"""Bind eight new M/J classifications to actual different-provider reviews."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
import subprocess
import sys

B=Path(sys.argv[1]).resolve();C=(B/'C.txt').read_text().strip()
T=Path('/home/pilot/cammeta-sessions/tasks')
delta=json.loads((B/'FILTER-DELTA.json').read_text())
assert delta['to']==C and not delta['changed'] and not delta['removed']
paths={
 'P01.324': {'Platform/01-store/acceptance/3/inputs/member-join-other.json':('judge_only','include'),'Platform/01-store/acceptance/3/inputs/member-leave-other-follower.json':('judge_only','include'),'Platform/01-store/acceptance/3/inputs/member-leave-other.json':('judge_only','include')},
 'P01.320': {'Platform/01-store/qualification/stand-procedures.md':('judge_only','include'),'Platform/01-store/ru/qualification/stand-procedures.md':('judge_only','exclude')},
 'P03.35': {'Platform/03-worker/vectors/fetched/README.md':('model_and_judge','include'),'Platform/03-worker/vectors/fetched/cases.tsv':('judge_only','include'),'Platform/03-worker/ru/vectors/fetched/README.md':('judge_only','exclude')},
}
expected={p:v for values in paths.values() for p,v in values.items()}
assert {r['path']:(r['M'],r['JI']) for r in delta['added']}==expected
with Path('/home/pilot/cammeta-sessions/sessions.tsv').open() as f:
    rows=[dict(zip(('name','handle','model'),r[:3])) for r in csv.reader(f,delimiter='\t') if r and r[0]=='architect']
assert len(rows)==1 and rows[0]['model']=='Claude';identity=rows[0]
reviews=[]
for name in paths:
    author='\n'.join(line for line in (T/(name+'.yaml')).read_text().splitlines() if line.startswith(('id:','provider:')))+'\n'
    (B/'reviews'/(name+'-author.txt')).write_text(author)
    accepted=json.loads((B/'reviews'/(name+'-accepted.json')).read_text());assert accepted['status']=='accepted'
    subprocess.run(['git','--git-dir',str(B/'source.git'),'merge-base','--is-ancestor',accepted['commit'],C],check=True)
    if name in ('P01.320','P01.324'):
        assert 'provider: claude' in author
        # Actual Codex semantic review of this task, separate from the Claude acceptance.
        text='''# P01.329 — Codex-обзор двух классификаций P01.320\n\nАвтор файлов P01.320 — Anthropic (provider: claude в метаданных задачи). Обзор классификации выполнил OpenAI Codex в P01.329, на точном C, записанном в C.txt.\n\nПрочитаны qualification/stand-procedures.md и его русский перевод; сопоставлены начало, разделы среды, поставщиков D7, процедур и контролей. Английский файл задаёт процедуры квалификации и среду стенда, без нового исхода кандидата; это Q, который по действующему правилу находится вне M. Русский файл — производный перевод Q, вне M и J.\n\nПроверены обе добавленные записи в forms/export.json и запись английского источника в qualification-input-filter.json. Для en: M judge_only, J include; для ru: M judge_only, J exclude. Эти роли согласованы с правилом входа Q и областью файлов. Результат обзора классификации — PASS. Обзор не проверяет работоспособность поставщиков на ВМ и не заменяет приём процедуры; её принятие подтверждает отдельная квитанция P01.320.\n'''
        if name=='P01.324':
            text='''# P01.329 — Codex-обзор трёх классификаций P01.324\n\nАвтор P01.324 — Anthropic (provider: claude в метаданных задачи). Обзор классификации выполнил OpenAI Codex в P01.329 на точном C из C.txt.\n\nПрочитаны member-join-other.json, member-leave-other.json и member-leave-other-follower.json; сверены ссылки сценария 35 главы 3 и добавленные записи forms/export.json. Это конкретные JSON-входы стенда для join/leave чужого id: они не интерфейс и не нормы реализации. Всем трём файлам соответствует M judge_only и J include. Классификация согласована с правилом: сценарии и их конкретные входы модели-писателю не даются, а судья получает их для проверки. Результат обзора классификации — PASS. Полноту сценария и нормы этот узкий обзор не оценивает; принятие изменения подтверждает отдельная квитанция P01.324.\n'''
        review=name+'-classification-review-Codex.md';(B/'reviews'/review).write_text(text)
        ap,rp='Anthropic','OpenAI'
        evidence='actual Codex classification review in P01.329; task provider claude'
    else:
        assert 'provider: codex' in author and accepted['window']==identity['handle']
        (B/'reviews'/(name+'-reviewer.json')).write_text(json.dumps({'source':'/home/pilot/cammeta-sessions/sessions.tsv','fields':identity,'accepted_window':accepted['window'],'window_match':True,'provider':'Anthropic'},indent=1)+'\n')
        review=name+'-accepted-review.json';shutil.copyfile(B/'reviews'/(name+'-accepted.json'),B/'reviews'/review)
        ap,rp='OpenAI','Anthropic';evidence='accepted.window equals architect Claude handle; accepted receipt is review record'
    reviews.append({'task':name,'records':sorted(paths[name]),'author_provider':ap,'reviewer_provider':rp,'provider_evidence':evidence,'accepted_receipt':'reviews/'+name+'-accepted.json','review':'reviews/'+review,'review_sha256':hashlib.sha256((B/'reviews'/review).read_bytes()).hexdigest()})
result={'C':C,'baseline':'P01.299 accepted pair; all unchanged semantic records inherited','delta_sha256':hashlib.sha256((B/'FILTER-DELTA.json').read_bytes()).hexdigest(),'deltas':reviews,'filter_author_provider':'per-record actual provider in deltas','filter_reviewer_provider':'different actual provider per record in deltas','all_delta_records_covered':True}
(B/'FILTER-REVIEWS.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
print(json.dumps({'C':C,'reviewed_added_records':len(expected)},indent=1))
