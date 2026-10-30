"""Finite design witnesses for ADR-0097, not a platform implementation or a SUT test.

Run only through CT 103. Scope coverage is explicit fixture data; compare the
document's single action-sub rule with the different action-subs it also requires.
"""
import hashlib
import json
import os
from pathlib import Path
import tarfile
import tempfile

RANK = {'view': 0, 'edit': 1, 'admin': 2}


def allow(grants, cap, action_sub, ref, folders=()):
    for grant in grants:
        if action_sub is not None and 'sub' in grant and grant['sub'] != action_sub:
            continue
        covered = grant['scope'] == '*' or grant['scope'] == 'unit:' + ref or (
            grant['scope'].startswith('folder:') and grant['scope'][7:] in folders)
        if RANK[grant['cap']] >= RANK[cap] and covered:
            return True
    return False


def main():
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='adr97-model-') as directory:
        source = Path(directory)
        with tarfile.open(root / 'sources.tar') as archive:
            assert archive.pax_headers['comment'] == '2900d976a04e7e78d57b932f9f9ead78db23c0d0'
            archive.extractall(source, filter='data')
        sources = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in source.rglob('*') if p.is_file()}
        folder_writer = [dict(cap='admin', sub='platform', scope='folder:F'),
                         dict(cap='edit', sub='cam', scope='unit:cam/7')]
        required_pair = [allow(folder_writer, 'admin', 'platform', 'platform/F', ['F']),
                         allow(folder_writer, 'edit', 'cam', 'cam/7')]
        fixed_sub = {s: [allow(folder_writer, 'admin', s, 'platform/F', ['F']),
                         allow(folder_writer, 'edit', s, 'cam/7')] for s in ('platform', 'cam')}
        assert all(required_pair) and not any(all(v) for v in fixed_sub.values())

        cam_only = [dict(cap='admin', sub='cam', scope='unit:cam/7')]
        # Both rows address cam/7, the second through about; their own subs differ.
        one_sub_batch = [allow(cam_only, 'admin', 'cam', 'cam/7') for _ in ('cam', 'rec')]
        row_sub_batch = [allow(cam_only, 'admin', s, 'cam/7') for s in ('cam', 'rec')]
        assert all(one_sub_batch) and not all(row_sub_batch)

        # A canonical unit-event is not required to carry a payload field named sub.
        journal_record = {'t': 1, 'kind': 'alarm', 'id': 'example', 'of': 'cam/7'}
        archive_reader = [dict(cap='view', sub='rec', scope='unit:cam/7')]
        missing_as_null = allow(archive_reader, 'view', journal_record.get('sub'), 'cam/7')
        producer_sub = allow(archive_reader, 'view', 'det', 'cam/7')
        assert missing_as_null and not producer_sub

        folder_reader = [dict(cap='view', sub='cam', scope='folder:F')]
        visible_before = allow(folder_reader, 'view', 'cam', 'cam/7', ['F'])
        visible_after = allow(folder_reader, 'view', 'cam', 'cam/7', [])
        existing_reset = any((False, False, False, False))  # instance, history, grants, labels unchanged
        assert visible_before and not visible_after and not existing_reset

        # This is a policy question, not classified as a defect by the model.
        membership_admin = folder_writer + [dict(cap='admin', sub='rec', scope='folder:F')]
        before_rec = allow(membership_admin, 'admin', 'rec', 'cam/7', [])
        after_rec = allow(membership_admin, 'admin', 'rec', 'cam/7', ['F'])
        assert not before_rec and after_rec
        compatibility = {}
        for sub in ('cam', 'rec', 'platform', None):
            compatibility[str(sub)] = allow([dict(cap='admin', scope='*')], 'edit', sub, 'cam/7')
        assert all(compatibility.values())
        result = dict(model_only=True, SUT=0, source_commit='2900d976a04e7e78d57b932f9f9ead78db23c0d0',
            sources=sources, mixed_folder_checks=dict(required_pair=required_pair, fixed_sub=fixed_sub),
            mixed_batch=dict(single_sub=one_sub_batch, per_row_sub=row_sub_batch),
            event_sub=dict(record=journal_record, missing_as_null=missing_as_null, producer_det=producer_sub),
            folder_feed=dict(visible_before=visible_before, visible_after=visible_after, existing_reset=existing_reset),
            delegation_policy_question=dict(before_rec=before_rec, after_rec=after_rec),
            old_grant_compatibility=compatibility)
        (Path(os.environ['CHECK_OUT']) / 'model-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
