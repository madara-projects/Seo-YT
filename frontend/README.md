# Win-Engine frontend

React + TypeScript + Vite rebuild of the Win-Engine dashboard. It runs beside the
existing interface rather than replacing it: both interfaces use the same API and
SQLite database.

| Route | Serves |
|---|---|
| `/next` | This React app |
| `/`, `/app`, `/dashboard_view` | The classic dashboard |

Every page is now migrated. `/` and `/app` still serve the extracted dashboard;
switching them over to React is a separate step.

## Stack

React 18, TypeScript (strict), Vite 6, Tailwind CSS 4, Radix UI with vendored
shadcn/ui components, TanStack Query, React Router 7, React Hook Form + Zod,
Lucide, Sonner, and Vitest with React Testing Library.

React 18 rather than 19 is deliberate: every library above is stable on 18,
and the app gains nothing from 19's new features today.

## Commands

```bash
npm install
npm run dev        # http://localhost:5173/next/, proxies the API to 127.0.0.1:8000
npm run build      # builds into ../win_engine/api/static/app/
npm run test       # Vitest
npm run typecheck  # tsc --noEmit
npm run gen:api    # regenerate src/api/schema.d.ts from the running backend
```

The dev server proxies `/analyze`, `/api`, `/health`, `/meta`, `/diagnostics`,
`/ready`, `/youtube`, and `/oauth` to the Docker backend, so the app is
same-origin in both development and production and the API client never needs a
base URL.

`index.html` has no inline script or event handler, so the server's Content
Security Policy can forbid inline scripts. The pre-paint theme switch is
`public/theme-init.js`, served at `/app-assets/theme-init.js` when built and at
`/next/theme-init.js` by the dev server.

Switching themes is one step (`transitionTheme` in `src/lib/theme.tsx`): a
250 ms View Transition cross-fade where the browser has one, otherwise a shared
250 ms colour transition on every element for the length of the switch, and an
instant change with reduced motion. Elements' own colour transitions are held
off meanwhile, so nothing animates on its own timing. The desktop sidebar folds
to an icon rail (the button in its header, or Ctrl/⌘ B), remembered in
`localStorage`.

## API types

`src/api/schema.d.ts` is generated from the live FastAPI OpenAPI document and
should not be hand-edited — run `npm run gen:api` with the backend up.

It covers the request contract and the top-level response scalars. It does not
usefully describe the nested analysis structures: those are declared as bare
`dict` in the Pydantic models, so they generate as `Record<string, never>`,
which makes every real field access a type error. `src/api/types.ts` hand-writes
view models for the shapes the UI reads. Narrowing the Pydantic models would let
those be generated too.

## Conventions

**Provenance is part of the data.** The product never presents a guess as a
measurement, so values are paired with where they came from via `EvidenceChip`.
The tone carries meaning: `ok` is creator-supplied, `info` is a public
observation, `warn` is a heuristic or inference, `neutral` is unavailable, `bad`
is a failure. "Unavailable" is a real result and renders as one — never as a
zero, a blank, or an em dash.

**Analysis is slow and expensive.** One `/analyze` run currently takes one to
three minutes and spends real YouTube quota plus several Gemini calls, so the
mutation never retries and has no client-side timeout. `AnalysisProgress` shows
elapsed time and the expected range rather than a synthetic percentage, because
the backend emits no progress events.

