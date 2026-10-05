"""The VMS — the first subsystem the platform hosts.

    archive.py      the archive: volumes of ObjectStorage through the host's obsd — streams, the index, the ring
    worker.py       vmsworker — DriverPack as the worker: N pipelines against an assignment
    controller.py   the VMS's words over the platform's controller (the process is `w2c-controller@vms`)
    console.py      the one-box console: the platform's SpecConsole over the VMS spec, plus /timeline, /export, /segment and the WHEP door
    gateway.py      the live gateway — the second subsystem's worker: a camera's fan-out as the unit, viewers as the capacity
    detworker.py    the detector worker — the second subsystem's worker: a model on a camera as the unit, streams as the capacity
    det.subsystem.yaml    the third subsystem, as a spec
    live.subsystem.yaml   the second subsystem, as a spec

Nothing here imports from platform/ except through its public interfaces,
and nothing in platform/ imports from here.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # __init__.py — the package docstring: what `vms` is, the first subsystem the platform hosts
#
# **Role in the module.** No code, only the docstring. It names the VMS as the *first subsystem* — the thing
# the platform (`w2cplatform/`) was built to host without knowing what it is — and gives a one-line map of
# the package: `archive.py` (the archive: volumes of ObjectStorage through the host's `obsd` — streams, the index, the ring), `worker.py`
# (vmsworker — DriverPack as the worker, N pipelines against an assignment, over the platform's reconcile helper),
# `controller.py` (the VMS's words over the platform's controller, whose process is `w2c-controller@vms`) and `console.py` (the one-box console: the
# platform's `SpecConsole` over the VMS spec, plus `/timeline`, `/export` and `/segment`).
#
# The last sentence fixes the dependency direction that
# `tests/test_lesson1_platform.py::test_the_platform_knows_nothing_about_its_subsystems` enforces: `vms/` imports
# from the platform only through its public interfaces (`Worker`, `SpecController`, `SpecConsole`,
# `EventLog`, the store Protocols), and nothing in the platform imports from here.
#
# ## Module-level names
# None, and no imports: `import vms` pulls in nothing. `python3 -m vms …` runs `__main__.py`, which imports
# the modules it needs explicitly.
#
# ## Notes
# - The docstring still says `platform/` where the directory is `w2cplatform/` (renamed because Python's
#   standard library owns `platform`; see `w2cplatform/__init__.py`).
# - `config.py` and `vms.subsystem.yaml` are not listed in the docstring's map; they are the schema the
#   controller and console run from (see `config.py`, `vms.subsystem.yaml`).
# ================================================================================================
