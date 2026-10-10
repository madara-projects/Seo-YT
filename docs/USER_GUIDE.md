# Win-Engine OS — Complete User Guide
### *The Creator Intelligence Operating System for YouTube* (v0.13)

Welcome to **Win-Engine OS**! This guide will help you get the most out of your local-first YouTube SEO and creator intelligence workstation.

---

## ⚡ Quick Start: 3 Steps to Launch

```
1. Start Docker  ──▶  2. Open Browser  ──▶  3. Connect Channel & Create
   docker compose up    http://127.0.0.1:8000   Settings ➔ Creator
```

1. **Start the Engine**: Put your keys in `.env` (see the README section "Configuration"), create the data folder once (`mkdir runtime/data`, or `New-Item -ItemType Directory -Force runtime/data` in PowerShell), then run `docker compose up -d --build` in your project folder.
2. **Open the App**: Go to **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. The address opens **Creator**. Use `127.0.0.1` rather than `localhost`: the YouTube OAuth callback is registered on `127.0.0.1`.
3. **Check Settings**: Open **Settings** (the last item in the sidebar, under *System*), connect your YouTube channel and check that the AI & data providers show as configured. Keys are not typed into the app; they live in `.env`.

The sidebar groups the pages as **Studio** (Dashboard, Creator, AI Shorts, History), **Performance** (Channel), **Research lab** (Ideas, Demand, Audits, Experiments, Watchlist) and **System** (Settings). On a desktop it folds into an icon rail with the button at its top or **Ctrl+B**.

> [!TIP]
> **Theme Switching**: The sun/moon button in the top bar switches between light and dark. **Settings ➔ Appearance ➔ Theme** also offers **System**, which follows your operating system. The choice is saved in this browser only.

---

## 🔄 The 6-Step Creator Loop

Win-Engine OS follows a continuous learning loop that connects your pre-production ideas with post-publication YouTube performance:

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  1. IDEA    │ ──▶ │ 2. RESEARCH  │ ──▶ │  3. PACKAGE  │
│    Ideas    │     │ Demand/Watch │     │   Creator    │
└─────────────┘     └──────────────┘     └──────────────┘
                                                │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  6. LEARN   │ ◀── │   5. AUDIT   │ ◀── │  4. PUBLISH  │
│ Experiments │     │    Audits    │     │YouTube Studio│
└─────────────┘     └──────────────┘     └──────────────┘
```

| Step | Workspace | What You Do |
| :--- | :--- | :--- |
| **1. Idea** | **Ideas** | Save video ideas in your private backlog, research them and carry the strongest into a package. |
| **2. Research** | **Demand** and **Watchlist** | Take dated snapshots of what YouTube showed for a topic (no invented search volume) and follow channels and videos as benchmarks. |
| **3. Package** | **Creator** or **AI Shorts** | Generate title options, a description, tags and hashtags from your script or idea. For an AI-made quote Short, AI Shorts also writes the Google Flow prompts. |
| **4. Publish** | *YouTube Studio (Manual)* | Copy your selected package into YouTube Studio and upload your video yourself. |
| **5. Audit** | **History** and **Audits** | Link the uploaded video to its package in History, then compare what you generated with what went live and how it has performed. |
| **6. Learn** | **Experiments** | Compare a Control and a Variant across your own published videos, reported as directional evidence. |

---

## 🛠️ Complete Workspace Breakdown

---

### 1. Dashboard

Your overview of channel numbers, package quality signals and what the tool has learned so far. Every card says when its data is unavailable or the channel is not connected instead of showing a number.

- **Key numbers**:
  - **Views (28 days)**: the real 28-day figure from YouTube Analytics, once your channel is connected and synced.
  - **Estimated watch time**: from the same 28-day sync, or from your linked videos.
  - **Avg opportunity score** and **Avg title quality**: both marked *Heuristic*, with the change against the previous window. Title quality is a local heuristic, not measured CTR.
- **Start a new SEO package** and **Connected channel**: a quick way into Creator, and your channel's snapshot.
- **Title quality by content angle**, **Learning confidence** and **Retention risk spread**: learning from results starts only once enough comparable videos have matured.
- **Recent packages** and **Highest-scoring titles**: your latest saved packages.
- **Does the Opportunity Score track your results?**: compares past scores with the results of your published videos within comparable groups. It says when there is not yet enough evidence, and recommends keeping, recalibrating or retiring the score only once there are enough videos.

---

### 2. Creator (The Core Engine)

Creator turns your script or idea into a ready-to-upload title, description and tags. It is one input screen followed by four result tabs. Nothing here uploads, publishes or changes a YouTube video.

#### The input screen
1. **What are you making?**: **Short** (vertical, up to 3 minutes: `#shorts` leads the hashtags but is not forced into the title, a focused tag set ending with the `yt` and `shorts` platform tags, no chapters), **Long video** (over 3 minutes, with an optional kind such as Tutorial, Vlog or Review: no `#shorts`, chapters only from your own timestamps) or **Not sure — detect it for me** (the format is inferred and labelled as inferred).
2. **Your script or idea**: paste the script, then fill in the brief fields that apply, such as *Who is it for?*, *What will viewers get?*, *What makes it different?*, *Proof you can show*, *Facts stated in the video*, *Claims to avoid*, *Thumbnail idea* and *Title style* (Balanced, Searchable or Curiosity-led). Quote and visual fields include *On-screen quote or text*, *Background visuals*, *Voice-over* and *Length (seconds)*.
3. **Language and region**: *Output language*, *Spoken language* and *Region*.

