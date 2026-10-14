"""Explicit test catalogues restore isolation without changing production guards."""
import inspect
import os
from w2cplatform import catalog
from tests.catalog_fixture import isolated_catalog


def test_catalog_scope_restores_all_state_even_when_the_test_raises():
    saved = catalog._loaded, catalog._files, catalog.version, catalog._derived
    previous = os.environ.get(catalog.SPEC_DIR)
    os.environ[catalog.SPEC_DIR] = '/a/catalogue/that/must/not/be-loaded'
    try:
        try:
            with isolated_catalog():
                assert catalog.specs() == []
                catalog.version += 7
                catalog._derived['fixture'] = 'only inside'
                raise RuntimeError('test ended')
        except RuntimeError as e:
            assert str(e) == 'test ended'
        assert catalog._loaded is saved[0] and catalog._files is saved[1]
        assert catalog.version == saved[2] and catalog._derived is saved[3]
        assert os.environ[catalog.SPEC_DIR] == '/a/catalogue/that/must/not/be-loaded'
    finally:
        if previous is None: os.environ.pop(catalog.SPEC_DIR, None)
        else: os.environ[catalog.SPEC_DIR] = previous


def test_catalog_decorator_keeps_discovery_and_fixture_signature():
    @isolated_catalog()
    def example(monkeypatch):
        return monkeypatch, catalog.specs()
    assert example.__module__ == __name__ and example.__name__ == 'example'
    assert str(inspect.signature(example)) == '(monkeypatch)'
    assert example('fixture') == ('fixture', [])
