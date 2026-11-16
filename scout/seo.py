"""Helping search engines and AI assistants find, understand and quote the website.

- robots.txt says who may read what (everyone, AI assistants included, except the private pages).
- sitemap.xml lists the public pages, so search engines find them all.
- llms.txt is a plain summary of the site written for AI assistants (see llmstxt.org).
- The home page carries structured data (schema.org JSON-LD): facts about the book, its author,
  the website and the questions people ask, in a form search engines read directly.
- Example reports are written into their page on the server, so tools that don't run
  JavaScript (many AI assistants among them) still read them.

The questions and answers live in scout/static/site/faq.md, so the home page, the structured
data and llms.txt always say the same thing.
"""
import html
import json
import re
from xml.sax.saxutils import escape as xml_escape

from . import config, examples

SITE_DIR = examples.EXAMPLES_DIR.parent / "site"
FAQ_FILE = SITE_DIR / "faq.md"
LLMS_FILE = SITE_DIR / "llms.txt"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/chris-haworth-98605b27/"

# Pages people and robots should never find through search.
PRIVATE_PATHS = ("/admin", "/api/", "/book/")
# AI assistants and AI search engines, named so it's clear they're welcome.
AI_CRAWLERS = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User", "Claude-SearchBot",
               "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "CCBot")


def site() -> str:
    return config.SITE_URL.rstrip("/")


# ----------------------------------------------------------------- the FAQ
def faq() -> list[tuple[str, str]]:
    """The questions and answers in faq.md, in order."""
    text = FAQ_FILE.read_text(encoding="utf-8")
    pairs = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        question, _, answer = block.partition("\n")
        answer = " ".join(answer.split())
        if question.strip() and answer:
            pairs.append((question.strip(), answer))
    return pairs


def faq_html() -> str:
    return "\n".join(f'        <div class="faq-item"><h3>{html.escape(q)}</h3><p>{html.escape(a)}</p></div>'
                     for q, a in faq())


# ------------------------------------------------------- structured data
def script_json(data: dict) -> str:
    """JSON that is safe inside a <script> tag."""
    return json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")


def home_json_ld() -> str:
    """Facts about the website, the book, its author and the FAQ, for search engines."""
    base = site()
    author = {"@id": f"{base}/#author"}
    return script_json({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "@id": f"{base}/#website", "url": f"{base}/", "name": "Building Scout",
             "description": "The website of Building Scout, a free plain-English guide to AI agents.",
             "inLanguage": "en-GB", "publisher": author},
            {"@type": "Book", "@id": f"{base}/#book", "name": "Building Scout",
             "alternativeHeadline": "A plain-English guide to AI agents, and the tools that build them",
             "description": "Build a working AI research assistant, even if you've never written code. A hands-on "
                            "guide to AI agents, Claude Code, prompts, tools, hooks, subagents, skills, MCP, "
                            "LangGraph and self-improving agent loops.",
             "author": author, "publisher": author, "url": f"{base}/", "image": f"{base}/book-cover.jpg",
             "inLanguage": "en-GB", "bookFormat": "https://schema.org/EBook", "isAccessibleForFree": True,
             "genre": "Computers / Artificial Intelligence", "datePublished": "2026-11-11",
             "keywords": "AI agents, Claude Code, Claude, prompts, tools, hooks, subagents, skills, MCP, "
                         "Model Context Protocol, LangGraph, AI research assistant, vibe coding",
             "audience": {"@type": "Audience", "audienceType": "Beginners with no coding experience"},
             "offers": {"@type": "Offer", "price": "0", "priceCurrency": "GBP",
                        "availability": "https://schema.org/InStock", "url": f"{base}/#free"}},
            {"@type": "Person", "@id": f"{base}/#author", "name": "Christopher Haworth",
             "alternateName": "Chris Haworth", "jobTitle": "Product leader", "url": f"{base}/#author",
             "image": f"{base}/author.jpg", "sameAs": [AUTHOR_LINKEDIN]},
            {"@type": "FAQPage", "@id": f"{base}/#faq", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faq()]},
        ],
    })


