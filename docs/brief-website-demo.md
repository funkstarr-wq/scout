# Brief: the book website and a live Scout demo

I'm the author of **"Building Scout: A plain-English guide to AI agents, and the tools
that build them"**. Readers with no technical background build Scout, the
research-assistant app in this folder, while learning AI agents, Claude Code, prompts,
tools, hooks, subagents, skills, MCP, LangGraph, long-running harnesses and
Karpathy-style autoresearch.

Build two things into this project and deploy them together as **one Railway service**:

1. **A website that sells the book**, at `/`.
2. **A public live demo of Scout**, at `/demo`, so people can watch it work before they buy.

The demo spends my money every time someone uses it. **Cost control comes before
everything else in this brief.**

---

## 0. How to work

1. Read `CLAUDE.md`, the code and the existing tests first. Every rule in `CLAUDE.md`
   still applies.
2. **Stop and give me a plan in plain English. Don't change any file until I say OK.**
   The plan must include:
   - The files you'll add or change, and what each one is for.
   - **Every place where this brief doesn't match the code.** For example: what the
     effort settings are actually called, how the password works today, how the tests
     fake the API, and where history is stored. I wrote this brief without the code in
     front of me, so the code is right. Tell me what you'll do instead.
   - Your best estimate of what one demo run costs with the cheaper limits below, and
     a suggested `SCOUT_DAILY_LIMIT` that keeps the demo under **£[20] a month**.
   - Three example questions you suggest for the example reports (see 2.6).
   - Any new package you want to add, and why. I'd rather have none.
3. Build in the stages below, in order. Run the whole test suite at the end of each
   stage. Don't start the next stage while tests are failing.
4. **Never call the real Claude API or any paid search API.** That covers tests,
   checks, `scripts/make_examples.py` and "just a quick try". Don't deploy anything
   either. I'll do both myself.

**Out of scope:** payments, user accounts, email sign-up, analytics or tracking,
changes to how Scout researches (apart from the effort limits below), and any
frontend framework or build step.

---

## Stage 1: The book website (served at `/`)

One polished, fast, static landing page in `scout/static/site/`. Use plain HTML and
CSS only: no build step, no frameworks, and **no third-party requests** (no web fonts,
no analytics, no CDN). The page must be readable without JavaScript.

**Look and feel.** Calm and bookish, to match the existing Scout page. Use serif body
text from a system font stack, one accent colour and generous spacing. Nothing flashy.

**Must work:**
- On phones (check at 375px wide with no sideways scrolling) and in dark mode
  (`prefers-color-scheme`).
- With assistive technology: one `<h1>`, headings in order, a "skip to content" link,
  alt text on every image, WCAG AA contrast in both light and dark, a visible
  keyboard focus, every control reachable with Tab, and animation turned off under
  `prefers-reduced-motion`.

**Sections, in this order:**

1. **Hero:** the book cover, the title, the subtitle and this line: *"Build a working
   AI research assistant, even if you've never written code."* Two buttons: **Buy on
   Amazon** (opens `AMAZON_URL`) and **Try the live demo** (goes to `/demo`).
2. **What you'll build:** three short points.
   - A team of AI agents researches any question.
   - Every claim is cited.
   - It ends up live on the internet.
3. **How it works:** a simple diagram drawn as inline SVG: *Question → planner →
   researchers (in parallel) → writer → fact-checker → cited report*. Give the SVG a
   `<title>` and `<desc>`, add the same steps as a plain text list for screen readers,
   and make sure it reads well on a phone, stacking vertically if needed.
4. **Contents:** the 15 chapters in five parts, exactly as written here.
   - **Part One, Foundations**
     1. What an agent actually is
     2. Setting up your workshop
     3. Talking to Claude well
   - **Part Two, Working with Claude Code**
     4. Building with Claude Code
     5. Giving Claude a memory
     6. Checks that can say no
   - **Part Three, Building the agent**
     7. Writing tools for agents
     8. A team of researchers
     9. Drawing the map
   - **Part Four, Scaling your workshop**
     10. Helpers with their own desks
     11. Teaching Claude your recipes
     12. Plugging into the world
   - **Part Five, Running on its own**
     13. Work that outlasts a conversation
     14. The agent in a loop
     15. Shipping Scout
5. **Who it's for:** complete beginners, and people who keep hearing "agents" and
   "MCP" at work.
6. **What you need:** a computer, a Claude subscription, about £10 of API credit, and
   patience for setup.
7. **Example reports:** three cards. Each shows its question and links to
   `/examples/<name>`.
8. **About the author:** `[AUTHOR]` plus two lines of bio: `[BIO]`.
9. **Footer:** a link to the companion code (`GITHUB_URL`), a link to the privacy
   note (see 2.7), and: *"This book is independent and is not affiliated with or
   endorsed by Anthropic. Claude is a trademark of Anthropic."*

