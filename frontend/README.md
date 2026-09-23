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

## Testing

Vitest covers the package-derivation rules, the checklist, and an App mount
smoke test. The Python Playwright suite in `../tests/browser/` still targets the
legacy dashboard; it needs porting when `/app` is switched over.

## Charts

Most dashboard data is not a chart. Single headline numbers are `StatCard`
tiles, and a category with one member renders as a sentence rather than a
one-bar bar chart — claiming a comparison the data cannot support is the same
failure as inventing a number.

Where a chart is right, it is single-series, so colour carries no identity and
no legend is needed. The data hue is `--chart-1` (blue), deliberately not the
brand red: red is reserved for destructive and critical status and must never
double as a series colour. Both mode steps were validated for lightness band,
chroma floor and >=3:1 contrast against the card surface. Every chart also
ships a "View as table" disclosure so identity is never colour-alone.

## Status

Migrated: the application shell, the design system, the eight-stage Creator
workflow, the **Dashboard**, and **History** (list, search, tri-state bulk
selection, delete with confirmation, video linking, and the full package detail
with whole-bundle copy).

Not yet migrated: Ideas, Demand, Audits, Experiments, Watchlist, and Settings.
Each has a route and an honest placeholder linking to the working legacy page.

### Known gaps and deliberate deviations

- **OAuth return is not handled under `/next`.** The backend redirects the
  consent callback to `/?youtube=connected`, which the legacy app answers by
  POSTing `/youtube/channel/refresh`, stripping the query param, and refreshing.
  There is no React equivalent. It does not affect Dashboard or History today
  because the redirect lands on the legacy root, but it must be built before
  Settings is migrated, including a once-per-load guard — without one, a React
  effect would re-POST on every navigation and spend real quota.
- **`on_screen_text` and `audience_type`** are accepted by the API but were
  never wired into the legacy Creator form, so they are left out here too.
- **Fallback vocabulary is standardised.** The legacy mixed "Not available",
  "--" and "Unknown" for absent values; this app says "Unavailable"
  everywhere. Deliberate, and a visible difference from the legacy dashboard.
- **`GET /api/history/runs` does not return `content_angle` or `intent`**,
  though the legacy row renderer and its search filter both read them — so the
  angle always fell back to "General" and searching by angle never matched.
  The types declare them and the UI tolerates their absence.
- **Timestamps are pinned to IST** (`historyDate`), matching the backend's
  `WIN_ENGINE_CREATOR_TIMEZONE` default. Use it for every stored timestamp;
  there is deliberately no viewer-locale date helper.
