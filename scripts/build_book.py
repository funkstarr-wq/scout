"""Build the free PDF and EPUB editions of the book from the Word manuscript.

Run it again whenever Building-Scout.docx changes, then commit the two files in book/.
It doesn't call the Claude API and costs nothing. One-off setup, from the project folder:

    pip install -r requirements-book.txt
    playwright install chromium

Then:

    python scripts/build_book.py

It makes book/Building-Scout.epub (with pandoc) and book/Building-Scout.pdf (pandoc lays the
book out as a web page, then a headless Chromium browser prints it). Both get the cover,
a title page, a table of contents and the font from the cover.
"""
import os
import sys
import tempfile
from pathlib import Path

import pypandoc

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "book"
MANUSCRIPT = ROOT / "Building-Scout.docx"
COVER = ROOT / "scout" / "static" / "site" / "cover.jpg"
FONTS = ROOT / "scout" / "static" / "fonts"
FILTER = BOOK / "manuscript.lua"

TITLE = "Building Scout"
SUBTITLE = "A plain-English guide to AI agents, and the tools that build them"
AUTHOR = "Christopher Haworth"  # as written in the manuscript

PDF = BOOK / "Building-Scout.pdf"
EPUB = BOOK / "Building-Scout.epub"

COMMON = [
    "--lua-filter", str(FILTER),
    "--toc", "--toc-depth=2",
    "--metadata", f"title={TITLE}",
    "--metadata", f"subtitle={SUBTITLE}",
    "--metadata", f"author={AUTHOR}",
    "--metadata", "lang=en-GB",
]


def build_epub() -> None:
    pypandoc.convert_file(
        str(MANUSCRIPT), "epub3", format="docx+styles", outputfile=str(EPUB),
        extra_args=COMMON + [
            "--split-level=2",                       # one file per chapter, so e-readers stay quick
            f"--epub-cover-image={COVER}",
            f"--css={BOOK / 'epub.css'}",
            *[f"--epub-embed-font={font}" for font in sorted(FONTS.glob("*.woff2"))],
            "--metadata", "rights=Copyright © 2026 Christopher Haworth. Free to download and share, unchanged.",
        ],
    )


def font_faces() -> str:
    faces = []
    for weight in (400, 700):
        for style in ("normal", "italic"):
            url = (FONTS / f"charis-sil-latin-{weight}-{style}.woff2").as_uri()
            faces.append(f'@font-face {{ font-family: "Charis SIL"; font-weight: {weight}; '
                         f'font-style: {style}; src: url("{url}") format("woff2"); }}')
    return "<style>\n" + "\n".join(faces) + "\n</style>\n"


def build_pdf() -> None:
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        header = work / "fonts.html"
        header.write_text(font_faces(), encoding="utf-8")
        html_path = work / "book.html"
        pypandoc.convert_file(
            str(MANUSCRIPT), "html5", format="docx+styles", outputfile=str(html_path),
            extra_args=COMMON + [
                "--standalone",
                f"--extract-media={work}",
                f"--css={(BOOK / 'print.css').as_uri()}",
                f"--include-in-header={header}",
            ],
        )
        html = html_path.read_text(encoding="utf-8")
        cover = f'<section class="cover-page"><img src="{COVER.as_uri()}" alt=""></section>'
        html = html.replace("<body>", "<body>\n" + cover + '\n<div class="book">', 1)
        html = html.replace("</body>", "</div>\n</body>", 1)
        html_path.write_text(html, encoding="utf-8")

        with sync_playwright() as p:
            # BOOK_CHROMIUM lets you point at a Chromium that's already installed somewhere else.
            browser = p.chromium.launch(executable_path=os.environ.get("BOOK_CHROMIUM") or None)
            page = browser.new_page()
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.pdf(path=str(PDF), prefer_css_page_size=True, print_background=True, tagged=True, outline=True)
            browser.close()


def main() -> int:
    if not MANUSCRIPT.exists():
        print(f"Can't find the manuscript at {MANUSCRIPT}")
        return 1
    print("Building the EPUB…")
    build_epub()
    print(f"   {EPUB.relative_to(ROOT)}  ({EPUB.stat().st_size // 1024} KB)")
    print("Building the PDF…")
    build_pdf()
    print(f"   {PDF.relative_to(ROOT)}  ({PDF.stat().st_size // 1024} KB)")
    print("Done. Commit both files in book/ so the website can offer them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
