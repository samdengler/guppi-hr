import pytest


@pytest.fixture(autouse=True)
def _obo_off_for_tests(monkeypatch):
    """Nothing in these tests reaches AgentCore Identity: exchange is switched off the one
    sanctioned way (OBO=off); the hop-token tests replace the exchangers instead."""
    monkeypatch.setenv("OBO", "off")
