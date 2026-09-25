# Win-Engine frontend

React + TypeScript + Vite rebuild of the Win-Engine dashboard. It runs beside the
existing interface rather than replacing it: the backend, the API, the SQLite
database, and the legacy dashboard are all unchanged.

| Route | Serves |
|---|---|
| `/next` | This React app |
| `/`, `/app`, `/dashboard_view` | The existing extracted dashboard (unchanged) |
| `/dashboard_legacy` | The original embedded dashboard (unchanged) |

`/app` is handed over to React only once every page reaches feature parity.

## Stack

React 18, TypeScript (strict), Vite 6, Tailwind CSS 4, Radix UI with vendored
shadcn/ui components, TanStack Query, React Router 7, React Hook Form + Zod,
Lucide, Sonner, and Vitest with React Testing Library.

React 18 rather than 19 is deliberate: every library above is stable on 18,
and the app gains nothing from 19's new features today.

## Commands

```bash
npm install
npm run dev        # http://localhost:5173, proxies the API to 127.0.0.1:8000
npm run build      # builds into ../win_engine/api/static/app/
npm run test       # Vitest
npm run typecheck  # tsc --noEmit
npm run gen:api    # regenerate src/api/schema.d.ts from the running backend
```

The dev server proxies `/analyze`, `/api`, `/health`, `/meta`, `/diagnostics`,
`/ready`, `/youtube`, and `/oauth` to the Docker backend, so the app is
same-origin in both development and production and the API client never needs a
base URL.

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
checklist, the Settings, Channel and Demand pages, History, and an App mount
smoke test that also exercises the command palette.

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

Migrated: the application shell and design system, the eight-stage **Creator**
workflow, the **Dashboard**, **History** (list, search, tri-state bulk
selection, delete with confirmation, video linking, and a package detail panel
that opens from a shareable `?run=` link), **Channel** (28-day analytics against
the previous period, an uploads chart and table, learning, and linked packages),
**Settings** (channel connection, cloud sync, providers with an on-demand
live check, database, snapshot collector, appearance, and about) and **Demand**
(topic research saved as dated snapshots, the classification with its reasons,
each observed signal with its provenance, the sampled public videos the legacy
page stored but never showed, and package generation that links to the saved
History run).

Not yet migrated: Ideas, Audits, Experiments, and Watchlist. Each has a route
and an honest placeholder linking to the working legacy page.

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
