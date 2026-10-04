import pytest


@pytest.fixture(autouse=True)
def _obo_off_for_tests(monkeypatch):
    """Nothing in these tests reaches AgentCore Identity: exchange is switched off the one
    sanctioned way (OBO=off). test_obo.py covers the fail-closed default."""
    monkeypatch.setenv("OBO", "off")


@pytest.fixture(autouse=True)
def _no_priming_in_tests(monkeypatch):
    """The entrypoint primes the runtime's snapshot (prime.py); tests that start it do not."""
    monkeypatch.setenv("HR_PRIME", "0")
