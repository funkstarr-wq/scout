# The book website

This is the landing page for *Building Scout: A plain-English guide to AI agents, and
the tools that build them*. It's Stage 1 of [the website-and-demo brief](brief-website-demo.md).

## What's in `scout/static/site/`

| File | What it is |
|---|---|
| `index.html` | The whole page: HTML, CSS and a small script for the animations, in one file, with no build step and no outside requests. |
| `book-cover.jpg` | The book cover (800 × 1280), from the manuscript's cover page. It's also the EPUB's cover. If you change it, save the new one under a new name and update `index.html`, so no browser keeps showing an old copy. |
| `og-image.jpg` | The picture shown when someone shares the link (1200 × 630), in the cover's style. |
| `author.jpg` | Your photo for "About the author". Your name, bio and LinkedIn link are written into `index.html` itself. |

The design follows the book's cover: clay, Scout blue and black, set in Outfit (the cover's style of
lettering, free under the SIL Open Font Licence, in `scout/static/fonts/`, used by every page). The
colours are at the top of the `<style>` block in `index.html` (`--clay`, `--blue`, `--blue-bright`,
`--black`).

Things that move, all drawn by the script at the bottom of `index.html`:

- **The cover's robots** in the hero: they bob and blink, pulses run along their wires, and the big
  blue robot's eyes follow the pointer.
- **"Watch Scout think":** an animated walk-through of the three example questions, using Scout's own
  progress messages. It's an illustration, so it never calls Claude and costs nothing.
- **The topics ticker and the numbers** that count up.

Visitors whose device asks for less motion (an accessibility setting) see everything still and
finished, and the page reads the same without JavaScript.

## The free book

The **Get the book free** section has a form (first name, surname, email, and an optional box for
occasional emails). It posts to `/book`, which saves the reader and shows download links for
`book/Building-Scout.pdf` and `book/Building-Scout.epub`. See the README for how to get your list of
readers and how to rebuild the book when the manuscript changes.

## Its address

The site is live at https://scout-production-aa37f689.up.railway.app. That address is written into
`index.html` for link previews (the canonical link and the `og:` tags); change it there if the site
moves to its own domain. There are no Amazon or companion-code links for now.

## Preview it on your computer

Run Scout (see the README) and open http://127.0.0.1:8000. The website is served at `/`, and its
links go to the live demo (`/demo`), the three example reports (`/examples/...`) and the privacy
note (`/privacy`). The example pages say "coming soon" until you record the saved questions, with the button on
`/admin/recordings` or by running `scripts/make_examples.py`.

## The privacy note

For now, the "Questions" section of `scout/static/privacy.html` asks readers to message Chris on
LinkedIn. Once the site has its own domain and email address, put the email there instead.