# -------------------------------------------------- robots, sitemap, llms.txt
def robots_txt() -> str:
    rules = "Allow: /\n" + "".join(f"Disallow: {path}\n" for path in PRIVATE_PATHS)
    named = "".join(f"User-agent: {bot}\n" for bot in AI_CRAWLERS)
    return ("# Building Scout: everyone is welcome to read this site, AI assistants included.\n"
            "# Only the owner's pages, the data behind the demo and personal download links are off limits.\n\n"
            f"User-agent: *\n{rules}\n"
            f"# AI assistants and AI search, named so it's clear they're welcome too.\n{named}{rules}\n"
            f"Sitemap: {site()}/sitemap.xml\n")


def sitemap_xml() -> str:
    base = site()
    pages = [(f"{base}/", None), (f"{base}/demo", None), (f"{base}/privacy", None)]
    for name in examples.recorded():
        saved = examples.load(name) or {}
        pages.append((f"{base}/examples/{name}", (saved.get("made_at") or "")[:10] or None))
    urls = "".join(f"  <url><loc>{xml_escape(loc)}</loc>" + (f"<lastmod>{xml_escape(day)}</lastmod>" if day else "")
                   + "</url>\n" for loc, day in pages)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')


def llms_txt() -> str:
    reports = []
    for name in examples.recorded():
        saved = examples.load(name) or {}
        summary = plain_summary(saved.get("report", ""), 160)
        reports.append(f"- [Example report: {examples.EXAMPLES[name]}]({site()}/examples/{name})"
                       + (f": {summary}" if summary else ""))
    faq_text = "\n\n".join(f"### {q}\n{a}" for q, a in faq())
    text = LLMS_FILE.read_text(encoding="utf-8")
    return (text.replace("{{SITE}}", site())
                .replace("{{EXAMPLES}}", "\n".join(reports) + ("\n" if reports else ""))
                .replace("{{FAQ}}", faq_text))


# ----------------------------------------------------------- example reports
def _inline(text: str) -> str:
    """One line of Markdown as safe HTML: links (web addresses only) and bold. Everything else is text."""
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                  lambda m: f'<a href="{m.group(2)}" rel="nofollow noopener">{m.group(1)}</a>', text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def report_html(markdown: str) -> str:
    """A simple, safe HTML version of a report, so the page reads well before any script runs.
    (The page's script then shows the fully formatted version.)"""
    out, paragraph, items, list_tag = [], [], [], None

    def flush():
        nonlocal paragraph, items, list_tag
        if paragraph:
            out.append(f"<p>{_inline(' '.join(paragraph))}</p>")
        if items:
            out.append(f"<{list_tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{list_tag}>")
        paragraph, items, list_tag = [], [], None

    for line in markdown.splitlines():
        stripped = line.strip()
        heading = re.match(r"(#{1,6})\s+(.*)", stripped)
        bullet = re.match(r"[-*]\s+(.*)", stripped)
        numbered = re.match(r"\d+[.)]\s+(.*)", stripped)
        if not stripped:
            flush()
        elif heading:
            flush()
            level = 2 if len(heading.group(1)) <= 2 else 3  # the page's own h1 is the question
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif bullet or numbered:
            tag = "ul" if bullet else "ol"
            if paragraph or (list_tag and list_tag != tag):
                flush()
            list_tag = tag
            items.append((bullet or numbered).group(1))
        else:
            if items:
                flush()
            paragraph.append(stripped)
    flush()
    return "\n".join(out)


def plain_summary(markdown: str, limit: int = 155) -> str:
    """The report's first paragraph as plain text, cut to fit a search result."""
    for block in re.split(r"\n\s*\n", markdown):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", block)  # links become their words
        text = re.sub(r"\s*\[\d+(?:,\s*\d+)*\]", "", text)       # citation numbers go
        text = " ".join(text.replace("**", "").split())
        if len(text) <= limit:
            return text
        return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return ""


def report_json_ld(name: str, saved: dict) -> str:
    base = site()
    data = {
        "@context": "https://schema.org", "@type": "Report",
        "headline": saved.get("question") or examples.EXAMPLES[name],
        "description": plain_summary(saved.get("report", "")),
        "url": f"{base}/examples/{name}", "inLanguage": "en-GB",
        "isPartOf": {"@id": f"{base}/#website"},
        "publisher": {"@type": "Person", "name": "Christopher Haworth", "url": f"{base}/#author"},
        "creditText": "Researched and written by Scout, the AI research assistant built in the book Building Scout",
        "citation": [s["url"] for s in saved.get("sources", []) if str(s.get("url", "")).startswith("http")],
    }
    if saved.get("made_at"):
        data["datePublished"] = saved["made_at"]
    return script_json(data)
