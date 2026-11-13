# The book website

This is the landing page for *Building Scout: A plain-English guide to AI agents, and
the tools that build them*. It's Stage 1 of [the website-and-demo brief](brief-website-demo.md).

## What's in `scout/static/site/`

| File | What it is |
|---|---|
| `index.html` | The whole page. The HTML and CSS are in one file, with no JavaScript, no build step and no outside requests. |
| `cover.jpg` | A placeholder book cover (800 × 1200). Replace it with your real cover, keeping the 2:3 shape. |
| `og-image.jpg` | The picture shown when someone shares the link (1200 × 630). Replace it once you have the real cover. |
| `author.jpg` | Your photo for "About the author". Your name, bio and LinkedIn link are written into `index.html` itself. |

The design follows the book's cover: deep teal and cream, the cover's lettering in the hero, and its
typeface, Charis SIL (a free version of Charter), which lives in `scout/static/fonts/` and is used by
every page. If you replace the cover with a different design, the colours are at the top of the
`<style>` block in `index.html` (`--teal` and `--cream`).

## The free book

The **Get the book free** section has a form (first name, surname, email, and an optional box for
occasional emails). It posts to `/book`, which saves the reader and shows download links for
`book/Building-Scout.pdf` and `book/Building-Scout.epub`. See the README for how to get your list of
readers and how to rebuild the book when the manuscript changes.

## Before it goes live

The top of `index.html` lists three placeholders. Swap each one for your real value
with your editor's "Replace All":

- `{{AMAZON_URL}}`: your book's Amazon page
- `{{GITHUB_URL}}`: the companion code
- `{{SITE_URL}}`: the public address, with no slash at the end

## Preview it on your computer

Run Scout (see the README) and open http://127.0.0.1:8000. The website is served at `/`, and its
links go to the live demo (`/demo`), the three example reports (`/examples/...`) and the privacy
note (`/privacy`). The example pages say "coming soon" until you run `scripts/make_examples.py`.

## The privacy note

`scout/static/privacy.html` has one placeholder of its own, listed at the top of the file:
`{{CONTACT_EMAIL}}`. Fill it in the same way.