**Pages are fluid.** Page content fills the main area inside its gutters
(2.5rem from `lg`, 3.5rem from `2xl`) and stops growing at `--container-page`,
120rem: 1536px at the desktop 80% scale, so 1280–1680px screens use their full
width and a 1920px screen keeps even margins. The top bar uses the same gutters
and cap, so its edges line up with the page. Grids are balanced per breakpoint
rather than stretched: a 3:2 split up to `2xl` and three columns from `2xl` on
the Dashboard and Channel, two-up Settings cards from `2xl`, and detail panels
that flow their sections down two columns from `2xl` (the `detail-flow`
utility; `detail-span` runs a block across both). Cards sit on one 1.25rem
spacing scale. Long text keeps an 80-character measure however wide its card
(`main p` in `styles/index.css`; a boxed paragraph keeps its box's width). The
Creator's setup puts the form beside a sticky "Your package" panel from `xl`;
narrower, it is one column with Generate in a bottom bar.

## Design system

The look is a "studio console": a dark sidebar in both themes, cool ink
neutrals, and a violet brand. Tokens live in `src/styles/index.css` as oklch CSS
variables with a `.dark` override, mapped into Tailwind through `@theme inline`.

- **Two brand colours on purpose.** `--primary` fills solid controls and keeps
  white text at WCAG AA in both themes; `--brand` is for brand-tinted text and
  icons and is lighter in dark mode, where the fill colour would fail AA as
  text. Use `text-brand`, not `text-primary`, for coloured text.
- **The gradient is decoration only** (logo, glows, the current step). It never
  carries meaning. Buttons that use it (`variant="gradient"`) draw from separate
  `--cta-*` stops that keep white text at AA.
- **Type:** Bricolage Grotesque for display (page titles, card titles, big
  numbers), Geist for UI text, Geist Mono for tabular figures. Fonts load
  without blocking the first paint, so the app renders at once, and offline, in
  system fonts.
- **Building blocks:** `PageHeader` (eyebrow, the page's only `<h1>`, actions),
  `Panel` (icon, title, description, a chip or actions), `StatCard`,
  `EvidenceChip`, `Delta`, `Meter`, and the shared empty, error and loading
  states. New pages should compose these rather than style cards by hand.
- **Research pages share one shape:** a `ListPanel` of `SelectableItem`s
  beside an inspector, with the open record in the URL through `useSelection`
  (`?idea=`, `?video=`, `?link=`), so any record can be linked to. `StepFlow`,
  `PublicVideoList`, `SavedRunNotice` and `ConfirmDialog` cover the rest.
- **Command palette:** Ctrl/⌘ K jumps to any page. It only navigates and
  switches the theme; it never calls the API.
- Grid items may shrink below their content width (a base rule in the
  stylesheet), so a long unbroken title truncates inside its card instead of
  widening the page on a phone.
- **Sizes are in rem, and desktop renders at 80%.** From 64rem (1024px) up,
  the root font size is 80%, which gives the density of an 80% browser zoom;
  phones and tablets keep the browser default. Everything scales together only
  because sizes are in rem, so write `text-[0.8125rem]` or a spacing-scale
  class such as `w-110` rather than px (shadows, blurs and hairlines excepted).
  Chart text takes rem strings too. Do not add custom font sizes such as
  `text-13` to the theme: tailwind-merge v2 reads an unknown `text-*` class as
  a colour and drops it when `cn()` merges it with a real colour class.

## Testing

Vitest covers the package-derivation rules, the formatting helpers, the
checklist, every page, and an App mount smoke test that also exercises the
command palette. The audit and experiment fixtures in `src/test/fixtures/` were
produced by running the real `build_published_audit` and `compare_experiment`
offline, so the pages are tested against the backend's actual output.

`npm run e2e` runs Playwright against the Docker backend at `127.0.0.1:8000`, so
start the stack first with `docker compose up -d`. It checks every migrated page
for console errors and horizontal overflow at desktop, tablet and phone widths.
A connected channel is mocked, and every call that could spend quota or change
saved data is intercepted. The Python Playwright suite in `../tests/browser/`
still targets the legacy dashboard; it needs porting when `/app` is switched
over.

## Charts

Most dashboard data is not a chart. Single headline numbers are `StatCard`
tiles, and a category with one member renders as a sentence rather than a
one-bar bar chart — claiming a comparison the data cannot support is the same
failure as inventing a number.

Where a chart is right, it is single-series, so colour carries no identity and
no legend is needed. The data hue is `--chart-1`, the brand violet, at 5.4:1
(light) and 6.6:1 (dark) against the card surface. Red is reserved for failures
and destructive actions; the only place it marks data is a decline in a
period-over-period comparison, which also carries a minus sign and a down
arrow. The title-quality chart ships a "View as table" disclosure, and the
Channel uploads chart sits beside the full uploads table, so no value depends
on colour alone.

## Status

Migrated: the application shell and design system, the **Creator** (a setup
screen that asks first whether it is a Short or a long video, then a results
screen with Package, Compare options, Research and insights, and Before you
publish tabs; `?tab=` keeps the tab, and old `?stage=` links open the tab that
now holds that stage), the **Dashboard**, **History** (list, search, tri-state bulk
selection, delete with confirmation, video linking, and a package detail panel
that opens from a shareable `?run=` link), **Channel** (28-day analytics against
the previous period, an uploads chart and table, learning, and linked packages),
**Settings** (channel connection, cloud sync, providers with an on-demand
live check, database, snapshot collector, appearance, and about), and the
research lab:

- **Ideas**: the backlog with status filters and paging, a new-idea form, each
  idea's lifecycle, angles and production plan, its dated research and demand
  check, and research, demand, generate and status actions.
- **Demand**: topic research saved as dated snapshots, the classification with
  its reasons, each observed signal with its provenance, the sampled public
  videos the legacy page stored but never showed, and package generation that
  links to the saved History run.
- **Audits**: every package linked to a published video, with a field-by-field
  check of what went live against what was generated, performance by
  completed window, findings, the saved pre-publish checks and audit history.
- **Experiments**: planned and observational comparisons, assigning verified
  videos to each side, every status change the backend allows, and the saved
  comparison with its metrics and limits.
- **Watchlist**: public channels and videos with their dated snapshots, the
  local outlier check, a channel's watched uploads, and archiving.

### Known gaps and deliberate deviations

- **OAuth returns to the page that started it.** Settings and Channel link to
  `/youtube/channel/connect?return_to=/next/settings` (or `/next/channel`). The
  backend keeps that choice in a short-lived HttpOnly cookie, checked against an
  allow-list, and the callback redirects there with `?youtube=connected|error`.
  The page announces the result once and removes the parameters. The legacy
  flow passes no `return_to` and still lands on `/`. Unlike the legacy app, the
  React page does not POST a second refresh after connecting, because the
  server already syncs during the connection; instead the Channel page
  refreshes a sync older than two minutes once per app session, guarded per
  QueryClient so navigating can never re-POST.
- **`on_screen_text` and `audience_type`** are accepted by the API but were
  never wired into the legacy Creator form, so they are left out here too.
- **Fallback vocabulary is standardised.** The legacy mixed "Not available",
  "--" and "Unknown" for absent values; this app says "Unavailable"
  everywhere. Deliberate, and a visible difference from the legacy dashboard.
- **`GET /api/history/runs` now returns `content_angle` and `intent`**, which
  the legacy row renderer and search always read but never received. Rows show
  the angle, search matches it, and records saved without one say "General".
- **Timestamps are pinned to IST** (`historyDate`), matching the backend's
  `WIN_ENGINE_CREATOR_TIMEZONE` default. Use it for every stored timestamp;
  there is deliberately no viewer-locale date helper.
- **Demand's language and region are choices, not free text.** The lists hold
  every value the research engine acts on, including Tamil Nadu, Sri Lanka and
  the Gulf; anything else the legacy fields accepted was saved and then
  ignored. Snapshots researched from an idea keep the Ideas form's spellings
  (`in`, `global`, `unknown`), which display as the options they mean.
- **Watch time says what it measures.** The Dashboard card shows the 28-day
  channel total when a YouTube Analytics sync provides one, and otherwise the
  total across linked videos at their latest snapshots, labelled "Linked
  videos". The backend used to add up every snapshot of each video (24-hour,
  7-day, 28-day and current), counting the same watch time once per snapshot.
- **Ideas use the regions research acts on.** The legacy form offered Global,
  `in` and US; this one saves `india` (which the research planner recognises;
  `in` it did not) and adds Tamil Nadu, Sri Lanka, the Gulf, the UK and Hindi.
  Older `in` records display as India. Restoring an archived idea returns it to
  "package generated" when it has a package, instead of back to "idea".
- **Audits read the backend's field states.** The legacy page tested for
  `"match"`, which the audit never returns (it says `exact_match`), so it
  reported differences on every audit. The audit list also loads about ten
  times faster: it checked each video's package selection on a new database
  connection, and now reads them in one query.
- **Experiments offer every allowed status change**, not only the next one:
  pause, resume, inconclusive and cancel too. Completing, marking inconclusive
  and cancelling ask first, because the backend never reopens them.
- **The watchlist takes channel IDs, not handles.** The backend looks channels
  up by ID only, so an `@handle` is refused in the form rather than after
  spending a quota call, and a `youtube.com/channel/UC…` link is accepted.
  Video search waits for a pause in typing instead of querying on every key.
  Channels show initials: their avatars are served from a host the Content
  Security Policy doesn't allow.
