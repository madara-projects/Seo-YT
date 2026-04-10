# YouTube Win-Engine OS Roadmap

This roadmap now reflects the **actual verified project state** in this repository.

## Current Status

- Current phase: **Phase 7**
- Phase 1: **Done**
- Phase 2: **Done**
- Phase 3: **Done**
- Phase 4: **Done**
- Phase 5: **Done**
- Phase 6: **Done**
- Docker: **Optional**
- Redis cache: **Optional and now supported**

## What We Just Completed

- [x] Audited Phase 1 against the roadmap text
- [x] Confirmed FastAPI app factory and modular backend
- [x] Confirmed Pydantic validation schemas
- [x] Confirmed logging, middleware, and health/readiness endpoints
- [x] Confirmed SQLite storage
- [x] Added optional Redis-backed cache support with safe fallback to in-memory cache
- [x] Added local Redis service support in Docker Compose
- [x] Started Phase 2 by adding language, region, and audience context into the generation flow
- [x] Added Tamil/Tanglish-aware packaging behavior
- [x] Added regional and audience-aware competition weighting
- [x] Added language-specific emotional trigger mapping
- [x] **Phase 2 Completion:** Improved Tamil/Tanglish title validation with real-world phrasing patterns
- [x] **Phase 2 Completion:** Added region-aware keyword prioritization based on target market
- [x] **Phase 2 Completion:** Added stronger local-vs-global YouTube result weighting based on language and region
- [x] **Phase 3 Completion:** Audited YouTube research, keyword extraction, entity extraction, outlier scoring, and cache policy
- [x] **Phase 3 Completion:** Fixed Streamlit research flow so region/language settings reach the data intelligence layer
- [x] **Phase 3 Completion:** Fixed SQLite in-memory history behavior for audit and smoke-test reliability
- [x] **Phase 4 Completion:** Audited intent classification, hook audit, alignment scoring, and retention-risk heuristics
- [x] **Phase 4 Completion:** Improved intent classification coverage for search, browse, and suggested patterns
- [x] **Phase 4 Completion:** Improved stake detection for experiment-style script openings
- [x] **Phase 5 Completion:** Audited title, description, tags, hashtags, and CTR/A-B generation outputs
- [x] **Phase 5 Completion:** Added proper backend tag generation instead of relying only on UI-derived tags
- [x] **Phase 5 Completion:** Verified title variants, description generation, hashtags, tags, and CTR prediction output
- [x] **Phase 6 Completion:** Audited competitor pattern extraction, differentiation output, and competition analysis
- [x] **Phase 6 Completion:** Added competitor shadow analysis to the generated result payload
- [x] **Phase 6 Completion:** Verified competitor-shadow guidance through the generation path

---

## Phase 1: Core Infrastructure

### Backend Setup
- [x] Setup FastAPI async application
- [x] Create modular folder structure aligned to the real codebase:
  - [x] `win_engine/api`
  - [x] `win_engine/core`
  - [x] `win_engine/ingestion`
  - [x] `win_engine/analysis`
  - [x] `win_engine/scoring`
  - [x] `win_engine/generation`
  - [x] `win_engine/feedback`

### Core Systems
- [x] Add Pydantic validation schemas
- [x] Setup logging
- [x] Setup middleware and structured error handling
- [x] Setup health/readiness/meta endpoints
- [x] Setup SQLite database
- [x] Add optional Redis caching layer

### Phase 1 Verdict
- [x] Phase 1 is now complete against the current roadmap scope

---

## Phase 2: Language Intelligence Engine

### Input Layer
- [x] Add language selector baseline
- [x] Add region selector baseline
- [x] Add audience type selector baseline
- [x] Pass language/region/audience context into generation flow

### Language Strategy
- [x] Detect primary script language with conservative heuristics
- [x] Support explicit language override from UI
- [x] Return localization guidance in analysis output

