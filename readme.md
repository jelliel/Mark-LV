# ⚙️ MARK LV (55)
### The Ultimate Cross-Platform Personal AI Assistant — By FatihMakes

> 📺 **[Watch the full setup video on YouTube](https://www.youtube.com/@FatihMakes)**

A real-time voice AI that can hear, see, speak, and control your computer — on any OS. Supports Windows, macOS, and Linux. Built on the Gemini Live API for native audio streaming, delivering zero subscriptions and total digital autonomy.

---

## ✨ Overview

Mark LIV gave the assistant a face. **Mark LV gives it a screen — and the stamina to keep working when a model goes down.**

Say "play the new Dune trailer" and the video appears **where the avatar was**, in the HUD itself, muted until you ask for sound. A YouTube link, a local file, a direct URL or just a description to search for: they all land in the same place, and JARVIS tells you it is coming *before* the picture arrives instead of going quiet for five seconds.

Underneath, every Gemini call in the app now goes through **one ladder of nine models**, ordered by measured response time rather than guesswork. When a model hits its quota, times out or disappears, the next rung takes the call and the dead one is put on a cooldown so nobody pays for it twice. Before this release, sixteen files named their own model, twenty-six times, with **no timeout at all** — one unwell alias could hang a request forever.

The release also draws a line through the bundled skill list. **Everything JARVIS ships with now drives the computer** — applications, files, the browser, the desktop, the screen. Five skills that served one hobby or one trade left the list, which is a thousand tokens the model no longer reads on every connection, and five fewer wrong tools for it to reach for.

It's not just an assistant — it's an extension of your digital life.

---

## 🚀 Capabilities

### Core Features
| Feature | Description |
|---|---|
| 🧑‍🎤 Holographic Avatar | An animated human head in the HUD — real facial geometry, lit and drawn in software, no GPU or extra packages |
| 👄 Real Lip-Sync | ~50 mouth shapes a second from the audio's formants **and** the transcript — closures, spreads and rounds, not a volume meter |
| 🌍 Language-Free Mouth | Articulation is derived by Unicode reduction, so Latin, Cyrillic and Greek scripts all work from one rule set — and scripts that hide pronunciation fall back cleanly |
| 🙂 Facial Acting | Brows track the phrase, gaze saccades between fixations, natural blinking, a small nod on stressed syllables |
| 😐 Face as Status | Looks away while thinking, meets your eyes while listening, lids fall while asleep, glances down at new content |
| 🎚️ Push-to-Talk | Hold **Ctrl+Space** and the mic opens — closed the rest of the time. Truly global on Windows, window-scoped elsewhere |
| 🔇 Self-Echo Guard | Never answers its own last sentence: the tail of its own voice is recognised and dropped without muting you |
| 🪪 Runtime Self-Knowledge | Name, OS, abilities **and limits** are generated from the live system each session — rename it or add a plugin and it knows |
| 🎙️ Wake Word | Local **"Hey Jarvis"** detection — sleeps until called, auto-sleeps after 2 min of silence, and never streams audio while asleep |
| ⚡ Instant Acknowledgment | Speaks a short, context-aware reply in **your language** the instant a longer task starts — no more silent waiting |
| 🚀 Faster Live Engine | Runs on **Gemini 3.1 Flash Live** — roughly 2× faster time-to-first-word than the previous model |
| 🧩 Self-Describing Skills | Every bundled skill declares its own `TOOL` dict + handler and is auto-discovered at launch — adding one is a single file |
| 🧠 Recallable Memory | No size limit and nothing silently forgotten — the prompt carries what fits, the rest is looked up on demand from a local search |
| 👁️ Memory Panel | See every fact JARVIS has stored about you, when it learned it, and delete any of it in one click |
| ↩️ Undo | Take back what the assistant did — files it moved, renamed, created or wrote, and settings it changed |
| ⚠️ Real Confirmation | Shutdown, restart and WiFi wait for a button **you** press — the model cannot confirm its own irreversible actions |
| 🎧 Audio Device Picker | Choose the microphone and speakers by name, filtered to the short list your OS shows — and measured, so every entry actually works |
| 🔗 Session Continuity | A dropped connection, a voice change or a device change no longer wipes the conversation |
| 🧩 Plugin System | Drop a single `.py` file into `plugins/` — JARVIS learns a new skill on next launch |
| 📺 Video on the HUD | Plays YouTube, a local file or any video URL **where the avatar sits** — starts muted, sound on request |
| 🪜 Model Ladder | Nine Gemini models in one measured order — a quota, a timeout or an outage steps to the next rung instead of failing |
| 🎙️ Real-time Voice | Ultra-low latency conversation in any language via Gemini Live API |
| 🎨 Live Theming | Recolour the entire HUD from a hue wheel or hex — the avatar retints with it |
| 〰️ Reactive HUD | Waveform pulses to real audio — your mic while listening, JARVIS while speaking |
| 🎙️ Voice Picker | Choose from 5 native Gemini voices and switch live from the UI — no restart |
| ♾️ Unlimited Sessions | Sliding-window context compression — one conversation can last for hours |
| 🖥️ System Control | Launch apps, adjust volume/brightness, WiFi, shortcuts, power — all by voice |
| 🧩 Autonomous Tasks | High-level planning for complex multi-step goals via agent mode |
| 👁️ Visual Awareness | Screen capture and webcam vision piped into your main Gemini session, labelled by source |
| 🧠 Persistent Memory | Deeply remembers projects, preferences, and personal context across sessions |
| ⌨️ Hybrid Input | Seamlessly switch between keyboard typing and voice commands |
| 🌅 Morning Briefing | On first boot: greets you, reads the time, recaps yesterday, and fetches live news |
| 🔔 Proactive 2.0 | Time-aware, context-aware check-ins — knows the time of day, your projects, and what you've been discussing |
| 🗓️ Session Memory | Summarises each conversation and mentions it naturally next morning — consumed after use, never repeats |
| 👁️‍🗨️ Background Monitoring | User-configured topic watching — checks for new headlines once a day and alerts naturally |
| 📊 Hardware Monitoring | Continuous CPU, RAM, GPU and temperature telemetry with localized voice alerts |
| 🌤️ Weather Report | Live weather data for your city, personalized from memory |
| 🗺️ Dynamic Content Panel | Scrollable display layer beneath the HUD that renders web results, news, and search data |
| 🔍 Multi-Mode Web Search | `news` / `research` / `price` / `compare` / `search` — Gemini Grounded first, DDG fallback |
| 🦌 Deep Research | A DeerFlow-style loop — plan, parallel readers, contradiction analysis, cited Markdown report — in the background while you keep talking |
| 🧭 Research Sub-Agents | Planner, researcher, analyst, critic and writer, each with its own instructions and its own job — overridable with one Markdown file |
| 📜 Declarative Skills | Markdown skills the planner selects per topic: sourcing, comparison, fact-check, technical due diligence, theology source critique |
| ♻️ Resumable Reports | Every source, note and outline is on disk — a failed or cancelled run is rebuilt from its notes without re-reading a page |
| 🕳️ Vault Gap Trigger | A theology question the vault cannot answer starts a deep run by itself, and the finished report is filed back as a synthesis page — measured coverage, one run at a time, 30-minute cooldown |
| 📜 Theological Reading | What the brain returns is read back theologically — the subject first, then each item in its own authority, with its weight marked — instead of a list of page titles |
| ⏰ Smart Reminders | OS-native scheduled notifications (Windows Task Scheduler / macOS LaunchAgent / Linux systemd) |
| 📂 File Processor | Read, summarize, and answer questions about local files |
| 🌐 Browser Control | Open URLs, navigate tabs, and interact with the browser by voice |
| 📨 Send Message | Compose and send messages through WhatsApp, Telegram, and more |
| 🖱️ Desktop Control | Taskbar, window management, and desktop-level operations |
| 🧑‍💻 Silent Language Memory | Detects spoken language on first use — all future sessions adapt automatically |
| 📱 Remote Dashboard | Control the assistant from your phone via QR code pairing |
| ⚡ Auto-Start on Boot | Registers with the OS startup system (registry / LaunchAgent / .desktop) |
| 📋 Clipboard Intelligence | Copy any text → floating panel with Translate / Summarise / Explain / Fix |
| 🪪 Assistant Customization | Change the assistant name, your name, voice, and colour from the UI — takes effect immediately |

---

## 🆕 What's New in Mark LV

One new dependency for the whole release — `yt-dlp`, and only to turn a YouTube page into something Qt can play.

### The display

#### 📺 Video where the face is
The HUD already had a surface that takes the centre of the screen and gives it back: the camera. Video shares that same stack, so the avatar, the live camera and a video can never be on screen at once — and a video always lands exactly where you are already looking.

It accepts **a local file, a direct media URL, a YouTube link, or just a description** ("play the new Dune trailer") and searches for it. It **starts muted every time**, because a soundtrack talking over the assistant is the one way this feature could make JARVIS worse rather than better. You turn the sound on by asking, or from the button in the video header.

**It answers before it opens.** Resolving what to play takes seconds nothing can remove — measured at 2.0s for a link and 3.3s for a spoken phrase, plus buffering. Restricting yt-dlp to a lighter client was tried and made it worse: the fast clients came back with zero usable formats. So the seconds stay, and what changed is where you spend them — listening to JARVIS say it is coming, instead of watching nothing happen. Say "stop" during those seconds and the video is cancelled before it ever reaches the screen.

#### 🔀 Two streams, one picture
The first version asked YouTube for a format carrying both picture and sound and got *"Requested format is not available"*. That was not a bad selector; it was a wrong assumption. Checked against three videos — including the oldest upload on the site — **every one offered zero combined formats.** Picture and sound are separate streams now.

So there are two players running together, with a timer that corrects any drift over 300 ms. And the audio track is chosen on **language first, bitrate second** — because YouTube auto-dubs a great many videos and ships every dub at the *same* bitrate as the original: measured on one video, English at 129.483 and Arabic, Bangla, German, Spanish, French, Hindi and Indonesian all at 129.482. Sorting on bitrate alone came down to a thousandth of a kilobit, so the same video would play in Arabic one time and English the next for no reason you could see. It now reads YouTube's own original-track marker first.

#### 🔇 It stopped hearing the film
The microphone is open while a video plays, so the moment you turn the sound on, JARVIS starts answering the film. The mic now mutes itself when the video's sound goes on and unmutes when it goes off — and it says so in the activity log rather than going deaf silently.

#### 🎛 Two drawers instead of one
⚙ **SETUP** holds the things you set once — remote control, desktop shortcut, auto-start and customisation. 🎛 **CONTROLS** holds the switches you flick daily — fullscreen, morning brief, wake word, sleep, push-to-talk, HUD style. Only one is open at a time, and each sits under its own header button.

The panel used to stutter when it opened, and the obvious explanation — too many buttons — was wrong. Measured, the **first** wake-word state check took **2.104 seconds**, because it imported `openwakeword` on the UI thread the moment the drawer was built. That import now happens off-thread at boot, and the drawer opens instantly whether it has six buttons or sixteen.

> The drawer also used to vanish *behind* the video. `QVideoWidget` creates a native child window, and no Qt overlay can be drawn on top of one. The video is now a `QGraphicsVideoItem` inside a graphics view — same picture, and the interface stays where it belongs.

### Staying up

#### 🪜 Every Gemini model, in one ladder
Every one-shot Gemini call in the app now goes through `core/gemini.py`. Before this, **sixteen files named their own model — twenty-six times — and not one of them set a timeout.** When a single alias went unwell, the call did not fail; it hung.

The ladder is nine models deep, ordered by **measurement rather than guesswork**:

| Model | Measured | Model | Measured |
|---|---|---|---|
| `gemini-3.5-flash-lite` | 0.56s | `gemini-2.5-flash` | 0.67s |
| `gemini-3.1-flash-lite` | 0.60s | `gemini-2.5-flash-lite` | 0.74s |
| `gemini-flash-lite-latest` | 0.60s | `gemini-3.5-flash` | 1.13s |
| `gemini-3-flash-preview` | 504 after 14.7s | `gemini-3.6-flash` | 504 after 12.0s |
| `gemini-flash-latest` | 503 UNAVAILABLE | | |

The three that fail were **not deleted** — a model that is unwell today is a real rung tomorrow. They sit at the bottom, and a **cooldown** decides how long a failure is believed:

| What happened | Rested for | Why |
|---|---|---|
| Quota exhausted (429) | 5 minutes | Quotas refill |
| No answer (503 / 504 / DEADLINE_EXCEEDED) | 30 minutes | An outage outlasts a retry |
| Not found, or no access (404) | 6 hours | Your key does not have it, and won't in a minute |

That middle row is where the time was going. Only quota and 404 used to be cooled, so the 14-second wait on a dead model was paid **on every single call**. Measured after the fix: first call 13.15s, second 1.98s, third 1.16s — **11.2 seconds saved on every call from then on.**

**The Live model is deliberately not on this ladder.** Live models are not drop-in replacements for one another; they accept different config fields, and the same API key also exposes transcribe-live, live-translate and robotics-streaming models that will happily connect and then not behave like an assistant. So Live has exactly **two** rungs — the current model, and the one this project used before it — and it steps only on quota or loss of access. Never on a network blip or a bad key, which would otherwise walk the whole list into the same wall.

### The shape

#### 🧩 Everything bundled drives the computer
The bundled skill list had grown to seventeen, and some of it was nobody's business but its author's. **Not everyone updates games; everyone opens applications.**

Mark LV trims it to **twelve**, and every one of them does the same kind of thing: drive this machine. Applications, the browser, files, the desktop, the screen, the clock, the weather, the display. The rule is written into the project tree, so the next skill lands in the right folder without anyone having to ask.

This is not only tidiness. Every bundled skill is declared to the model on **every** connection, whether you ever use it or not. The declarations sent at startup dropped from **16,827 characters to 12,907** — roughly a thousand tokens off every session, and five fewer wrong tools for the model to reach for.

### 🩹 Fixes
* An unanswering model was retried on **every call**, at 12–15 seconds a time, because only quota and 404 failures were ever cooled down. 503/504 now rest for 30 minutes — **11.2 seconds saved per call**.
* One-shot Gemini calls had **no timeout anywhere**, in any of the sixteen files that made them. Every call now carries a deadline of at least 10 seconds.
* YouTube playback failed outright with *"Requested format is not available"* — it was asking for a combined stream that no longer exists.
* Videos played in a **random language**, because YouTube's auto-dubs carry the same bitrate as the original track.
* The settings drawer **stuttered on first open** — a 2.1-second `openwakeword` import on the UI thread, not the button count it looked like.
* The settings drawer opened **underneath the video**, because `QVideoWidget` creates a native window.
* JARVIS **answered the video's soundtrack.** The microphone now follows the video's sound.
* Qt's multimedia backend printed an ffmpeg banner to the console on every play, containing the **signed streaming URL with the viewer's IP address in it**. Silenced at startup.
* **Every launch paid 201 ms for a plugin nobody had asked to use.** Discovery executes every file in `plugins/`, and `youtube_video` imported `requests` and `youtube_transcript_api` at module scope. Deferring one of them would have saved nothing — the transcript library imports `requests` itself. Both are now checked with `find_spec`, which answers "is it installed?" without executing anything, and loaded on first use: **plugin discovery 211 ms → 39 ms**.
* A plugin that needed a file from a **newer Mark** was rejected with *"pip install core"*. The loader could not tell this project's own packages from a third-party one, so it told people to install a same-named stranger from an index — wrong, and a supply-chain hazard dressed up as a fix. First-party names now say the app is behind the plugin and that there is nothing to install.

> Built on the Mark LI–LIV foundation: the **🧑‍🎤 Holographic Avatar**, **👄 Lip-Sync**, **🎚️ Push-to-Talk**, **🔇 Self-Echo Guard**, **🧩 Plugin System**, **♾️ Unlimited Sessions**, **🎨 Live Theming** and **🎙️ Wake Word** are all still here.

---

## 🦌 DeerFlow, natively — the research loop, not the platform

DeerFlow 2.0 is a **super-agent harness**: a LangGraph lead agent, a sub-agent
runtime, declarative skills, a sandbox, an MCP gateway, IM channels and a
Next.js console. Its harness alone is **756 Python files and 185,000 lines**;
the console wants Node 22 and pnpm, and the sandbox wants Docker. Bolting that
next to a single-process voice assistant would trade this app's one dependency
for four, and its one window for a second control plane.

What was worth taking is the loop that made DeerFlow useful, and that is what
`research/` now is — **six stages, one thread pool, no new dependency**:

| Stage | What happens | Why it is its own stage |
|---|---|---|
| **Plan** | the topic becomes 3–7 sub-questions, each with real search queries, plus the skills this topic needs | a plan you can read is a plan you can argue with |
| **Research** | per round: search in parallel → number the sources → fetch in parallel → one reader per question | reading is the slow part, and it is embarrassingly parallel |
| **Analyse** | the notes become one outline: claims, sources, contradictions, gaps, confidence | reconciliation is a different job from summarising |
| **Critique** | every claim is checked against the evidence and corrected before it is polished (deep runs) | prose hides a weak claim; an outline does not |
| **Read** | (theological runs) what the outline holds is said as a reading — subject, each item in its authority, each with its weight marked — and checked before it is spoken or filed | the only part of a run that is spoken and filed as doctrine-shaped prose cannot be left to the model's taste |
| **Write** | one call per section, then header, limits, sources and method are added by code | a long report should not depend on a single reply arriving intact |

### Three things that are structural, not prompted

**Citations cannot be invented.** Sources are numbered once, by the coordinator,
*before* anyone reads them. A reader cites the page it was handed; a section
writer can only cite numbers from the source list it was given; and `report.py`
parses every `[n]`, expands ranges, and **deletes any marker pointing at a source
the run never fetched**. A report that cites a page which does not exist is worse
than one that cites fewer, so the guarantee lives in code instead of in a
sentence asking the model to be careful.

**Gaps drive the next round.** Round two is not "search again". It is the
analyst's own list of unanswered questions, capped at three. When the first
round answered everything, the run stops early and says so — the budget is spent
on what is missing, not on repetition.

**A run survives its own failure.** Plan, sources, notes and pages are written
to disk as they arrive, `run.json` atomically. `resume` rebuilds the report from
the notes **without fetching a page again** — the test suite proves it by making
every search and fetch raise.

### When the vault cannot answer, it goes and finds out

The theology vault is the first place a theological question should be answered
from — it is local, it is the user's own reading, and it costs nothing. Its
weakness is the same as its strength: it only knows what was put in it. Until
now a miss produced *"No wiki page matches"* and nothing was learned.

`research/theology.py` closes the loop:

```
search  →  coverage measured  →  gap  →  deep run  →  report filed as synthesis
```

**A gap is measured, not guessed — and the question is measured as a SUBJECT,
not as a bag of words.** "peux-tu m'expliquer le concile de Chalcédoine" is
about one thing, and a vault that holds that thing answers it. So the framing of
the request (*explique*, *raconte-moi*, *peux-tu*) and the generic scaffolding
(*l'histoire de…*, *ses conséquences*) are removed before anything is compared,
and what is left is the subject. The vault is bilingual by nature — the
question is French, the source may be Latin or English — so words that have two
names are folded together: a page titled **Council of Nicaea** answers
*concile de Nicée*.

The subject of a question is the term the vault carries in a **title**: a page
titled *Chalcédoine* is a page written about Chalcédoine, while a page that
mentions it once in a paragraph is not. A question is a gap when the vault holds
no page about its subject, or when the rest of the question is nowhere in the
vault. Zero pages is a gap; an **empty** vault is not — a brain nobody uses yet
should not start buying reports. And a matching **raw** source is a lead, not a
hole: the cheap next move is to structure what you already own, so that case
does not trigger either.

**Nobody pays twice.** One run at a time, through the same `research/jobs.py`
the voice tool uses, with a 30-minute cooldown per question — and the cooldown
is **written down**, so closing the app is not a way to buy the same report
again, and asking the same question in different words is the same question. A
gap that arrives while a run is already paying for the web is **queued**, not
dropped, and served when that run is over. A **daily ceiling** (3 runs a day by
default) bounds the whole thing: a gap is a trigger, not a purchase order.

**The loop closes.** The finished report is written into the vault as a
`synthesis` page — attribution line, source URLs in the metadata, indexed and
pushed to XERJ like any other page — and its **title carries the subject**, so
the next question about that subject reads the vault instead of buying the
report again. The page opens with the **reading** (below), so what the vault
answers with on that subject is the reading itself, not five sections of
prose.

### The report is read back, not summarised

A deep report is a document: sections, claims, citations, a method. What the
user is owed when it finishes is not a document but a **reading** — the subject
first, then each point in the authority it speaks with, its weight marked, and
what stays open. The vault's searches already returned one; the research path
now composes one, and `research/reading.py` is where that happens.

**One composition, two surfaces.** The reading is composed once, from the
outline the run already produced — never from the web a second time — and
stored on the run. The spoken announcement and the synthesis page are two
renderings of that one structure. A reading said one way and filed another is
two readings, and the vault would eventually contradict the voice.

**The vocabulary is closed, and the check is ours, not the model's.** An
authority outside the five (Scripture, Tradition, magisterial teaching,
scholarship, practice and custom) or a weight outside the four (*defined*,
*commonly held*, *disputed*, *one author's opinion*) is not a reading, it is an
improvisation. Validation drops what falls outside — item by item, along with
every citation of a page the run never fetched — and drops the whole reading
when nothing valid is left. That matters because a reading is the one part of a
research run that is **spoken and filed as doctrine-shaped prose**: an
unverified authority is believed, not checked by the ear. A run whose reading
will not check still writes its report; it simply is not read back
theologically, and says so.

**It is only ever composed for a run the theology discipline governs** — which
is what the vault trigger always requests, what the planner selects for a
doctrinal or historical topic, and what `vault=true` now forces. A reading of
a market report that classified its evidence as *Tradition* would be a category
error dressed as a summary.

**Where it shows up:** the report, ahead of the sections that argue for it; the
`[RESEARCH_DONE]` announcement, which asks the model to relay the reading in
the user's own language rather than summarise the report; and the synthesis
page, where it is the first thing on the page — because a vault answer quotes
the head of a page, and a reading cropped mid-item is a reading the model
completes from memory.

Both search paths fire it: `theology_brain` (keyword) and `xerj_search`
(semantic, and its fallback when the engine is down). The ceiling, the
cooldown, the depth and the language are in the vault's settings section (⚙
Settings → THEOLOGY BRAIN), and the whole trigger can be turned off there too.

**The model knows what the vault holds.** A model cannot look for what it does
not know exists — so the vault's subjects are mirrored into the prompt, and the
assistant is told to search the vault before answering a theological question
from memory. A question answered from memory is a question the vault never
learns, and one that would otherwise be bought again on the next run.

### The vault is consulted before the answer, not after it

The mirror is a table of contents. The **consultation** is structural: the
application asks the vault itself, while the user is still speaking, and hands
what it finds to the conversation before the model writes a word.

```
user speaks  →  the vault is asked  →  [VAULT] the pages, with their text
                                      →  the answer comes from them, cited
```

`actions/_vault_router.py` decides, in a few milliseconds and without a model:

| what the message is | what happens |
|---|---|
| the vault holds pages whose **title** carries the question | those pages and their text are handed to the conversation |
| a religious subject the vault does **not** hold | a deep research starts — and the assistant is told to say so and to wait |
| anything else | nothing; the assistant answers as it would anywhere else |

The two halves cannot disagree: the router, the vault's search and the trigger
that spends money all use **one** tokenizer (`research/vocab.py`) and **one**
measurement. A question the search finds is a question the trigger does not
buy — the old version measured the question twice, with two different
tokenizers, and a search that found a page could still be answered twice.

A name or a date is not worth a report: *"who is the pope"* is answered from
what the assistant knows, and only a question the vault could not settle is
sent out to be researched.

**What comes back is read, not listed.** A vault of page titles is an index,
not an answer to a theological question. So every retrieval — the consultation
the application makes before the answer, the keyword search the model makes
itself, the semantic search over the same pages — carries the same **frame**:
name the subject the question is about, then take each item in turn and say
what it holds *on that question*, naming the authority it speaks with
(Scripture, Tradition, Magisterial teaching, Scholarship, Practice and
custom), and mark its weight — what is defined, what is commonly held, what is
disputed, what is one author's opinion. Then say plainly what the reading does
not settle.

One frame, one behaviour: it lives in the router
(`actions/_vault_router.py`), the light layer every search path already
reaches, so the answer cannot read as a summary on one path and as a reading
on another.

### From the chair

Say **« lance une recherche approfondie sur le concile de Nicée »**. The tool
returns in milliseconds and the run continues in the background: the HUD shows
the stage, the source count and the notes; when the report lands the assistant
speaks the three headline findings and puts the document on screen. Nothing in
the conversation is blocked while it works.

| You say | It does |
|---|---|
| « recherche approfondie sur X » | `standard` — 5 questions, ~18 pages, 2 rounds |
| « recherche rapide » / « à fond » | `quick` — 3 questions, ~8 pages / `deep` — 7 questions, ~30 pages, 3 rounds + critique |
| « où en est la recherche ? » | stage, sources, notes, elapsed |
| « montre le rapport » / « ouvre le rapport » | on the HUD / in the system's Markdown app |
| « annule la recherche » | stops at the next safe point, keeping what was read |
| « reprends la recherche » | rewrites the report from the notes, no new searches |
| « quelles compétences de recherche ? » | the skills a run can apply |

### Skills and sub-agents are files, not code

A **skill** is a Markdown file with a small frontmatter in
`Documents/Mark LV Research/skills/`. Five ship with the app:

| Skill | It changes how a run judges… |
|---|---|
| `sourced-brief` | what counts as evidence, and what must be labelled inference |
| `fact-check` | claim decomposition, primary sources, a verdict per claim |
| `comparative-analysis` | criteria before evidence, symmetric treatment, "no winner" allowed |
| `technical-due-diligence` | versions, matched benchmarks, licence, advisories |
| `theology-source-critique` | scripture / tradition / magisterium / scholarship kept apart, no anachronism |

The planner sees the catalogue and picks; a body is loaded only for the run that
chose it. A same-named file in your folder **overrides** the shipped one, so
tuning a skill never means editing the application.

A **sub-agent** is a Markdown file too, in `.../agents/`: frontmatter for
`name`, `description`, `tools`, `max_sources`, and the body is the system prompt.
Replace `researcher` and the reading changes; the rest of the pipeline does not
care.

### What is not ported, and why

| DeerFlow | Here | Why |
|---|---|---|
| LangGraph graph, checkpoints | a thread pool and `run.json` | one user, one run — a graph engine would be a second runtime to debug |
| Next.js console | the HUD's content panel | the window already exists, and voice is the input |
| Docker sandbox, `coder` sub-agent | **not ported** | executing model-written code unattended is a security decision this app does not make for you |
| MCP gateway, 30+ search providers, IM channels | DDG + Gemini grounded, the tools already installed | the app's promise is one key, no accounts |
| Long-term memory store (DeerMem) | `memory/long_term.json` | the app already has a memory with a prompt budget |

### Settings and files

Everything lives in `Documents/Mark LV Research/`:

```
Mark LV Research/
├── runs/<date>-<slug>/   # run.json · pages/ · notes/ · report.md
├── agents/*.md           # your sub-agents (optional)
└── skills/*.md           # your skills, overriding the shipped ones
```

| Key in `config/api_keys.json` | Default | What it does |
|---|---|---|
| `research_dir` | `Documents/Mark LV Research` | where runs, agents and skills live |
| `research_max_parallel` | `4` | readers working at the same time |
| `research_language` | `"auto"` | report language; `auto` follows the topic |
| `research_voice_summary` | `true` | speak the headline when a run finishes |
| `research_max_page_chars` | `4000` | how much of one page a reader is given |
| `theology_auto_research` | `true` | start a run when the vault has no coverage |
| `theology_auto_research_depth` | `"standard"` | `quick` / `standard` / `deep` for automatic runs |
| `theology_auto_research_language` | `"auto"` | report language for automatic runs |
| `theology_auto_research_cooldown` | `1800` | seconds before the same question may trigger again |

### Measured, not assumed

One `quick` run on *« Concile de Nicée et le Credo nicéen »*, on an ordinary
Windows machine with the app's own key: **111.5 s**, **6 sources**, **3 notes**,
a **5,658-character report** in French, every marker resolving to a source on
disk. Four of the six sources could not be read — three grounded answers with no
citable page and one PDF — and the report says so beside their numbers instead of
quietly dropping them.

The test suite runs the whole six-stage loop against a fake web and a fake
model: **68 tests, a few seconds, no network, no API key** —
`python tests/test_research_engine.py`.

## 🔄 The Foundation Update — in every Mark from LII

These four landed across **Mark LII, LIII, LIV and LV at the same time**, after each of those releases had already shipped. They are not what any one of those versions originally introduced; they are the floor all of them now stand on, so moving up a Mark never costs you something the one below it had.

No new dependencies. No bundled asset files. No hardcoded language, and nothing that assumes one operating system.

### 🧠 A memory that actually remembers

The store was capped at **2,200 characters — the whole memory, not per entry** — because all of it was pasted into the system prompt on every connect, so growing the memory grew every request. When it filled, the oldest entries were deleted and one line was printed to a console nobody reads. An assistant advertised as remembering "projects, preferences and personal context" was in practice a two-page notepad that quietly forgot your sister's name after a few weeks.

Storage and prompt budget are now separate problems:

* **Nothing is deleted.** The cap is a runaway guard normal use never approaches, and if it is ever hit it says so in the activity log instead of on stdout.
* **The prompt carries a core, not a dump.** Identity in full, then the most recently updated facts, budgeted — measured at **971 characters on a memory holding 62 stored facts.** That is *smaller* than the old whole-store cap, so sessions now connect with fewer tokens than before.
* **The rest is fetched on demand.** A `recall_memory` tool searches the full store locally — no network, no second model, well under a millisecond.

The part that is easy to get wrong: **a model cannot look something up if it doesn't know the thing exists.** So the prompt also carries an **index of the keys** it had no room for. Without it, "who is Ayşe?" gets "I don't know" while `ayse_sister` sits on disk unread. That index interleaves categories rather than sorting by recency — sorted like the core, a memory with forty preferences pushed the one entry the index existed for off the end.

⚙ → **🧠 MEMORY** shows every stored fact, when it was learned, and a ✕ to forget it. Everything stays in `memory/long_term.json` on your machine.

### ↩️ Undo — it can take back what it did

JARVIS moves files, renames them, writes to them and changes your settings. None of that had a way back; if it misheard you, the only remedy was to fix it by hand.

Say **"undo"** — in any language — and it reverses its own last action:

| | |
|---|---|
| **Files** | move · rename · create · copy · write · delete · organize desktop |
| **Settings** | volume · brightness · dark mode |

Three things it deliberately does *not* do:

* **It does not guess.** Settings undo reads the current value *before* changing it. Where a platform won't report that value, nothing is registered — an undo that restores a guess is worse than no undo.
* **It does not hoard.** Undoing a write means keeping the old contents in memory, so files over 1 MB are excluded and it says so rather than holding a 200 MB log for the session.
* **It does not delete your files to undo a copy.** The reverse of a copy is removing the copy; the reverse of "create a folder" is removing it *only while it's still empty*.

`organize_desktop` gets special treatment — one command that moves dozens of files, which made it the least reversible thing the assistant could do. It journals every move and puts all of them back in one go, cleaning up the folders it created if they're still empty.

**Undo costs nothing at runtime.** It appends a closure to a list; nothing in it runs unless you ask.

### ⚠️ A confirmation the model can't forge

The old gate read like this:

```python
if action in _DANGEROUS_ACTIONS:            # {"restart", "shutdown"}
    confirmed = str(params.get("confirmed", "")).lower()
```

`confirmed` is a **tool parameter, which means the model fills it in.** Nothing stopped it sending `confirmed=yes` on the first call and nothing checked that a human was ever involved. It was a convention, not a gate. And its coverage was two actions — so `toggle_wifi`, which cuts the assistant's own connection to the Live API and therefore *cannot be asked to undo itself*, went through with no gate at all.

The token is now issued by the interface. Shutdown, restart and WiFi put a banner on the HUD and **return immediately**; the action runs only if you press CONFIRM. Nothing blocks — JARVIS keeps talking while the banner is up — so this is **cheaper than the old gate**, which burned two tool round trips on every power command.

> The split between the two mechanisms is about reversibility, not about how alarming a word sounds. Anything undoable is done at once; only the genuinely irreversible asks. An assistant that checks with you before turning the volume down is one you stop talking to.

### 🎧 It finally asks which microphone

Both audio streams opened with no device argument at all, so they always took whatever the OS called "default" — and on Windows that *moves on its own* the moment you plug a headset in. "JARVIS can't hear me" almost always meant "JARVIS is listening to the webcam".

⚙ → **🎧 AUDIO DEVICES** lets you pick the microphone and the speakers by name. Two things matter more than the dropdown:

**The list is short.** `query_devices()` returns one entry per *device × host API*, not per device — measured on an ordinary Windows machine, **41 entries for what the sound settings show as 4 microphones and 4 speakers.** The same microphone appears four times, under MME, DirectSound, WASAPI and WDM-KS, with nothing to say which is which. That is not a choice, it's a quiz. The picker takes one host API per direction, drops the "Sound Mapper" and "Primary Sound Driver" pseudo-devices that just mean "default", and deduplicates. **41 → 8.**

**Every entry has been measured, not assumed.** The obvious approach is to pick the host API with the nicest names — WASAPI on Windows, which in shared mode **doesn't resample**, so with 16 kHz in and 24 kHz out against 48 kHz hardware every open failed. Adding a rate check and moving to DirectSound passes that test on both sides, and PortAudio's DirectSound **output is a silent sink**: the stream opens, every write returns success in ~0 ms, and not one sample reaches the speakers.

| | write(2.0 s) took | |
|---|---|---|
| MME | **2.02 s** | consumed in real time |
| DirectSound | **0.00 s** | swallowed instantly |

No capability flag reports that. So the app measures it — once per host API per direction, on a background thread at startup, using silence. Two consequences worth stating plainly:

* **Each direction picks its own host API.** On Windows this lands on DirectSound for the microphone and MME for the speakers — a split no amount of reasoning would have produced.
* **The probe runs in the mode the app actually ships.** DirectSound input passes a callback stream and fails a blocking read; probing the wrong mode rejected a microphone that works perfectly.

Your choice is stored **by name, not by index** — indices shift whenever something is plugged in. If the saved device is gone, it falls back to the system default and says so in the log rather than failing to start.

### 🔗 It stops forgetting the conversation when the connection drops

`session_resumption` was switched on in the config and the handle the server sent back was **never read** — so every reconnect started an empty session. A dropped packet, or simply changing the voice, wiped the conversation. "Unlimited sessions" leaked through exactly this hole.

The handle is captured and replayed now. A network blip, or switching your microphone, keeps the conversation intact.

It is held in memory only, deliberately: writing it to disk would make a fresh launch continue yesterday's chat, which sounds appealing but breaks the session-summary flow — a conversation that never ends never produces a summary, and the "yesterday we talked about…" line in the morning briefing silently disappears. Changing the **voice** also starts clean on purpose, since resuming restores the server's session state and would likely bring the old voice back with it.

### 🩹 Fixes that came with it

* **The assistant could die on a log line.** Status lines carry emoji and arrows (`📤 file_controller → Moved: a.txt → Documents/`). On a non-UTF-8 console — cp1254 on a Turkish Windows, cp1251 on a Russian one, cp932 on a Japanese one — printing one raises `UnicodeEncodeError`, and because that print sits *after* the tool's own `try/except`, it escaped into the receive loop and took the session down.
* **Every computer command paid for two model round trips.** `computer_settings` made an *entire second Gemini call, inside the tool*, purely to translate the request into one of its own action names — because the declaration only said "The action to perform", so the model rarely filled it in. When that second call failed, the fallback was `description.lower().replace(" ", "_")`, which turns the Turkish for "turn it down" into `sesi_kis` and straight into "Unknown action". The declaration now names all 56 actions and the rest is spelling tolerance handled locally by `difflib` in microseconds. When nothing matches it suggests real action names instead of dead-ending.
* An unresolvable saved audio device, or one the driver refuses to open, falls back to the system default and says so — on both the microphone and the speakers.
* A rejected session-resumption handle is dropped after one attempt, so an expired handle can never be replayed on every retry and prevent the reconnect it exists to protect.



---

## 🗺️ Mark Roadmap

| Mark | Focus |
|---|---|
| **XLIX** | Auto-start · clipboard intelligence · assistant customization |
| **L** | Session memory · background monitoring · proactive 2.0 · instant vision |
| **LI** | Plugin system · affective dialog · proactive audio · unlimited sessions |
| **LII** | Voice picker · live theming · reactive HUD · recallable memory · undo · real confirmation · audio device picker · session continuity |
| **LIII** | Wake word · Gemini 3.1 Flash Live · instant acknowledgment · self-describing action/plugin architecture |
| **LIV** | Holographic avatar · viseme lip-sync · facial acting · face-as-status · push-to-talk · self-echo guard · runtime self-knowledge & limits |
| **LV** | Video on the HUD · model ladder with measured fallback · split settings drawers · trimmed bundled skill list |
| *shared* | The last five above also shipped to LIII, LIV and LV at the same time — moving up a Mark never loses them |
| **LVI+** | Interrupt by voice · conversation history · Telegram remote · full file access · security camera · Obsidian |

---

## ⚡ Quick Start

```bash
git clone https://github.com/FatihMakes/Mark-LV.git
cd Mark-LV
python setup.py        # installs deps for YOUR OS + the browser automation engine
python main.py
```

`setup.py` only ever installs what your operating system needs — the Windows-only libraries are skipped automatically on macOS and Linux, and vice-versa. It also checks your Python version up front, so a wrong interpreter fails with a sentence instead of a wall of pip output. Prefer to do it by hand? `pip install -r requirements.txt` works too.

> ⚠️ **Installation Note:** If you hit a `ModuleNotFoundError` for an OS-specific package, install it with `pip install <module_name>`. The optional **wake word** engine is *not* installed here — grab it in one click from **⚙ → WAKE WORD** inside the app.

---

## 📋 Requirements

| Requirement | Details |
| --- | --- |
| **OS** | Windows 10/11, macOS, or Linux |
| **Python** | 3.11, 3.12 or 3.13 |
| **Microphone** | Required for voice interaction (and for the "Hey Jarvis" wake word) |
| **Speakers** | Required for voice replies |
| **API Key** | Free Gemini API key (entered on first launch → `config/api_keys.json`) |
| **GPU** | **Not required.** The avatar is rendered in software, and so is HUD video |
| **YouTube on the HUD** | `yt-dlp`, installed by `setup.py`. Without it, local files and direct URLs still play and YouTube links open in the browser with an explanation |
| **Wake word** *(optional)* | One-click download from ⚙ → WAKE WORD (`openwakeword`, a few MB, fully local) |

---

## 🗂️ Project Structure

```
Mark LV/
├── main.py                   # Core loop — Gemini Live session, audio I/O, viseme extraction, tool dispatch
├── ui.py                     # PyQt6 HUD — avatar canvas, waveform, log panel, settings drawer, camera feed
├── setup.py                  # OS-aware installer (skips wrong-OS dependencies, checks your Python)
├── .gitignore                # Keeps your API key, TLS key and memories out of the repository
├── plugins/
│   └── _template.py          # Copy this to write a new skill — one file, drop in, done
├── actions/                  # Bundled skills — each self-describes via a TOOL dict + handler
│                             #   Everything here drives the COMPUTER, which is what decides
│                             #   whether a new skill belongs in this folder at all.
│   ├── web_search.py         # Gemini + DDG parallel search (news, research, price, compare)
│   ├── screen_processor.py   # Screen & webcam capture for vision
│   ├── background_monitor.py # User-configured topic watching — daily DDG check
│   ├── proactive.py          # Proactive 2.0 — time/context/rotation-aware check-ins
│   ├── reminder.py           # OS-native scheduled notifications
│   ├── system_monitor.py     # CPU / RAM / GPU / temperature telemetry
│   ├── computer_settings.py  # Volume, brightness, WiFi, power (per-OS)
│   ├── computer_control.py   # Keyboard shortcuts, mouse, window management
│   ├── open_app.py           # Application launcher (per-OS name map)
│   ├── browser_control.py    # Web browser control
│   ├── file_controller.py    # File system operations
│   ├── file_processor.py     # Document reading and summarization
│   ├── send_message.py       # Messaging integration
│   ├── weather_report.py     # Live weather data
│   ├── deep_research.py      # Deep research — the voice entry point for research/
│   ├── video_player.py       # Plays video on the HUD, where the avatar normally is
│   └── desktop.py            # Desktop and taskbar control
├── memory/
│   ├── memory_manager.py     # Load/save long_term.json — sessions, monitors, identity
│   ├── config_manager.py     # api_keys.json access — key, OS, name, voice, colour, toggles
│   └── long_term.json        # Persistent store — created on first run
├── core/
│   ├── gemini.py             # One place for every one-shot Gemini call — model ladder, timeouts, cooldowns
│   ├── prompt.txt            # All prompt wording — {tokens} are filled from the live system at startup
│   ├── avatar.py             # Avatar renderer — lighting, pose, expression, mouth (QPainter)
│   ├── avatar_mesh.py        # Head geometry — loads the face, generates skull/neck/rigs
│   ├── face_model.obj        # The face itself (MediaPipe canonical model, Apache-2.0, 25 KB)
│   ├── viseme.py             # Transcript → mouth shapes, fused with the audio's timing
│   ├── echo.py               # Tells your voice from the assistant's own echo; self-calibrating
│   ├── hotkey.py             # Push-to-talk chord — global on Windows, windowed fallback elsewhere
│   ├── undo.py               # One shared undo stack — actions register how to reverse themselves
│   ├── confirm.py            # Irreversible-action gate — the token is issued by the UI, not the model
│   ├── audio_devices.py      # Microphone / speaker list — filtered, measured, resolved by name
│   ├── plugin_loader.py      # Plugin engine — discovery, validation, crash isolation
│   ├── action_loader.py      # Bundled-action engine — the built-in twin of plugin_loader
│   └── wake_word.py          # Local "Hey Jarvis" detector — own thread, offline, opt-in
├── research/                 # the research loop, native — no Node, no Docker
│   ├── engine.py             # plan → parallel readers → analysis → critique → read → write
│   ├── subagents.py          # planner / researcher / analyst / critic / theologian / writer
│   ├── skills.py             # declarative skills loader (Markdown, on demand)
│   ├── skills/               # the shipped skills themselves
│   ├── fetcher.py            # page → text, with a public-address policy
│   ├── search.py             # reuses actions/web_search.py — no second provider
│   ├── jobs.py               # one run at a time — shared by the voice tool and the vault
│   ├── theology.py           # vault gap → deep run → synthesis page
│   ├── store.py              # runs on disk: plan, sources, notes, report, resume
│   ├── reading.py            # the reading: closed vocabulary, checked before it is said
│   ├── report.py             # citation validation and report assembly
│   ├── llm.py                # every call through core/gemini.py
│   └── config.py             # settings and folders
├── tests/
│   └── test_research_engine.py  # 68 tests, no network, no key
└── config/
    ├── api_keys.json         # API key, name, voice, colour, toggles — created on first launch (git-ignored)
    └── certs/                # Self-signed TLS pair for the phone dashboard — generated locally (git-ignored)
```

---

## 🙏 Third-Party Assets

| Asset | Source | Licence |
| --- | --- | --- |
| `core/face_model.obj` | [MediaPipe](https://github.com/google-ai-edge/mediapipe) canonical face model — 468 vertices of measured human face geometry | Apache License 2.0 |
| Research loop design | [bytedance/deer-flow](https://github.com/bytedance/deer-flow) — the plan / research / analyse / critique / write pipeline | MIT. Ideas reimplemented in Python here; no code vendored |

---

## 🔒 Your Data

Everything stays on your machine. There is no MARK server, no telemetry and no account.

| What | Where | Notes |
|---|---|---|
| Gemini API key, plugin credentials | `config/api_keys.json` | **Plaintext.** Anyone with your user account can read it. Treat it like a password file. |
| Dashboard TLS certificate + private key | `config/certs/` | Generated locally, self-signed, never leaves the machine. |
| What the assistant remembers about you | `memory/long_term.json` | Delete the file to make it forget everything. |

All three are listed in `.gitignore`, so a fork or a pull request cannot leak them by accident. **If you have already committed `config/api_keys.json` anywhere public, revoke that key** at [aistudio.google.com](https://aistudio.google.com/app/apikey) and generate a new one — removing the file in a later commit does not remove it from the history.

Your voice is streamed to Google's Gemini Live API while a session is open; that is the one thing that leaves your computer, and it stops when you mute or close the app.

---

## ⚠️ License

Personal and non-commercial use only.
Licensed under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**.

---

## 👤 Connect with the Creator

Engineered by a developer building a real-world JARVIS-style assistant.
⭐ **Star the repository to support the journey to Mark 100.**

| Platform | Link |
| --- | --- |
| YouTube | [@FatihMakes](https://www.youtube.com/@FatihMakes) |
| Instagram | [@fatihmakes](https://www.instagram.com/fatihmakes) |
