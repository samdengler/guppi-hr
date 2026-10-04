import pytest


@pytest.fixture(autouse=True)
def _obo_off_for_tests(monkeypatch):
    """Nothing in these tests reaches AgentCore Identity: exchange is switched off the one
    sanctioned way (OBO=off). test_obo.py covers the fail-closed default."""
    monkeypatch.setenv("OBO", "off")
