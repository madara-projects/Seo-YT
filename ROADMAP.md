# YouTube Growth Tool Roadmap

## The goal

Build a private, local tool that helps you make better video decisions before publishing and learn from your own YouTube results after publishing.

It will not promise 90% or 100% growth. Nobody can guarantee that: YouTube recommendations depend on how viewers choose, watch, enjoy, and return to videos. The tool will instead help us improve the things we can control: topic choice, title, thumbnail idea, first 30 seconds, description, and learning from real performance.

## Cost rule

The target cost is **$0 per month**.

- Run the app and database on your own computer with Docker.
- Use the free YouTube Data API and YouTube Analytics API within Google's default quota.
- Use Ollama locally for writing titles and descriptions. It runs on your computer, so there is no per-request charge.
- Do not add paid AI, paid keyword tools, cloud hosting, or subscriptions unless you explicitly decide to later.

Ollama should stay. It is the part that writes natural titles, descriptions, and Tamil/Tanglish output. Removing it would leave only rigid templates, which would make the quality worse. We will remove the weak silent template fallback and show a clear message when Ollama is unavailable instead.

## How we will work

Complete one stage, test it with a few real video ideas, and only then begin the next stage. Every stage has a clear finish line.

---

## Stage 1 — Better video input (complete)

### Problem today

The tool mainly receives one text box. A vague idea such as “my office vlog” does not give it enough information to make a strong title.

### Build

Replace the single-input workflow with a simple creator brief:

- What happens in the video?
- Who is the viewer?
- What will the viewer get, learn, feel, or see?
- What is unique about your video?
- What proof do you have: result, story, footage, before/after, experiment?
- Video type: vlog, tutorial, Short, review, story, challenge, etc.
- Language and target location.
- Preferred title style: searchable, curiosity-led, or balanced.
- Optional thumbnail idea.

The tool should turn this into a structured internal brief before researching or writing.

### What you will see

Instead of one generic package, you will see a clear statement such as:

> Audience: young Tamil working professionals. Promise: the honest reality of balancing a 9-to-5 job and content creation. Proof: real commute, office, and evening workflow footage.

### Done when

You can submit a complete brief in under two minutes, and the tool warns you when the idea is too broad or has no clear viewer promise.

---

## Stage 2 — Stronger research and packaging (complete)

### Problem today

The tool searches YouTube using the opening part of your text and sees only a small number of competitors. It creates titles, but it does not properly choose the best angle to compete with.

### Build

For every brief, generate several research searches:

- Main topic
- Viewer problem
- Desired result
- Local-language / Tamil / Tanglish variation
- Video-format variation
- Competitor framing

Then group competitor titles by pattern and identify:

- Repeated promises
- Repeated thumbnail styles
- Strong videos from smaller channels
- Viewer questions competitors do not answer well
- A specific angle for your video to own

### What you will see

The tool should give a decision, not just a list:

> Do not use “Daily Office Vlog.” Use “The Real 9-to-5 + Creator Life in Chennai” because competitors are generic and your personal proof is the differentiator.

### Done when

Each analysis shows a recommended angle, the reason it is different, and the competitor patterns to avoid copying.

---

## Stage 3 — Title + thumbnail packages (complete)

### Problem today

A title alone is not enough. Viewers decide using the title and thumbnail together.

### Build

Generate 5 to 8 complete packages. Each package must include:

- Title
- Thumbnail visual idea
- Thumbnail text, limited to 2–4 words
- Viewer promise
- Why someone would click
- Whether it is searchable or curiosity-led
- Risk of being misleading

Add a quality gate. The tool must reject titles that are vague, clickbait, unrelated to the video, too long, or too similar to competitors.

### What you will see

You choose from packages, not isolated titles:

| Package | Title | Thumbnail text | Best for |
|---|---|---|---|
| A | The Real 9-to-5 + Creator Life in Chennai | NO TIME LEFT | Browse / relatable viewers |
| B | How I Create Content After a Full-Time Office Job | 6 PM START | Search / aspiring creators |

### Done when

You can confidently choose two honest title-thumbnail packages before publishing.

---

## Stage 4 — Connect your YouTube channel (complete)

