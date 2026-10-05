"""What an older epoch means in each subsystem of the VMS, as its spec says it — the VMS's half of
`test_epoch_meaning.py`, whose platform half (the default, and a spec that says otherwise) is proved there."""
from vms.config import DET_SPEC, DETJOB_SPEC, SPEC


def test_the_default_is_what_every_subsystem_but_the_scan_says():
    assert DETJOB_SPEC.older_epochs == "earlier-run"
    for spec in (SPEC, DET_SPEC):
        assert spec.older_epochs == "fenced"
