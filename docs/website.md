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

Run Scout (see the README) and open http://127.0.0.1:8000. The website is served at `/`, and its
links go to the live demo (`/demo`), the three example reports (`/examples/...`) and the privacy
note (`/privacy`). The example pages say "coming soon" until you run `scripts/make_examples.py`.

## The privacy note

`scout/static/privacy.html` has two placeholders of its own, listed at the top of the file:
`{{AUTHOR}}` and `{{CONTACT_EMAIL}}`. Fill them in the same way.