#### The four result tabs
| Tab | What it holds |
| :--- | :--- |
| **Package** | The title, description, hashtags and video tags with copy buttons, the thumbnail direction, a preview and the Opportunity Score. |
| **Compare options** | Every option side by side: its approach, what it is best for, its intent and its title quality. |
| **Research and insights** | The creator brief and where each field came from, the YouTube research (queries run, public results, keyword signals, warnings), the research-backed tag selection, the content angle and the hook, pacing and retention assistant. |
| **Before you publish** | Why the package was suggested, the pre-publication scoring, the manual pre-publish checklist and the upload package to copy. For a long video it also prepares a **YouTube Studio test (Test & Compare)**: up to three title and thumbnail variants for YouTube's own A/B test. |

What to expect in a package:
- **Title options**: up to five validated titles. When fewer pass the quality checks, fewer are returned rather than padded. Each option's label says what that title does (a Short's options carry "Shorts feed").
- **Description**: written for viewers. Chapters appear only for a long video whose script includes valid chapters of your own: the first at `0:00`, at least three, each at least 10 seconds, with the last checked against the length you gave. Shorts get no chapters, and timestamp lines you did not supply are removed.
- **Tags and hashtags**: chosen for the format, with the evidence for each tag in the Research tab.
- **Research**: 25 results per YouTube search by default (up to 50 with `WIN_ENGINE_YOUTUBE_MAX_RESULTS`). A Short is compared only with Shorts.
- **Source label**: each result says whether it was **Written with Gemini** or is a **Local fallback**.

#### 💡 Example Input for a Quote Short:
```text
What are you making?     Short
Script                   The hardest part of healing is accepting that they were never sorry.
On-screen quote or text  The hardest part of healing is accepting that they were never sorry.
Background visuals       Rainy neon-lit street at night with steady camera pan
Voice-over               No voice-over
Length (seconds)         15
Who is it for?           Young adults navigating breakups and self-worth
```

If you want the Short itself made with AI video, use **AI Shorts** instead.

---

### 3. AI Shorts

Type a quote and get Google Flow (Veo 3.1) prompts for each 8-second part, plus the title, description, hashtags and tags for the Short. Nothing here uploads or publishes.

