"""The pretend Claude now lives in scout/fake_llm.py, so the app can use it too (SCOUT_FAKE=1)."""
from scout.fake_llm import FakeClient, FakeMessages, reply, text_block, tool_block  # noqa: F401
