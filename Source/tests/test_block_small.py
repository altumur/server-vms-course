"""A volume whose blocks are smaller than a group of pictures says so — in the recorder's heartbeat
(`objectstorage.block_small`) and on the page by rec's `servers.status` (ADR-0064; the product's `smallBlock`)."""
from __future__ import annotations

import tempfile

from w2cplatform.console import heartbeats
from vms import volumes
from vms.archive import SMALL_BLOCK, Archive
from vms.config import REC_SPEC
from tests.vmsconftest import TEST_BLOCK, TEST_QUOTA, TEST_READ, Box, obsd_session, recorder


def _formatted(path: str, block: int) -> None:
    """A volume at `path` formatted with `block`, its writer closed: as a box's card formatted before the rule was."""
    Archive("file://" + path, "old", TEST_QUOTA, "rec:old-format", obsd_session("old-format"), block=block,
            read=256 << 10).open().close()


def test_the_writer_works_with_the_volumes_own_block_or_its_setting_whichever_is_smaller():
    """The engine takes the smaller of the volume's block — fixed when it was formatted — and the writer's setting
    (the product's `effectiveSizes`): a volume formatted with 1 MiB blocks stays at 1 MiB under a recorder set to 4."""
    small = tempfile.mkdtemp(prefix="vol-small-")
    _formatted(small, 1 << 20)
    st = Archive("file://" + small, "old", TEST_QUOTA, "rec:old-again", obsd_session("old-again"), block=TEST_BLOCK,
                 read=TEST_READ).open()
    assert st.block_bytes == 1 << 20 < SMALL_BLOCK
    fresh = Archive("file://" + tempfile.mkdtemp(prefix="vol-fresh-"), "new", TEST_QUOTA, "rec:new", obsd_session("new"),
                    block=TEST_BLOCK, read=TEST_READ).open()
    assert fresh.block_bytes == TEST_BLOCK == SMALL_BLOCK


def test_a_recorder_on_a_volume_of_small_blocks_says_block_small_and_the_page_is_told_by_servers_status():
    """The recorder of a volume formatted with 1 MiB blocks says `objectstorage: {volume, block_bytes, block_small}` in
    every heartbeat — `block_small` the block's bytes, a number, so that `/servers` shows it (a `true` leaf is a garbled
    one, ADR-0064; «Архитектор» 2026-10-07); one on a volume of 4 MiB blocks, nothing refused, says its block and no
    `block_small`. rec's
    spec names the field for the page (`servers.status`, «блок тома меньше кадров видео, байт»), and the console shows it."""
    assert {"field": "objectstorage.block_small", "title": "блок тома меньше кадров видео, байт"} in \
        [{k: s[k] for k in ("field", "title")} for s in REC_SPEC.servers_status]
    for block, small in ((1 << 20, True), (TEST_BLOCK, False)):
        box = Box()
        path = tempfile.mkdtemp(prefix="vol-")
        _formatted(path, block)
        volumes.write(box.vars, {"name": "disk", "kind": "local", "server": "srv-1", "url": "file://" + path,
                                 "quota_bytes": TEST_QUOTA})
        r = recorder(box, "r-1", "srv-1", acl=False)
        r.lease_pass()
        assert r.volume == "disk" and r.store is not None
        r.heartbeat_once()
        said = heartbeats(box.objects, "rec")["r-1"].extra["objectstorage"]
        assert said["volume"] == "disk" and said["block_bytes"] == block, said
        assert said.get("block_small") == (block if small else None), said
        from w2cplatform.console import SpecConsole
        from w2cplatform.spec import SpecController
        rows = SpecConsole(SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall), wall=box.wall).servers()
        shown = [w.get("status", {}).get("objectstorage.block_small") for s in rows["servers"].values() for w in s["workers"]]
        assert shown == ([block] if small else [None]), rows


def test_a_volume_whose_engine_refused_a_group_of_pictures_too_large_says_block_small_whatever_its_block():
    """«Архитектор» 2026-10-07 (one rule on both sides): a block of 4 MiB or more is said small too once the engine has
    refused a sample `SEQUENCE_TOO_LARGE` since the writer was mounted — a 4K group of pictures that did not fit. Counted
    by the volume (`Archive.too_large`), and a writer mounted again starts the count again."""
    import os
    from vms.obsd import ObsdError, video
    box = Box()
    path = tempfile.mkdtemp(prefix="vol-")
    _formatted(path, TEST_BLOCK)
    volumes.write(box.vars, {"name": "disk", "kind": "local", "server": "srv-1", "url": "file://" + path,
                             "quota_bytes": TEST_QUOTA})
    r = recorder(box, "r-1", "srv-1", acl=False)
    r.lease_pass()
    r.heartbeat_once()
    assert "block_small" not in heartbeats(box.objects, "rec")["r-1"].extra["objectstorage"]
    t0, frame = 1_757_500_000_000, 40
    for i in range(2100):                                       # one key frame and six megabytes after it
        try:
            r.store.put("7", 1, video(t0 + i * frame, t0 + (i + 1) * frame, os.urandom(20_000 if i == 0 else 3_000), i == 0))
        except ObsdError:
            pass
    assert r.store.too_large >= 1, r.store.too_large
    r.heartbeat_once()
    said = heartbeats(box.objects, "rec")["r-1"].extra["objectstorage"]
    assert said["block_small"] == said["block_bytes"] == TEST_BLOCK, said