- **Your quote**: you type only the **Quote**, exactly as it should appear on screen. You can add an optional **Mood or scene wish**, pick the **Length** (1, 2 or 3 parts of 8 seconds each; 2 by default) and the **Package language**.
- **Flow prompts**: Gemini writes one prompt per 8-second part. Part 1 goes into Flow's Text to Video; each later part goes into Flow's Extend, so the parts chain into one Short. Each prompt has its own copy button, and there is a **Copy all prompts** button.
- **Generate it in Flow**: step-by-step Flow instructions with cautions to keep in mind. For Flow plan and output details, see the Flow guide on the AI Shorts page.
- **Text on screen**: which line shows during each part. The quote is kept exactly as you typed it; add the text in your editor, not in the Flow prompt. The first line must be on screen from the very first frame, large and high-contrast, with no typing animation or fade-in.
- **Mood and audio**: how Gemini read the quote (its meaning, emotion and tone, and how viewers search for quotes like it), the chosen scene and why it fits, then the pace, palette, audio and a negative prompt to copy.
- **How the scene is chosen**: Gemini first reads the quote's plain meaning, its one emotion and who would feel it, then names its tone, which sets the light (night or blue dusk for sad and lonely quotes, sunrise or golden hour for hopeful and healing ones, cold pre-dawn for discipline). It writes three real moments a camera could film and keeps the one a stranger would understand from a single frame, avoiding scenes used in your recent AI Shorts. Symbols that need explaining (clocks, wrapped objects, masks), figures of speech, crowds, stillness, and heights or ledges for sad quotes are refused or repaired before you see the prompt. These are creative suggestions, not a guarantee of the footage Flow will generate. Old saved plans remain unchanged.
- **SEO package**: a lean Shorts package (title options, description, hashtags and video tags) built from that reading of the quote. The exact quote leads the titles when it fits; each title ends with an emoji that fits the quote and #shorts. The description is the exact quote, one reflective line and the hashtags (#shorts, #quotes and one that names the quote's theme). The video tags are 3 to 5 phrases viewers search for quotes like this one, checked against YouTube's search suggestions (free; no YouTube Data API quota is used), then yt and shorts. A package is GREEN only with at least three subject tags, two of them specific to this quote rather than broad ones like "deep quotes". One request makes at most six Gemini calls: the quote's reading and scene, prompt writing and an optional repair, then package writing with room for one repair and one refinement. Quality checks assess source fidelity, not predicted views; the Opportunity Score remains unmeasured.
- **History**: each plan is saved with its package as a History run. History marks that run as **AI Shorts** and links back to the plan with **Open AI Short**. Plans stay on this device: cloud sync carries only the History run, never the plan.
- **Did it work?** The tool checks the prompts, not the footage. Watch each clip in Flow before you use it and regenerate a part that drifts, shows text or a face, or doesn't match the feeling. After you publish, link the Short to its run in History: its 24-hour, 7-day and 28-day snapshots then appear in History and among the linked-video snapshots on the Channel page, beside your other Shorts.
- **When Gemini is unavailable**: the draft comes from a built-in template and says so, with a **Retry with Gemini** button.

---

### 4. Ideas

Your private backlog of video ideas. Research each one with real YouTube data, check demand, and carry the strongest into a package.

- **Backlog**: search your ideas and filter them by status: `Idea`, `Scripted`, `Package generated`, `Published` or `Archived`.
- **Idea detail**: shows how far an idea has come (Idea ➔ Script ➔ Package ➔ Published) and lets you research it, check its demand and mark it as scripted.
- **New idea form**: capture a new idea and its details.

---

### 5. Demand

See how much interest a topic shows before you film it. Every result is a dated snapshot of what YouTube showed that day, with no invented search volume.

- **Classifications**, from fixed rules over the sampled results:
  - `Strong observed interest`: at least 8 results from at least 4 channels, at least 3 of them recent, plus an outlier or enough engagement readings.
  - `Active topic`: at least 5 results from at least 3 channels, at least 2 of them recent, with view counts.
  - `Emerging signal`: 3 or more sampled results, with a recent upload or coverage from at least 2 channels.
  - `Insufficient evidence`: the sampled results were too sparse to classify interest in this topic.
- **Snapshot detail**: why the topic was classified that way, the public videos that were sampled, matching Watchlist outliers, whether your own published videos can add evidence, and the limits of what was measured.

---

### 6. Watchlist

Channels and videos you follow for ideas and benchmarks. Each refresh saves a dated snapshot of public numbers; nothing here touches your own channel.

- **Watching**: switch between the **Videos** and **Channels** tabs.
- **Watch something new**: add a channel or video to follow.
- **Possible outliers**: a video is compared with at least five comparable recent uploads from the same watched channel. The median, multiplier, sample, capture time, format and limitations are shown. With too few uploads the result is *insufficient evidence*, never a made-up score.

---

### 7. Audits

Check what actually went live against the package you generated, and how each video has performed since. Every audit is a dated record, and none claims to know why a video performed.