### What this adds

This is the most important stage. It lets the tool learn from **your actual channel**, not generic guesses.

### Build

1. Create a Google Cloud project.
2. Enable YouTube Data API v3 and YouTube Analytics API.
3. Create local desktop/web OAuth credentials with `http://127.0.0.1` as the redirect URL.
4. Add a **Connect YouTube Channel** button to the dashboard.
5. Ask for the smallest read-only permissions needed:
   - `https://www.googleapis.com/auth/yt-analytics.readonly`
   - a read-only YouTube scope only if required to list the creator's videos/channel details
6. Store the encrypted refresh token locally; never send it to another service.
7. Add a **Disconnect Channel** button that deletes the saved token.

### Dashboard to add

- Channel overview: views, watch time, subscribers gained, returning viewers
- Last 28 days compared with the previous 28 days
- Best and weakest recent videos
- Per-video: impressions, CTR, average view duration, average percentage viewed, likes, comments, traffic source where available
- Audience / device / geography summaries when Analytics makes them available

Google requires OAuth for private channel data, and channel reports can be queried for the authenticated channel using `channel==MINE`. [YouTube OAuth guide](https://developers.google.com/youtube/v3/guides/authentication) · [YouTube Analytics channel reports](https://developers.google.com/youtube/analytics/channel_reports)

### Done when

You can connect your channel, see the latest 28 days inside this dashboard, refresh the data, and disconnect safely.

---

## Stage 5 — Learn from published videos

### Problem today

The existing history tracks tool analyses, not the results of videos you actually published. It cannot tell whether your title choices worked.

### Build

For every published video, save:

- Video ID and publish date
- Topic, audience, format, language, and selected angle
- The title and thumbnail package selected
- Impressions and CTR after 24 hours, 7 days, and 28 days
- Average view duration and percentage viewed
- Retention at the opening and major drop-off points when available
- Views, likes, comments, shares, subscribers gained, and traffic sources

Then compare similar videos, not unrelated ones. For example: Tamil work-life vlogs compared with other Tamil work-life vlogs.

### What you will see

Useful findings such as:

> Your work-life videos with a specific personal outcome have a better early CTR than generic “daily vlog” titles. Their retention drops after the intro, so the next video needs a faster opening.

### Done when

The tool shows evidence-based recommendations based on at least 10 published videos in one content group.

---

## Stage 6 — Test, improve, repeat

### Build

- Keep the two best packaging packages for each video.
- Flag videos with low impressions and below-usual CTR.
- Recommend a title/thumbnail change only when the video is underperforming.
- Record what changed and compare results afterwards.
- Build a small evaluation set of real video briefs to ensure new changes improve output quality rather than adding noise.

Do not constantly change videos that are already working. YouTube notes that title or thumbnail changes can help or hurt because viewers respond differently to the new packaging. [YouTube recommendation guidance](https://support.google.com/youtube/answer/16559651?hl=en)

### Done when

Every change has a reason, a before/after record, and a measurable result.

---

## What matters most for growth

| Priority | What the tool should improve |
|---|---|
| 1 | Pick a video idea with a clear audience and promise |
| 2 | Make title and thumbnail work together |
| 3 | Deliver the promise in the first 30 seconds |
| 4 | Keep the viewer interested through the whole video |
| 5 | Learn from your own Analytics data |
| 6 | Write a clear description |
| 7 | Add relevant tags; do not over-focus on them |

YouTube describes discovery as a combination of appeal, engagement, and satisfaction. Titles, thumbnails, and descriptions matter, but tags are primarily useful for common misspellings. [YouTube performance guidance](https://support.google.com/youtube/answer/16559650?hl=en) · [YouTube tags guidance](https://support.google.com/youtube/answer/146402?hl=en-EN)

## First task when we start

Start with **Stage 1**. It is cheap, quick, and gives every later stage better information. Do not connect YouTube Analytics until the tool first understands what kind of video you are trying to make.

## What we will not do

- No paid AI API by default
- No paid SEO or keyword subscriptions
- No guaranteed growth percentage
- No misleading clickbait
- No automatic uploading or automatic changing of live video metadata without your approval
