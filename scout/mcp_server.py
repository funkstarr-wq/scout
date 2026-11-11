"""Scout as an MCP server, so Claude Code or Claude Desktop can use it as a tool.

Add it to Claude Code (from the scout folder, with the virtual environment active):
    claude mcp add scout -- "$(pwd)/.venv/bin/python" "$(pwd)/scout/mcp_server.py"
"""
import sys
from pathlib import Path

# Make "import scout" work no matter which folder this file is started from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402  (MCP Python SDK 2.x)

from scout.graph import run_research  # noqa: E402

mcp = MCPServer("scout")


@mcp.tool()
def deep_research(question: str) -> str:
    """Research a question on the public web using Scout's team of research agents.

    Returns a Markdown report that answers the question, with numbered citations
    and a list of sources. Use this for questions that need several up-to-date
    sources, comparisons, or a written summary. Do not use it for simple facts you
    already know. It takes one to four minutes and costs a small amount per call.

    question: the full question, written as you would ask a human researcher,
    including any country, time period or other constraints.
    """
    return run_research(question)["report"]


if __name__ == "__main__":
    mcp.run()  # talks to Claude over standard input and output
