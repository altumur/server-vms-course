"""Secret declarations grant exact names or slash-terminated families, never implicit descendants."""
from w2cplatform.domain.rights import secret_reads
from w2cplatform.rights import allowed
from w2cplatform.secrets import PLATFORM_SECRET_READERS


def test_exact_secret_grants_neither_descendants_nor_similar_names():
    readers = {"secret/value": {"reader"}}
    patterns = secret_reads("reader", readers, [])
    assert allowed(patterns, "secret/value")
    for key in ("secret/value/north", "secret/value-pending", "secret/values"):
        assert not allowed(patterns, key), key
    denied = ["*", *secret_reads("outsider", readers, ["*"])]
    assert not allowed(denied, "secret/value")
    for key in ("secret/value/north", "secret/value-pending", "secret/values"):
        assert allowed(denied, key), key


def test_exact_secret_does_not_deny_an_unrelated_descendant_grant():
    read = ["secret/value/north"]
    assert secret_reads("outsider", {"secret/value": set()}, read) == []
    assert allowed(read, "secret/value/north")


def test_prefix_secret_grants_and_denies_all_descendants_only():
    readers = {"secret/value/": {"reader"}}
    granted = secret_reads("reader", readers, [])
    denied = ["*", *secret_reads("outsider", readers, ["*"])]
    for key in ("secret/value/", "secret/value/north", "secret/value/a/b"):
        assert allowed(granted, key), key
        assert not allowed(denied, key), key
    for key in ("secret/value", "secret/value-pending", "secret/values/north"):
        assert not allowed(granted, key), key
        assert allowed(denied, key), key
    partial = ["secret/value/north"]
    assert not allowed([*partial, *secret_reads("outsider", readers, partial)], partial[0])


def test_exact_book_and_holder_family_can_have_different_readers():
    readers = {"domain/example/accounts": {"worker", "agent"},
               "domain/example/accounts/": {"agent"}}
    for role, read in (("worker", []), ("worker", ["domain/example/*"]), ("agent", [])):
        patterns = [*read, *secret_reads(role, readers, read)]
        assert allowed(patterns, "domain/example/accounts")
        assert allowed(patterns, "domain/example/accounts/north") == (role == "agent")


def test_related_platform_secrets_are_explicitly_closed_to_other_roles():
    expected = {"domain/signer-pending": {"domain"},
                "domain/backup-taken": {"console", "domain", "domainagent"},
                "domain/backup-doc": {"console", "domain", "domainagent"},
                "domain/backups/": {"console", "domain", "domainagent"}}
    for row, readers in expected.items():
        assert set(PLATFORM_SECRET_READERS[row]) == readers
        key = row + "north" if row.endswith("/") else row
        for role in ("domain", "console", "domainagent", "resource", "domainconsole"):
            patterns = ["*", *secret_reads(role, PLATFORM_SECRET_READERS, ["*"])]
            assert allowed(patterns, key) == (role in readers), (row, role)


def test_partial_prefix_grant_cannot_stand_for_the_entire_secret_family():
    readers = {"secret/value/": {"reader"}}
    for read in (["secret/value/north"], ["secret/value/_*"], ["secret/value/"]):
        patterns = [*read, *secret_reads("reader", readers, read)]
        for key in ("secret/value/north", "secret/value/south/a", "secret/value/"):
            assert allowed(patterns, key), (read, key)
