"""What an older epoch means in each subsystem of the VMS, as its spec says it — the VMS's half of
`test_epoch_meaning.py`, whose platform half (the default, and a spec that says otherwise) is proved there."""
from vms.config import DET_SPEC, DETJOB_SPEC, SPEC


def test_the_default_is_what_every_subsystem_but_the_scan_says():
    assert DETJOB_SPEC.older_epochs == "earlier-run"
    for spec in (SPEC, DET_SPEC):
        assert spec.older_epochs == "fenced"


def test_an_epoch_of_the_generation_after_a_recover_reads_in_every_name_the_vms_parses():
    """ADR-0070 (the product's 980547a: recproc, recact, vmscam): after `configstore recover` the epochs are 2^32 and
    above, and a recording's stream `<unit>/e4294967297`, its backfill and a segment `e4294967297/<from>-<to>.mp4` read
    as the number they are."""
    from vms.archive import parse_stream, stream_name
    from vms.footage import segment_piece
    big = (1 << 32) + 1
    assert parse_stream(stream_name("7", big)) == ("7", big, "live")
    assert parse_stream(stream_name("7", big, backfill=True)) == ("7", big, "backfill")
    assert segment_piece([f"e{big}", "1000-2000.mp4"]) == (big, 1.0, 2.0, "live")
