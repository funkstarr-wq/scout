# The book website

This is the landing page for *Building Scout: A plain-English guide to AI agents, and
the tools that build them*. It's Stage 1 of [the website-and-demo brief](brief-website-demo.md).

## What's in `scout/static/site/`

| File | What it is |
|---|---|
| `index.html` | The whole page. The HTML and CSS are in one file, with no JavaScript, no build step and no outside requests. |
| `cover.jpg` | A placeholder book cover (800 × 1200). Replace it with your real cover, keeping the 2:3 shape. |
| `og-image.jpg` | The picture shown when someone shares the link (1200 × 630). Replace it once you have the real cover. |

## Before it goes live

The top of `index.html` lists five placeholders. Swap each one for your real value
with your editor's "Replace All":

- `{{AMAZON_URL}}`: your book's Amazon page
- `{{GITHUB_URL}}`: the companion code
- `{{AUTHOR}}`: your name
- `{{BIO}}`: two lines about you
- `{{SITE_URL}}`: the public address, with no slash at the end

## Preview it on your computer

In a terminal, from the project folder:

```bash
cd scout/static/site
python3 -m http.server 8000
```

Then open http://localhost:8000.

Some links won't work yet, because Stage 2 of the brief builds the pages they point
to: **Try the live demo** (`/demo`), the three example reports (`/examples/...`) and
**Privacy** (`/privacy`).