### Still To Do In Phase 2
- [x] Improve Tamil-specific packaging rules
- [x] Add Tanglish detection
- [x] Add stronger regional biasing for India / Tamil Nadu / Sri Lanka / Gulf
- [x] Add global vs local competition weighting
- [x] Add language-specific emotional trigger mapping
- [x] Improve Tamil/Tanglish title quality further with real-world phrasing validation
- [x] Add region-aware keyword prioritization
- [x] Add stronger local-vs-global YouTube result weighting

### Phase 2 Verdict
- [x] Phase 2 is complete

---

## Phase 3: Data Intelligence Engine

- [x] Full audit completed
- [x] Phase 3 is verified and complete against the current roadmap scope

Current prototype work already present in code:
- [x] YouTube result gathering
- [x] Keyword extraction baseline
- [x] Entity extraction baseline
- [x] Outlier scoring baseline
- [x] Basic cache policy split for trending vs evergreen

### Phase 3 Verification
- [x] Added a current audit script
- [x] Verified keyword extraction
- [x] Verified entity extraction
- [x] Verified regional outlier scoring
- [x] Verified cache policy logic
- [x] Verified generation path with Phase 3 research payloads

---

## Phase 4: Script -> Intelligence Engine

- [x] Full audit completed
- [x] Phase 4 is verified and complete against the current roadmap scope

Current prototype work already present in code:
- [x] Script input flow
- [x] Intent classification
- [x] Hook/content audit baseline
- [x] Expectation/package auditing baseline

### Phase 4 Verification
- [x] Added a current audit script
- [x] Verified search / browse / suggested intent classification
- [x] Verified hook-topic detection
- [x] Verified stake detection
- [x] Verified title-script alignment scoring
- [x] Verified generation path returns content audit and retention-risk signals

---

## Phase 5: Generation Engine

- [x] Full audit completed
- [x] Phase 5 is verified and complete against the current roadmap scope

Current prototype work already present in code:
- [x] Title generation
- [x] Description generation
- [x] Tag generation
- [x] Hashtag generation
- [x] Title variants
- [x] Basic performance/CTR heuristics

### Phase 5 Verification
- [x] Added a current audit script
- [x] Verified title generation
- [x] Verified description generation
- [x] Verified tag generation
- [x] Verified hashtag generation
- [x] Verified title variants and A/B test output
- [x] Verified CTR prediction output

---

## Phase 6: Competitor Shadow Engine

- [x] Full audit completed
- [x] Phase 6 is verified and complete against the current roadmap scope

Current prototype work already present in code:
- [x] Competitor video lookup
- [x] Basic pattern extraction from titles
- [x] Differentiation signals

### Phase 6 Verification
- [x] Added a current audit script
- [x] Verified competition analysis output
- [x] Verified differentiation recommendation output
- [x] Verified competitor-shadow dominant pattern detection
- [x] Verified competitor-shadow data reaches the generated response

---

## Phase 7: Opportunity & Kill System

- [-] In progress

Current prototype work already present in code:
- [x] Opportunity gap analysis baseline
- [x] Competition labeling baseline
- [x] Proceed / kill-style recommendation baseline
- [x] Viability verdict baseline
- [x] Format lock recommendation baseline

---

## Phase 8: Pattern Memory System

- [ ] Full audit pending

Current prototype work already present in code:
- [x] SQLite-backed analysis history
- [x] Snapshot history for videos
- [x] Local learning summary baseline

---

## Phase 9: Feedback & Learning Loop

- [ ] Full audit pending

Current prototype work already present in code:
- [x] Internal scorecard baseline
- [x] Historical comparison baseline
- [x] Recent run tracking baseline

---

## Phase 10: Rapid Execution Engine

- [ ] Not started as an audited roadmap milestone

---

## Phase 11: UI & Control Panel

- [x] Streamlit UI exists
- [x] Script input flow exists
- [x] Package output UI exists
- [x] Copy-ready title / description / tags / hashtags flow exists
- [ ] Full audit pending

---

## Phase 12: Advanced Intelligence

- [ ] Future work

---

## Next Focus

1. **Audit Phase 7** - Opportunity & Kill System
2. Continue improving output quality:
    - title realism
    - description quality
    - tags that match real YouTube usage
3. Validate Phase 7 systems against real opportunity-filter expectations