```
1. GENERATED  ──▶  2. SELECTED  ──▶  3. PUBLISHED  ──▶  4. OBSERVED
```

- **Generated**: what the tool suggested.
- **Selected**: what you chose.
- **Published**: the metadata that actually went live on YouTube.
- **Observed**: dated public numbers such as views, likes, comments and average viewed.

---

### 8. Experiments

Test one content decision at a time across your own published videos. Results use your verified YouTube analytics and never change your channel.

- **Set it up**: give the question a name and hypothesis, describe the two sides (**Control** and **Variant**), then choose how it is measured: the primary metric, the window and the number of videos needed per side.
- **Assign videos**: put each verified video on the Control or Variant side, or keep it as a reference only.
- **Directional evidence**: results are reported as directional observations, not causal claims.

---

### 9. Channel and History

- **Channel**: real, read-only numbers from your connected channel: this period against the last, recent and all uploads, your linked packages, what the tool has learned from them, and the leading comparable videos.
- **History**: the package library, a searchable archive of every saved package with copy buttons. From a package you can link its published YouTube video, see what that video has done since, request its retention curve with **Check retention curve**, and, for a long video, prepare or record a YouTube Studio Test & Compare. Runs made on the AI Shorts page are marked **AI Shorts** and link back to their plan.

---

### 10. Settings

- **YouTube channel**: connect your YouTube channel with **read-only** OAuth permissions.
- **AI & data providers**: whether Gemini and YouTube are configured, and today's YouTube quota use. **Run live check** runs live diagnostics only when you press it.
- **Cloud sync**: optional and off by default. When on, it mirrors History to your own MySQL database.
- **Local database**, **Snapshot collector**, **Appearance** (theme) and **About**.

API keys and other settings live in `.env`, not in the app or the database.

---

## 🔒 Safety & Truth Boundaries

> [!IMPORTANT]
> **Our Core Guarantees:**
> 1. **Zero Auto-Publishing**: This tool will **never** automatically upload, modify, or delete videos on your YouTube channel. All publishing is done manually by you in YouTube Studio.
> 2. **Read-Only YouTube OAuth**: Permissions are strictly limited to reading channel metadata and analytics.
> 3. **No Fake Numbers**: We never show invented search volumes or promise guaranteed virality. Numbers are either observed YouTube data or clearly labelled heuristics.
> 4. **Local-First, Not Offline**: Your database (`runtime/data/win_engine.db`) lives on your machine, but some data does leave it: your scripts and quotes are sent to Gemini to write packages and prompts, research queries go to YouTube, and optional cloud sync (off by default) mirrors History to your own MySQL database.

> [!NOTE]
> **YouTube quota**: `search.list` has its own bucket of 100 calls a day; the other reads this app makes cost 1 unit each from a bucket of 10,000 a day. Settings shows today's use, and research warns you once a bucket reaches 90%.

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><strong>Q: Why do my title scores say "Heuristic" instead of guaranteed CTR?</strong></summary>
No algorithm can guarantee human click-through rate. Title quality is a local heuristic built from structural checks such as length, clarity and keyword placement. It helps you compare options, but it is not a CTR prediction.
</details>

<details>
<summary><strong>Q: What happens if Gemini API quota runs out?</strong></summary>
The tool falls back to its built-in rule-based writer instead of failing. Creator labels such a result <strong>Local fallback</strong>, and AI Shorts says the draft came from the built-in template and offers <strong>Retry with Gemini</strong>. Review a fallback package carefully before you use it.
</details>

<details>
<summary><strong>Q: How do I switch between Dark and Light mode?</strong></summary>
Use the sun/moon button in the top bar, or choose <strong>Light</strong>, <strong>Dark</strong> or <strong>System</strong> under <strong>Settings ➔ Appearance ➔ Theme</strong>.
</details>

<details>
<summary><strong>Q: How do I backup my data?</strong></summary>
Your ideas, packages and audits are stored locally in <code>runtime/data/win_engine.db</code>; you can copy this file while the app is stopped. Before a database schema migration the app also makes a verified backup in <code>runtime/data/backups/</code> and keeps the newest ten. Settings such as API keys live in <code>.env</code>, not in the database, so back that file up separately.
</details>
