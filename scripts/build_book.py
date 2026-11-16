"""Build the free PDF and EPUB editions of the book from the Word manuscript.

    python scripts/build_book.py                                  # from Building-Scout.docx
    python scripts/build_book.py ~/Downloads/Building-Scout.doc   # from a new version saved in Word
    python scripts/build_book.py ~/Downloads/Building-Scout.docx --epub ~/Downloads/Building-Scout.epub
                                                                  # ...and use your own finished EPUB

Given a new manuscript (.doc or .docx), it first saves it into the project as Building-Scout.docx.
It doesn't call the Claude API and costs nothing. Commit the files it changes.

The PDF keeps the design you made in Word: LibreOffice prints the manuscript exactly as laid out,
with its cover page, title page, contents and running heads. The EPUB is made with pandoc and
book/manuscript.lua, and uses scout/static/site/book-cover.jpg as its cover. If you made an EPUB
yourself, give it with --epub and the script checks it and uses it instead.

One-off setup:
  * LibreOffice, free from https://www.libreoffice.org (on a Mac: brew install --cask libreoffice)
  * pip install -r requirements-book.txt

The manuscript uses Georgia, Arial and Courier New. They come with macOS and Windows, so the PDF
matches Word exactly there. (Or skip LibreOffice for the PDF: in Word, File > Save As > PDF, and save
it over book/Building-Scout.pdf.)
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "book"
MANUSCRIPT = ROOT / "Building-Scout.docx"
COVER = ROOT / "scout" / "static" / "site" / "book-cover.jpg"
FILTER = BOOK / "manuscript.lua"
PDF = BOOK / "Building-Scout.pdf"
EPUB = BOOK / "Building-Scout.epub"

TITLE = "Building Scout"
SUBTITLE = "A plain-English guide to AI agents, and the tools that build them"
AUTHOR = "Christopher Haworth"
RIGHTS = "Copyright © 2026 Christopher Haworth. All rights reserved."  # as on the manuscript's copyright page


def find_libreoffice() -> str:
    """LibreOffice's command-line program, wherever it's installed."""
    for candidate in (os.environ.get("BOOK_SOFFICE"), shutil.which("soffice"), shutil.which("libreoffice"),
                      "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if candidate and Path(candidate).exists():
            return candidate
    sys.exit("LibreOffice isn't installed. Get it free from https://www.libreoffice.org "
             "(on a Mac: brew install --cask libreoffice), then run this again.")


def libreoffice_convert(source: Path, to: str, out_dir: Path) -> Path:
    subprocess.run([find_libreoffice(), "--headless", "--norestore", "--convert-to", to,
                    "--outdir", str(out_dir), str(source)], check=True, capture_output=True, timeout=600)
    return out_dir / f"{source.stem}.{to}"


def take_in(new_manuscript: Path) -> None:
    """Save a new version of the manuscript into the project as Building-Scout.docx."""
    if new_manuscript.suffix.lower() == ".docx":
        shutil.copyfile(new_manuscript, MANUSCRIPT)
    elif new_manuscript.suffix.lower() == ".doc":
        with tempfile.TemporaryDirectory() as work:
            shutil.copyfile(libreoffice_convert(new_manuscript, "docx", Path(work)), MANUSCRIPT)
    else:
        sys.exit("Give me a Word file (.doc or .docx).")
    print(f"Saved the new manuscript as {MANUSCRIPT.name}")


def build_pdf() -> None:
    with tempfile.TemporaryDirectory() as work:
        shutil.copyfile(libreoffice_convert(MANUSCRIPT, "pdf", Path(work)), PDF)


def use_epub(finished: Path) -> None:
    """Use an EPUB made elsewhere, after checking it really is one."""
    try:
        with zipfile.ZipFile(finished) as epub:
            first = epub.infolist()[0]
            ok = (first.filename == "mimetype" and epub.read("mimetype").strip() == b"application/epub+zip"
                  and "META-INF/container.xml" in epub.namelist() and epub.testzip() is None)
    except (zipfile.BadZipFile, IndexError, KeyError, OSError):
        ok = False
    if not ok:
        sys.exit(f"{finished} isn't a working EPUB file.")
    shutil.copyfile(finished, EPUB)


def build_epub() -> None:
    import pypandoc  # only needed here, so checking a finished EPUB works without it

    pypandoc.convert_file(
        str(MANUSCRIPT), "epub3", format="docx+styles", outputfile=str(EPUB),
        extra_args=[
            "--lua-filter", str(FILTER),
            "--toc", "--toc-depth=1",
            "--split-level=1",  # one file per part and chapter, so e-readers stay quick
            f"--epub-cover-image={COVER}",
            f"--css={BOOK / 'epub.css'}",
            "--metadata", f"title={TITLE}",
            "--metadata", f"subtitle={SUBTITLE}",
            "--metadata", f"author={AUTHOR}",
            "--metadata", f"rights={RIGHTS}",
            "--metadata", "lang=en-GB",
        ],
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the free PDF and EPUB editions of the book.")
    parser.add_argument("manuscript", nargs="?", help="a new version of the manuscript (.doc or .docx)")
    parser.add_argument("--epub", help="an EPUB you made yourself, to use instead of making one")
    args = parser.parse_args(argv)
    if args.manuscript:
        take_in(Path(args.manuscript).expanduser())
    if not MANUSCRIPT.exists():
        print(f"Can't find the manuscript at {MANUSCRIPT}")
        return 1
    print("Building the PDF with LibreOffice…")
    build_pdf()
    print(f"   {PDF.relative_to(ROOT)}  ({PDF.stat().st_size // 1024} KB)")
    if args.epub:
        print("Checking and using your EPUB…")
        use_epub(Path(args.epub).expanduser())
    else:
        print("Building the EPUB with pandoc…")
        build_epub()
    print(f"   {EPUB.relative_to(ROOT)}  ({EPUB.stat().st_size // 1024} KB)")
    print("Done. Commit the changed files so the website offers the new edition.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
