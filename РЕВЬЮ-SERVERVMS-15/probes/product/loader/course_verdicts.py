"""Probe 15/A: the course loader's verdict on every case of a directory.

usage: python course_verdicts.py <Source dir> <cases dir>
prints: <case>\t<ok|refused|crash>\t<message>
"""
import glob
import os
import sys

sys.path.insert(0, sys.argv[1])
from w2cplatform import catalog  # noqa: E402
from w2cplatform.spec import SubsystemSpec  # noqa: E402

for path in sorted(glob.glob(os.path.join(sys.argv[2], "*.subsystem.yaml"))):
    case = os.path.basename(path)[: -len(".subsystem.yaml")]
    saved = (dict(catalog._loaded), dict(catalog._files))
    try:
        s = SubsystemSpec.load(path)
        facts = []
        for n in ("feed_secret",):
            f = s.fields.get(n)
            if f is not None:
                facts.append(f"bound_to={list(f.bound_to)}")
        if "of" in s.fields:
            facts.append(f"of.fixed={s.fields['of'].fixed}")
        if "name" in s.fields:
            facts.append(f"name.required={s.fields['name'].required}")
        if "mode" in s.fields:
            facts.append(f"mode.enum={list(s.fields['mode'].enum)}")
        facts.append(f"requires={s.requires} servers={s.servers} tie_break={s.tie_break} id={s.id}")
        print(f"{case}\tok\t{' '.join(facts)}")
    except ValueError as e:
        print(f"{case}\trefused\t{str(e).replace(path+': ', '')[:220]}")
    except BaseException as e:  # noqa: BLE001
        print(f"{case}\tcrash\t{type(e).__name__}: {str(e)[:160]}")
    finally:
        with catalog._lock:
            catalog._loaded.clear(); catalog._loaded.update(saved[0])
            catalog._files.clear(); catalog._files.update(saved[1])
            catalog.version += 1
            catalog._derived.clear()