**Placeholders.** `AMAZON_URL`, `GITHUB_URL`, `AUTHOR`, `BIO` and `SITE_URL` (the
public address, used in sharing tags) all go in **one clearly marked config block at
the top of the file**. Be aware that link previews on WhatsApp, LinkedIn and similar
come from bots that don't run JavaScript. That means the `<title>`, meta description
and Open Graph tags (`og:title`, `og:description`, `og:image`, `og:url`) must contain
real text in the raw HTML. In the plan, tell me how you'll arrange things so I only
edit one place.

**Cover image.** I'll supply `scout/static/site/cover.jpg`. Until I do, use a plain,
tasteful placeholder that's the same shape as a book cover. It's also the `og:image`.

**Size.** Keep the HTML and CSS together under 100 KB, not counting the cover.

---

## Stage 2: The live demo (served at `/demo`)

### 2.1 Move the current page

- Move the current Scout page from `/` to `/demo`. It should keep working **exactly as
  now**, and every request it makes must still reach the right place.
- Add a short banner at the top: **"Live demo. Limited questions per day. Questions
  are stored."** Underneath it, in smaller text: *"Please don't include personal
  details."*

### 2.2 `DEMO_MODE` (environment variable, off by default)

- **When it's off**, everything behaves as it does today, including the password on
  `/demo` and on whatever runs Scout. All existing tests pass unchanged.
- **Whether it's on or off**, the website (`/`) and the example pages (`/examples/...`)
  are public. They never call the API, so they cost nothing.
- **When it's on:**
  - There's no password on `/`, `/demo` or `/examples`. Anything else that's
    password-protected today stays protected or is switched off. List those routes
    in the plan.
  - The limits in 2.3 and the cheaper effort settings in 2.4 apply.
  - The app **refuses to start**, with a clear message, if the salt is missing or
    `SCOUT_DAILY_LIMIT` isn't a whole number. A typo in a setting must never mean
    "no limit".

### 2.3 Limits (DEMO_MODE only)

Check all of these on the server **before any API call**, in this order:

1. **Question length:** 10 to 300 characters after trimming spaces. Also show a live
   character count on the page as a hint, but the server check is what counts.
2. **Global cap:** at most `SCOUT_DAILY_LIMIT` questions per day across all visitors.
3. **Per visitor:** at most **2 questions per day**.
4. **One at a time:** at most `SCOUT_MAX_CONCURRENT` runs at once (default 1). If
   Scout is busy, say so and ask the visitor to try again in a minute. A "busy"
   refusal doesn't use up one of their questions.

**How to count:**
- A question counts **the moment it's accepted**, not when it finishes. Failed runs
  still count, because they still cost money.
- Checking the limit and recording the question must happen in **one database
  transaction**, so two people pressing Ask at the same moment can't both slip under
  the cap.
- A "day" is a UTC calendar day. Counters reset at midnight UTC.
- Give every run a time limit (3 minutes, unless you think another value is better).
  When the time is up, stop the run cleanly and tell the visitor.

**Identifying a visitor without storing their IP:**
- On Railway, the connection comes from Railway's proxy, not the visitor. Railway
  passes the visitor's real IP in the `X-Real-IP` header. Trust that header **only
  when `DEMO_MODE` is on**. Locally, use the connection address.
- Store only `HMAC-SHA256(key = SCOUT_IP_SALT, message = IP + today's date)`. Because
  the date is included, the same person's hashes can't be linked from one day to the
  next.
- **Never store or log a raw IP**, including in error messages and access logs. If
  the server's own access log prints client IPs, turn that off in DEMO_MODE.
- People who share a network (an office, a school, some mobile networks) will share
  one allowance. That's acceptable for a demo.

**When a limit is hit**, say so in friendly, plain words and link to the example
reports. Something like:
- *"You've used your 2 questions for today. Come back tomorrow, or have a look at
  these example reports."*
- *"The demo has answered all the questions it can afford today. It resets
  overnight. Meanwhile, here are three finished reports."*
- *"Questions need to be between 10 and 300 characters."*

### 2.4 Cheaper effort settings (DEMO_MODE only)

`MAX_SUBTASKS=3` and `MAX_SEARCHES_PER_RESEARCHER=3`. Use whatever names the code
already has for these settings. If there's anything else that makes a run cheaper
(which model each role uses, maximum answer length, number of fact-check passes), list
it in the plan with the likely saving. **Don't change it without asking me.**

### 2.5 History

- In DEMO_MODE, history on `/demo` shows only the current visitor's own questions.
  Identify the visitor with a random ID in a cookie (HttpOnly, SameSite=Lax, and
  Secure when served over HTTPS), **not** the IP hash. Otherwise everyone on the same
  network would see each other's questions.
- No visitor can ever see someone else's question or report. The only public reports
  are the three examples I've chosen, so strangers can't use the demo to put text on
  my site.
- With DEMO_MODE off, history works as it does today.

### 2.6 Example reports

