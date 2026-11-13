"""One shared connection to the Claude API.

Tests swap in a fake client with set_client(), so they run without
an API key and without spending money. SCOUT_FAKE=1 does the same for
the running app, so you can click through it for free.
"""
import anthropic

from . import config
from .spend import Metered

_client = None


def client():
    global _client
    if _client is None:
        if config.FAKE_MODE:
            from .fake_llm import FakeClient

            _client = FakeClient()
        elif config.DEMO_MODE:
            # The live demo gives up on a slow reply sooner, so one question can't run on for ages,
            # and adds up what every reply costs so it can stop at its monthly budget.
            _client = Metered(anthropic.Anthropic(timeout=config.API_TIMEOUT_SECONDS, max_retries=config.API_MAX_RETRIES))
        else:
            _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def set_client(new_client):
    global _client
    _client = new_client
