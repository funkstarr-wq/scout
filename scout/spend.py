"""Adds up what the live demo spends on the Claude API, so it can stop at a monthly budget.

Every reply from Claude says how many tokens it read and wrote, and how many web
searches it ran. This module prices those at Anthropic's published rates and
records the total for the month in the database. The demo checks the month's
total before accepting a question (see server.py).

The Claude Console's own monthly spend limit is the hard stop; this keeps the
demo polite and inside the same budget.
"""
import logging

from . import store

log = logging.getLogger("scout")

# Anthropic list prices in US dollars per million tokens (input, output), November 2026.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
# Claude Haiku 5.5 costs more for very long prompts.
LONG_PROMPT = {"claude-haiku-5-5": (100_000, (0.50, 2.50))}
# A model this file doesn't know is priced high, so the demo errs on the side of stopping early.
UNKNOWN_MODEL = (5.00, 25.00)
WEB_SEARCH_USD = 0.01        # $10 per 1,000 searches
CACHE_WRITE = 1.25           # cached prompt writes cost 1.25x the input price
CACHE_READ = 0.10            # cached prompt reads cost 0.1x the input price


def _n(obj, name: str) -> int:
    value = getattr(obj, name, 0) if obj is not None else 0
    return value if isinstance(value, int) else 0


def cost_of(model: str, usage) -> float:
    """What one reply cost, in US dollars, from the usage figures Claude sent with it."""
    if usage is None:
        return 0.0
    price_in, price_out = PRICES.get(model, UNKNOWN_MODEL)
    tokens_in = _n(usage, "input_tokens")
    if model in LONG_PROMPT and tokens_in > LONG_PROMPT[model][0]:
        price_in, price_out = LONG_PROMPT[model][1]
    dollars = (
        tokens_in * price_in
        + _n(usage, "output_tokens") * price_out
        + _n(usage, "cache_creation_input_tokens") * price_in * CACHE_WRITE
        + _n(usage, "cache_read_input_tokens") * price_in * CACHE_READ
    ) / 1_000_000
    searches = _n(getattr(usage, "server_tool_use", None), "web_search_requests")
    return dollars + searches * WEB_SEARCH_USD


class _MeteredMessages:
    def __init__(self, messages):
        self._messages = messages

    def create(self, **kwargs):
        response = self._messages.create(**kwargs)
        try:
            store.add_spend(cost_of(kwargs.get("model", ""), getattr(response, "usage", None)))
        except Exception:  # never let the meter break a question
            log.exception("Could not record what a Claude reply cost")
        return response


class Metered:
    """Wraps a Claude client so every reply's cost is added to this month's total."""

    def __init__(self, client):
        self._client = client
        self.messages = _MeteredMessages(client.messages)

    def __getattr__(self, name):
        return getattr(self._client, name)