- **`scripts/make_examples.py`** runs Scout on three questions **with the demo effort
  settings**, so the examples look like what visitors get. It saves each result to
  `scout/static/examples/<name>.json`. Each file holds the question, the report, the
  sources, the full progress log, the date, and the settings used. Running it again
  overwrites the files. At the start it prints a line saying it calls the real API
  and roughly what that will cost. **Don't run it.** I'll run it myself once.
- **`/examples/<name>`** shows the report with its sources and progress log, in the
  same style as the demo. It **never calls the API**, and a test must prove that.
- Only names that match a file in that folder work. Anything else, including tricks
  like `../`, gets a friendly 404.
- If a JSON file doesn't exist yet (because I haven't run the script), show a polite
  "coming soon" page rather than an error. The site must work before I run the
  script.
- Hard-code the three questions in the landing page cards, so the landing page stays
  static.

### 2.7 Privacy note

Write a short, plain-English privacy note at `/privacy` or as a section of the site.
It should say what the demo stores (questions, reports, a one-way hash of your IP that
changes daily, and one cookie that shows you your own history), why, and for how long.
Then make that true: **delete demo questions and hashes older than 30 days**,
checking once at startup and once a day. No other cookies, and no analytics.

### 2.8 Free local preview

If the fake client used in the tests can drive the app easily, add `SCOUT_FAKE=1` so
I can click through `/demo` locally, including hitting the limits, without spending
anything. While it's on, show a clear "FAKE ANSWERS" banner so it can never be
mistaken for the real thing. If this turns out not to be simple, tell me in the plan
and skip it.

---

## Stage 3: Tests

Write these alongside Stage 2, not afterwards. Use the fake client. There must be no
real API calls in any test. Cover at least:

- A visitor's 3rd question of the day is refused, and the 1st and 2nd are allowed.
- The global cap refuses the next question once `SCOUT_DAILY_LIMIT` is reached, even
  for a brand-new visitor.
- Two questions sent at the same moment can't take the count over either cap.
- Questions of 9 and 301 characters are refused, and 10 and 300 are allowed (after
  trimming spaces).
- Counters reset the next UTC day. Use a fake clock and don't actually wait.
- A "busy" refusal doesn't use up a question.
- No raw IP appears anywhere in the database file or in captured logs.
- `X-Real-IP` is used in DEMO_MODE and ignored otherwise.
- Two visitors with different cookies see only their own history.
- `/`, `/demo` and `/examples/<name>` need no password in DEMO_MODE, and `/demo`
  still needs it when DEMO_MODE is off.
- Example pages never touch the client: the fake client fails the test if it's
  called. Unknown names and `../` tricks give a 404, and a missing JSON file shows
  the "coming soon" page.
- The app refuses to start in DEMO_MODE without a salt or a valid daily limit.
- Old demo rows are deleted after 30 days.
- With DEMO_MODE off, every existing test still passes unchanged.

---

## Stage 4: Deployment

- **Procfile:** one web process that listens on `$PORT`, with **a single worker**. The
  limits and the "one at a time" rule live in one process and one SQLite file, so the
  Railway service must also stay at **one replica**. Say this in the README.
- **README, new section "Deploying the demo on Railway"**, with a table of exactly what
  I need to set:

  | Variable | Value |
  |---|---|
  | `ANTHROPIC_API_KEY` | A **separate** key used only for the demo |
  | *(any search API key Scout uses)* | A separate key with its own spending cap, if the provider offers one |
  | `DEMO_MODE` | `1` |
  | `SCOUT_DAILY_LIMIT` | The number from your plan |
  | `SCOUT_MAX_CONCURRENT` | `1` |
  | `SCOUT_IP_SALT` | A long random string, plus the one-line command to generate it |
  | `SCOUT_DB` | `/data/scout.db`, with a Railway volume mounted at `/data` |

  Also include:
  - How to add the volume.
  - Why there should be only one replica.
  - The worst-case daily cost, which is `SCOUT_DAILY_LIMIT` × the cost of one run.
- **Remind me, in the README and in your final message:** create a separate API key
  for the demo in the Claude Console, ideally in its own workspace, and set a low
  monthly spending limit on it. That way a busy day, a bug or a leaked key has a hard
  ceiling, and I can revoke the demo key without breaking my own work.

---

## When you're finished

1. Run the full test suite and show me the summary.
2. If a headless browser is available, check the landing page and `/demo` at phone
   width and in dark mode, and tab through each page with the keyboard. Fix anything
   that's broken.
3. Use the **code-reviewer** subagent on all the changes. Fix what it finds, or tell
   me why you didn't.
4. Explain to me in plain English:
   - **How to try it locally**: the exact commands, first in free fake mode and then
     with my real key, what to click, and how to see each limit kick in.
   - **What I still need to do**: fill in the placeholders, add the cover, run
     `scripts/make_examples.py` once, set up Railway, and set the spending limit.
