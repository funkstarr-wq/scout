# Scout, your intro to AI
By the last page of this book you will have built Scout, a small web application that answers hard questions the way a good research assistant would. You type a question. Scout breaks it into parts, sends a team of AI researchers out onto the web in parallel, gathers what they find, writes a report with numbered sources, checks its own work, and hands it back to you. You will be able to put it on the internet with a password and use it every day.

This project also holds the book's website and a public **live demo** of Scout. The code exactly as the book describes it is on the `book-v1` branch.

| Address | What it is |
|---|---|
| `/` | The book's website |
| `/demo` | Scout itself |
| `/examples/<name>` | Three finished example reports, which never call Claude |
| `/privacy` | What the website and the live demo store |
| `/book` | The free-book form sends readers here, and they get their PDF and EPUB download links |

## Run it on your computer

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```
```bash
uvicorn scout.server:app --reload
```

Then open http://127.0.0.1:8000 for the website and http://127.0.0.1:8000/demo for Scout. Your API key goes in a `.env` file, as in Chapter 2.

To run the tests (free, no API calls):
```bash
python -m pytest -q
```

## Try the live demo for free

This runs Scout exactly as the public demo will, but with a pretend Claude, so nothing is spent. A red "FAKE ANSWERS" banner shows it isn't real.

```bash
DEMO_MODE=1 SCOUT_FAKE=1 SCOUT_IP_SALT=practice-salt-for-my-computer uvicorn scout.server:app --reload
```

Open http://127.0.0.1:8000/demo and ask a question twice. The third time, you're told you've used your questions for today, with links to the example reports.

## How the live demo protects your money

Every demo question costs you roughly 25 US cents (about 20p), which is an estimate. When `DEMO_MODE=1`:

- **Each visitor** can ask 2 questions a day (`SCOUT_PER_VISITOR_LIMIT`). Visitors are told apart by internet address. Every address in a home's IPv6 block counts as one visitor.
- **Everyone together** can ask `SCOUT_DAILY_LIMIT` questions a day. This is the real budget control.
- **Only one question runs at a time.** Anyone else is asked to try again in a minute, and that doesn't use up their question.
- **Questions must be 10 to 300 characters.**
- **Scout works with less effort:** 3 researchers, 3 web searches each, and no rewrite after the fact-check.
- **The researchers stop after 90 seconds.** If a question has taken over 3 minutes by the time its report is written, the final fact-check is skipped. A slow reply from Claude is retried once at most.
- **Visitors need cookies switched on.** A visitor whose browser blocks them is told so before their question counts.
- **The limits reset at midnight UTC.**
- **Scout refuses to start** if `SCOUT_IP_SALT` or `SCOUT_DB` is missing, or if `DEMO_MODE` or a limit is mistyped, so a typo never means "no limit".

Visitors are told about the limits in plain words. When a limit is reached, the page offers the example reports instead.

**Privacy:** visitors are counted by a one-way code made from their internet address, the date and the secret salt. The code is wiped once its day is over, and raw addresses are never stored. Each visitor sees only their own questions. Questions and reports are deleted after 30 days. The details are at `/privacy`.

## Make the example reports (about 75 US cents, once)

```bash
python scripts/make_examples.py
```

This researches the three website questions with the real API and the demo's settings, and asks before it spends anything. It saves the reports to `scout/static/examples/`. Commit those files so the website can show them.

## The free book (PDF and EPUB)

The website's **Get the book free** form asks for a first name, surname and email address, plus an optional "email me now and then" box. A reader who fills it in gets download links for the PDF and the EPUB. The links work for 7 days, and asking again gives a fresh pair. Each reader is stored once, by email address, with whether they're happy to get emails and how many times they've downloaded.

**To get your list of readers**, set `SCOUT_ADMIN_PASSWORD` (see the Railway table below) and open `https://<your site>/admin/signups.csv`. Sign in with the username `admin` and that password. It downloads as a spreadsheet. Only email the people marked "yes".

**When the manuscript changes**, rebuild both editions. It's free and doesn't call Claude. The PDF keeps your Word design exactly (cover, title page, contents, running heads): LibreOffice prints it as laid out. The EPUB is made with pandoc. One-off setup: install LibreOffice from https://www.libreoffice.org (on a Mac, `brew install --cask libreoffice` also works), then:
```bash
pip install -r requirements-book.txt
```
Then give the script your new manuscript. It accepts a `.doc` or `.docx` saved from Word, stores it in the project as `Building-Scout.docx`, and rebuilds both editions:
```bash
python scripts/build_book.py ~/Downloads/Building-Scout.doc
```
Commit the changed `Building-Scout.docx`, `book/Building-Scout.pdf` and `book/Building-Scout.epub`. If the cover changes, also replace `scout/static/site/cover.jpg`, which is the EPUB's cover and the website's. Prefer not to install LibreOffice? In Word, choose File → Save As → PDF and save over `book/Building-Scout.pdf`.

**While this repository is public**, anyone can download the book files (and the manuscript) straight from GitHub, without filling in the form. Make the repository private if the form matters to you.

## Deploying the demo on Railway

1. **Make a separate API key for the demo.** In the Claude Console, create a workspace just for the demo (for example "Scout demo"), set a **monthly spend limit** on it of $25, which is about £20, and create an API key in that workspace. Then a busy day, a bug or a leaked key can never cost more than that, and you can revoke the demo key without breaking your own work.
2. **Create the service.** In Railway, start a new project from this GitHub repository. Railway reads the `Procfile` to start Scout.
3. **Add a volume** to the service (right-click the service → Attach volume), mounted at `/data`. This keeps the database when Railway redeploys.
4. **Set the variables** in the service's Variables tab:

   | Variable | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | The demo key from step 1 |
   | `DEMO_MODE` | `1` |
   | `SCOUT_DAILY_LIMIT` | `2`. That's about £17 a month at worst, inside a £20 budget. |
   | `SCOUT_PER_VISITOR_LIMIT` | `1` is recommended at this budget, so two different people can try it each day. The default is `2`, which would let the first visitor use the whole day's questions. |
   | `SCOUT_MAX_CONCURRENT` | `1` |
   | `SCOUT_IP_SALT` | A long random string. Make one with the command below this table. |
   | `SCOUT_DB` | `/data/scout.db`. This is required: without it, the daily counts would start again every time Scout restarts, and your list of readers would be lost. |
   | `SCOUT_ADMIN_PASSWORD` | A long password of your own, for downloading your list of readers from `/admin/signups.csv`. |

   To make the salt, run this and paste the result into Railway:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

   You don't need `SCOUT_PASSWORD`, because the demo is public. Scout's web searches are Claude's own search tool, billed to the same API key at $10 per 1,000 searches, so there's no other key to set.
5. **Keep it to one replica** (Settings → Deploy). The limits are counted in one process and one database file, so a second copy would double them.
6. **Get a web address** (Settings → Networking → Generate Domain).

**Worst-case cost** is roughly `SCOUT_DAILY_LIMIT` × 35 US cents a day. That is an estimate, so check the real figure in the Claude Console after the first few days. The Console spend limit from step 1 is the only hard ceiling, so keep it at or below your budget.

### Before you go live

Fill in the placeholders, written like `{{AMAZON_URL}}`, at the top of `scout/static/site/index.html` (website) and `scout/static/privacy.html` (privacy note). The privacy note's contact email matters: it's how readers ask to stop emails or have their details deleted. Use the web address from step 6 as `{{SITE_URL}}`. Replace `scout/static/site/cover.jpg` with your real cover. See `docs/website.md`.
