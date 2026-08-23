import pytest


@pytest.fixture(autouse=True)
def _no_machine_brand(monkeypatch):
    """Machine-local brand assets (~/.sofit/assets) must not leak into tests."""
    monkeypatch.setenv("SOFIT_BRAND", "off")
