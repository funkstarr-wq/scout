"""One shared connection to the Claude API.

Tests swap in a fake client with set_client(), so they run without
an API key and without spending money.
"""
import anthropic

_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def set_client(new_client):
    global _client
    _client = new_client
