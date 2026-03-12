# CLAUDE.md — E2CAF Assessment Platform

> Project briefing for Claude Code. Read this at the start of every session.
> Maintained by: Vernon Rauch | Last updated: 2026-03-13

---

## What This Project Is

The **E2CAF Assessment Platform** (internally "Assessment MVP") is a Streamlit web application backed by a local SQLite database. It enables HPE consultants to conduct structured capability maturity assessments for enterprise clients, aligned to the **Edge-to-Cloud Adoption Framework (E2CAF)** — HPE's proprietary transformation framework.

The platform supports:
- Predefined and custom use-case-driven assessments
- AI-generated capability discovery, question generation, and findings narrative
- AI-generated transformation roadmap with Gantt visualisation and Excel export
- Per-capability and per-domain gap analysis with maturity heatmap
- Full E2CAF framework management (capabilities, maturity levels, interdependencies, versioning)

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (multi-page app) |
| Database | SQLite — local file, path set via `TMM_DB_PATH` in `.env` |
| AI | Anthropic API (`claude-sonnet-4-20250514`) via `src/ai_client.py` |
| DB client | Custom `TMMClient` in `src/tmm_client.py` — no ORM |
| Environment | `.env` file with `TMM_DB_PATH` and `ANTHROPIC_API_KEY` |
| Python | 3.11+ |

---

## Repository Structure

```
/
├── CLAUDE.md                        ← this file
├── app.py                           ← Streamlit entry point (sidebar nav: Dashboard / Create Assessment / Architecture)
├── .env                             ← TMM_DB_PATH, ANTHROPIC_API_KEY (never commit)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── fly.toml                         ← Fly.io deployment config
├── start.bat / start.ps1            ← Windows startup scripts
├── data/
│   └── e2caf.db                     ← SQLite database
├── assets/
│   └── architecture.png
├── scripts/
│   ├── seed_test_assessments.py     ← Original seed script (legacy, uses AI — do not use)
│   └── seed_v3_assessments.py       ← Current seed script — 6 comprehensive assessments, no AI needed
└── src/
    ├── tmm_client.py                ← SQLite client: TMMClient (query, write, write_many)
    ├── sql_templates.py             ← SQL query/write helper functions
    ├── ai_client.py                 ← All Anthropic API calls
    ├── assessment_builder.py        ← CapabilityResult dataclass + analyze_use_case_readonly()
    ├── assessment_store.py          ← Persistence: save_assessment, save_findings, save_narrative,
    │                                   save_recommendations, load_recommendations,
    │                                   list_assessments, load_assessment
    ├── question_generator.py        ← generate_questions_for_capability()
    ├── heatmap.py                   ← Maturity heatmap HTML + Excel export
    ├── roadmap.py                   ← Roadmap Gantt HTML + Excel export
    ├── recommendation_engine.py     ← build_recommendations(): DB context assembly + AI orchestration
    └── pages/
        ├── dashboard.py             ← Framework overview dashboard (Bootstrap 5 dark)
        ├── create_assessment.py     ← 6-step assessment wizard (primary workflow)
        ├── simulation.py            ← Scenario impact simulation (partial)
        ├── usecase_workspace.py     ← Use case management
        └── architecture.py          ← Architecture page stub
```

---

## Database

**File:** `data/e2caf.db` — path set in `.env` as `TMM_DB_PATH`
**Engine:** SQLite

### Schema Naming Convention
- `Next_*` tables — the current E2CAF framework model (active)
- `Assessment*` tables — client assessment data
- Legacy tables (`Domain`, `SubDomain`, `Capability`, etc.) — old schema, do not use

### Key Framework Tables

| Table | Purpose |
|---|---|
| `Next_Domain` | 12 domains |
| `Next_SubDomain` | 59 subdomains |
| `Next_Capability` | 308 capabilities (IDs 1–319, sparse) |
| `Next_CapabilityLevel` | L1–L5 maturity descriptors per capability. **Always filter `WHERE level_name IS NOT NULL`** — has duplicate rows |
| `Next_MaturityAssessment` | Baseline maturity scores (4 dimensions per capability) |
| `Next_MaturityDimension` | 1=Process, 2=People, 3=Technology, 4=Governance |
| `Next_CapabilityInterdependency` | 482 dependency edges. Types: Foundational/Complementary/Amplifying/Substitutive |
| `Next_CapabilityInteractionType` | 1=Foundational, 2=Complementary, 3=Amplifying, 4=Substitutive |
| `Next_UseCase` | 26 predefined use cases |
| `Next_UseCaseCapabilityImpact` | impact_weight 1–5 (CHECK constraint), maturity_target, feasibility_score |
| `Next_TargetMaturity` | Per-dimension target scores per use case + capability |
| `Next_RoadmapStep` | Framework phase guidance per use case + capability (phase 1–4) |
| `Next_CapabilityInvestmentCost` | Estimated implementation cost per capability |
| `Next_FrameworkVersion` | Version registry (v1.0–v1.3 published) |
| `Next_ChangeRecord` | Audit trail of all framework changes |
| `Next_CapabilityTag` / `Next_CapabilityTagMap` | Tags (cloud, data, security, etc.) |
| `Next_CapabilityCluster` / `Next_CapabilityClusterMap` | 12 clusters |

### Key Assessment Tables

| Table | Purpose |
|---|---|
| `Assessment` | Header: client_id, engagement_name, use_case_name, intent_text, usecase_id, assessment_mode, overall_score, status, created_at, completed_at, **findings_narrative** |
| `AssessmentCapability` | Capabilities selected for assessment with ai_score, rationale, capability_role, target_maturity |
| `AssessmentResponse` | Individual question responses (response_type, score, answer, notes) |
| `AssessmentFinding` | Per-capability and per-domain gap findings (finding_type='capability'\|'domain', avg_score, target_maturity, gap, risk_level, subdomain) |
| `AssessmentRecommendation` | AI-generated gap recommendations. Created via `CREATE TABLE IF NOT EXISTS` on first engine run. **See exact column list below.** |
| `Client` | Client master: client_name, industry, sector, country |

### AssessmentRecommendation — Exact Column List
**Critical:** the live DB schema differs from what you might expect. Always use these exact names:
```
id, assessment_id, capability_id, capability_name, domain, capability_role,
current_score, target_maturity, gap,
priority_tier, effort_estimate,
recommended_actions (JSON TEXT), enabling_dependencies (JSON TEXT), success_indicators (JSON TEXT),
hpe_relevance, narrative, created_at
```
**Not present:** `subdomain`, `recommendation_headline`, `target_score`, `current_state_narrative`, `generated_at`, `model_used`

### Important DB Notes
- `Next_CapabilityLevel` has duplicate rows — **always filter `WHERE level_name IS NOT NULL`**
- `Next_UseCaseCapabilityImpact.impact_weight` has `CHECK BETWEEN 1 AND 5`
- `Next_CapabilityTagMap` and `Next_CapabilityClusterMap` require explicit `id` on INSERT
- `Assessment.usecase_id`, `assessment_mode`, and `findings_narrative` were added via ALTER TABLE; `_ensure_narrative_column()` in `assessment_store.py` handles the migration inline
- `AssessmentRecommendation` is created inline (`CREATE TABLE IF NOT EXISTS`) by `recommendation_engine.py` on first run — no manual migration needed
- Roadmap is NOT persisted to the DB — held in session state only (`roadmap_data`)

---

## Framework State (v1.3 — current)

**319 capability IDs, 308 populated** across 12 domains and 59 subdomains.

| Domain | ID | Caps | Notes |
|---|---|---|---|
| Strategy & Governance | 1 | 29 | |
| Security | 2 | 56 | Includes AI Security (307), ZTNA (306), Supply Chain Security (305) |
| People | 3 | 24 | |
| Applications | 4 | 36 | Includes Technical Debt Management (308) |
| Data | 5 | 37 | |
| DevOps | 6 | 30 | |
| Innovation | 7 | 36 | Includes Digital Twin (310) |
| Operations | 8 | 37 | |
| AI & Cognitive Systems | 9 | 14 | Expanded in v1.3 — 5 subdomains |
| Intelligent Automation & Operations | 10 | 3 | |
| Sustainability & Responsible Technology | 11 | 3 | |
| Experience & Ecosystem Enablement | 12 | 3 | |

**Version history:**
- v1.0 (2026-01-23) — E2CAF Next Baseline, 303 capabilities
- v1.1 (2026-03-07) — FinOps & Cloud Economics (cap 304)
- v1.2 (2026-03-07) — 6 gap capabilities added (305–310)
- v1.3 (2026-03-07) — AI & Cognitive Systems expanded (311–319, new subdomain id=59)

---

## Application Architecture

### Multi-Page Streamlit App
All pages live in `src/pages/`. Routing is a sidebar radio in `app.py` (not Streamlit's native multi-page mechanism).

### UI Convention
- **Bootstrap 5.3 dark** (`data-bs-theme="dark"`) loaded via CDN
- **Fonts:** JetBrains Mono + Inter via Google Fonts CDN
- **Charts:** Chart.js 4.4.3 via CDN
- All rich HTML components rendered via `st.components.v1.html(html, height=N, scrolling=True)`
- Data injected into HTML via `json.dumps()` into `const DATA = {...}` inside the HTML blob
- **Never** put Streamlit widgets inside HTML components — only `st.button()` / `st.form()` outside

### AI Call Pattern (`src/ai_client.py`)
```python
# All AI functions follow this pattern:
client = get_ai_client()           # singleton Anthropic client
response = _call_with_retry(       # exponential backoff on 529 overload
    client,
    model=DEFAULT_MODEL,           # claude-sonnet-4-20250514 (set via ANTHROPIC_MODEL env)
    max_tokens=N,
    messages=[{"role": "user", "content": prompt}],
)
raw = response.content[0].text.strip()
# Strip markdown fences before JSON parsing
```

All AI functions that return structured data:
- Prompt explicitly instructs "Return ONLY a JSON array/object with no preamble, no markdown"
- Strip ` ```json ` fences before `json.loads()`

### DB Query Pattern (`src/tmm_client.py`)
```python
db = get_client()                          # reads TMM_DB_PATH from .env
result = db.query("SELECT ...", [params])  # returns {"rows": [...], "count": N}
rows = result.get("rows", [])
db.write("INSERT ...", [params])           # returns {"lastrowid": N, "rowcount": N}
db.write_many("INSERT ...", list_of_tuples)
```

---

## Assessment Wizard (`src/pages/create_assessment.py`)

The primary workflow. Steps tracked via `st.session_state.wizard_step`.

| Step | Key | Description |
|---|---|---|
| 1 | `1` | Client context + use case intent. Mode toggle: predefined UC or custom |
| 2 | `2` | AI capability discovery (custom mode only — skipped for predefined) |
| 2b | `"2b"` | Domain target-setting (maturity targets per domain, L1–L5) |
| 3 | `3` | Question style selection + AI question generation + review |
| 4 | `4` | Response capture (online or offline; maturity 1–5 / yes-no-evidence / free text) |
| 5 | `5` | Findings: domain/capability scores, maturity heatmap, AI executive narrative, gap table, export |
| 5b | `"5b"` | Gap recommendations: AI per-capability recommendations with P1/P2/P3 priority, actions, dependencies, success indicators. Optional — can be skipped or run later |
| 6 | `6` | Transformation roadmap — AI-generated Gantt with Excel export. Uses Step 5b recommendations when available to structure phases; falls back to scores-only when skipped |

### Session State Keys
```
wizard_step, use_case_name, intent_text, client_name, engagement_name,
client_industry, client_sector, client_country,
assessment_mode ('predefined'/'custom'), selected_usecase_id (int|None),
core_caps, upstream_caps, downstream_caps, domains_covered,
domain_targets, questions, responses, findings_narrative,
assessment_id, findings_saved, responses_ai_scored,
confirm_regen_narrative,          ← bool: True while confirm dialog is shown for narrative regen
confirm_regen_recs,               ← bool: True while confirm dialog is shown for rec regen
recommendations (list|None),
roadmap_data (dict|None), roadmap_timeline_unit, roadmap_horizon_months, roadmap_scope
```

### Predefined Use Case Flow
- Step 1 mode = 'predefined' → skips Step 2 entirely → goes directly to Step 2b
- `_load_predefined_usecases()` → queries `Next_UseCase`
- `_load_predefined_capabilities()` → queries `Next_UseCaseCapabilityImpact`, maps impact_weight to role
- Intent text pre-filled from framework description + business_value, editable by consultant

### Response Scoring (Step 5 pre-processing)
All response types are normalised to numeric 1–5 before Step 5 renders (flagged by `responses_ai_scored`):
- `maturity_1_5`: score already stored numerically — no action needed
- `yes_no_evidence`: mapped via fixed dict (Yes=3, Partial=2, No=1)
- `free_text`: batched to `score_free_text_responses()` in `ai_client.py` → Claude scores 1–5

---

## Key AI Functions (`src/ai_client.py`)

| Function | Purpose | Output |
|---|---|---|
| `rank_capabilities_by_intent()` | Ranks candidate capabilities by relevance to intent | JSON array with ai_score + rationale |
| `generate_findings_narrative(client_name, client_industry, client_country, client_stated_context, ...)` | Executive summary of assessment findings, grounded in client context | Plain text, 3–4 paragraphs |
| `score_free_text_responses()` | Scores free-text responses 1–5 using maturity rubric | Same list with score + rationale added |
| `generate_gap_recommendations(client_country, client_stated_context, ...)` | Per-capability gap recommendation grounded in level descriptors, actual responses, and dependency context | JSON dict with recommended_actions, enabling_dependencies, success_indicators, narrative |
| `generate_roadmap_plan(client_name, client_industry, client_country, client_stated_context, ...)` | Structured gap-closure roadmap (phases → initiatives). Accepts optional `recommendations` list to structure phases by P1/P2/P3 tier | JSON dict (see schema below) |

`generate_questions_for_capability()` lives in **`src/question_generator.py`**, not ai_client.py.

### AI Grounding Rules (all client-facing functions)
All three client-facing AI functions (`generate_findings_narrative`, `generate_gap_recommendations`, `generate_roadmap_plan`) include:
1. **CLIENT-STATED CONTEXT block** — verbatim answer/notes text extracted from assessment responses, injected into the prompt so the AI grounds recommendations in what the client actually said
2. **Technology grounding rule** — hard prohibition: do NOT name specific vendors, cloud providers, platforms, or products unless that exact name appears verbatim in the CLIENT-STATED CONTEXT
3. **Industry + country context** — client_industry and client_country passed to all three functions for market-appropriate framing

`_build_client_stated_context(responses: dict) -> str` is a module-level helper in `create_assessment.py` that deduplicates and formats response answer/notes for injection.

### Roadmap JSON Schema (from `generate_roadmap_plan()`)
```json
{
  "total_weeks": int,
  "phases": [
    {
      "id": "P1", "name": str, "start_week": int, "end_week": int,
      "rationale": str, "story": str, "description": str,
      "activities": [str],
      "initiatives": [
        {
          "id": str, "name": str, "domain": str, "capability_names": [str],
          "priority": "Critical|High|Medium|Low",
          "current_score": float, "target_score": float, "gap": float,
          "start_week": int, "end_week": int, "prerequisites": [],
          "outcome": str
        }
      ]
    }
  ],
  "critical_path": [str],
  "quick_wins": [str]
}
```

---

## Recommendation Engine (`src/recommendation_engine.py`)

### `build_recommendations(db, assessment_id, cap_scores, client_industry, intent_text, usecase_id, max_caps, on_progress, client_country)`
For each gap capability (gap > 0, sorted by gap desc, Core first, capped at `max_caps`):
1. Determines `priority_tier` (P1/P2/P3) and `effort_estimate` deterministically before the AI call
2. Loads from DB: `Next_CapabilityLevel` L(current) and L(target) descriptors (`capability_state` + `key_indicators`), `AssessmentResponse` for this capability, Foundational dependencies from `Next_CapabilityInterdependency` (interaction_type_id=1), `Next_RoadmapStep` framework phase if `usecase_id` provided
3. Calls `generate_gap_recommendations()` with full context
4. Failures on individual capabilities produce a placeholder and continue — run does not abort
5. Returns results sorted P1 → P2 → P3, then gap desc within tier

**Priority tier logic:**
- P1: `framework_phase == 1` OR `gap >= 2.0` OR (`role == 'Core'` AND `gap >= 1.5`)
- P2: `gap >= 1.0`
- P3: `gap < 1.0`

**Table creation:** `CREATE TABLE IF NOT EXISTS AssessmentRecommendation` runs on every call but is a no-op after first creation.

## Heatmap Module (`src/heatmap.py`)

| Function | Purpose |
|---|---|
| `render_heatmap_html(dom_scores)` | Bootstrap 5 HTML table — domain × maturity level (L1–L5) with colour coding |
| `generate_heatmap_excel(dom_scores, client_name, engagement_name, use_case_name)` | XLSX bytes with formatted heatmap + legend |

**Per-level score formula:** `level_score(L) = max(0, min(1, avg_score - (L - 1)))`
- Green (#B7E2CD) = 1.0 (level fully achieved)
- Amber (#FDE9B2) = 0–1 (partial)
- White = 0 (not achieved)

`DOMAIN_COLORS` dict in `heatmap.py` holds the 12 brand colours used across heatmap and Gantt.

---

## Roadmap Module (`src/roadmap.py`)

| Function | Purpose |
|---|---|
| `render_roadmap_gantt_html(roadmap, timeline_unit)` | Bootstrap 5 Gantt — phases, initiatives, quick wins, critical path |
| `generate_roadmap_excel(roadmap, client_name, engagement_name, use_case_name)` | 3-sheet XLSX: Initiatives / Phase Narratives / Critical Path |
| `TIMELINE_UNITS` | List of valid timeline unit strings |

Timeline units: `"Weeks"`, `"Sprints (2 wks)"`, `"Quarters (13 wks)"`
Priority badge colours: Critical=#DC2626, High=#EA580C, Medium=#D97706, Low=#16A34A

---

## Persistence (`src/assessment_store.py`)

| Function | Table(s) | Notes |
|---|---|---|
| `save_assessment()` | `Client`, `Assessment`, `AssessmentCapability`, `AssessmentResponse` | Creates records; returns assessment_id |
| `save_findings()` | `Assessment` (UPDATE), `AssessmentFinding` (INSERT) | Updates overall_score + status; calls `_ensure_narrative_column()` inline |
| `save_narrative(client, assessment_id, narrative)` | `Assessment` (UPDATE) | Persists executive summary to `findings_narrative` column; calls `_ensure_narrative_column()` |
| `save_recommendations()` | `AssessmentRecommendation` | Idempotent — DELETE then INSERT; JSON-encodes list fields; uses actual DB column names |
| `load_recommendations()` | `AssessmentRecommendation` | JSON-decodes list fields; ensures `narrative` key is always set; returns [] if none exist |
| `list_assessments()` | `Assessment`, `Client` | Returns all assessments newest-first |
| `load_assessment()` | `Assessment`, `AssessmentCapability`, `AssessmentResponse` | Returns dict with assessment/capabilities/responses |

**Column mapping for `save_recommendations()` (in-memory → DB):**
- `r["narrative"]` → `narrative` column
- `r["target_maturity"]` → `target_maturity` column
- Timestamp → `created_at` column
- `hpe_relevance` written as NULL (field removed from AI output)

**Note:** Roadmap is generated in-session and is NOT persisted to the database.

---

## Current State

### Assessment Wizard — All Steps Complete ✅

| Step | Status |
|---|---|
| 1 — Client context + use case intent | ✅ Complete |
| 2 — AI capability discovery (custom) | ✅ Complete |
| 2b — Domain target-setting | ✅ Complete |
| 3 — Question generation + review | ✅ Complete |
| 4 — Response capture | ✅ Complete |
| 5 — Findings + heatmap + AI narrative | ✅ Complete |
| 5b — Gap recommendations (per-capability, AI-grounded) | ✅ Complete |
| 6 — Transformation roadmap (Gantt + Excel) | ✅ Complete |

**Step 5 — Findings & Narrative:**
- Executive summary narrative is generated by `generate_findings_narrative()` and persisted to `Assessment.findings_narrative` via `save_narrative()`
- On reload, `_hydrate_session_from_db()` restores `findings_narrative` from DB into session state
- Regenerate button shows confirm-before-overwrite dialog (`confirm_regen_narrative` flag in session state); user must click "Yes, regenerate" to proceed
- `client_name`, `client_industry`, `client_country`, and `_build_client_stated_context()` are all passed to `generate_findings_narrative()`

**Step 5b implementation:**
- Optional step — accessible via "Generate Recommendations →" from Step 5; can also be skipped
- **Priority scope selector**: radio — "All priorities" / "P1 only" / "P1 + P2" — pre-filters caps before AI calls using `_preview_tier()` helper (mirrors engine logic)
- **Cap count slider**: 1 to `eligible_count`, default `min(eligible_count, 20)`; Generate disabled when 0
- `build_recommendations()` in `recommendation_engine.py` orchestrates per-capability AI calls
- Priority tier (P1/P2/P3) determined deterministically before AI call; effort_estimate derived from gap size
- Each capability's AI call receives: L(current) and L(target) descriptors, actual scored responses + notes, Foundational dependency chain, framework phase from `Next_RoadmapStep`, client_country
- Progress callback shows which capability is being analysed
- Results cached in `st.session_state.recommendations`; persisted to `AssessmentRecommendation` via `save_recommendations()`
- On reload, loaded from DB via `load_recommendations()` if session is empty
- UI: expandable cards (P1 expanded by default), priority filter, CSV + JSON export
- Regenerate button shows confirm-before-overwrite dialog (`confirm_regen_recs` flag); user must confirm

**Step 6 implementation:**
- Detects whether `st.session_state.recommendations` is populated
- If recommendations present: passes them to `generate_roadmap_plan(recommendations=...)` → AI uses P1/P2/P3 tiers to assign phases and uses recommended actions for initiative content
- If no recommendations (skipped): falls back to scores-only roadmap (original behaviour)
- User selects timeline unit, horizon (months), scope (Core / Core+Upstream / All)
- `client_name`, `client_industry`, `client_country`, and `_build_client_stated_context()` are all passed to `generate_roadmap_plan()`
- Export via `generate_roadmap_excel()` → 3-sheet XLSX download

### Test Assessments in DB (`scripts/seed_v3_assessments.py`)

Run with: `docker compose exec app python scripts/seed_v3_assessments.py`
Idempotent — skips any assessment whose client_name + use_case_name already exists.
Pass `--clean` to first remove the six seeded clients by name before re-inserting (useful when re-seeding from scratch).

| ID | Client | Country | Use Case | Q-Type | Domains | Caps | Responses |
|---|---|---|---|---|---|---|---|
| 21 | Deutsche Bank AG | Germany | General IT Readiness (UC 31) | `maturity_1_5` | 9 | 53 | 159 |
| 22 | Ramsay Health Care | Australia | General IT Readiness (UC 31) | `yes_no_evidence` | 9 | 53 | 159 |
| 23 | Siemens AG | Germany | Operating Model Modernization (UC 27) | `maturity_1_5` | 7 | 55 | 165 |
| 24 | Qatar National Bank | Qatar | AI Readiness (UC 30) | **mixed** (all 3 types) | 8 | 38 | 114 |
| 25 | Norsk Hydro ASA | Norway | General IT Readiness (UC 31) | `free_text` | 9 | 53 | 159 |
| 26 | Singapore Airlines | Singapore | Datacenter Transformation (UC 32) | `maturity_1_5` | 6 | 30 | 90 |

Each assessment has: 3 questions per capability, 8 gap recommendations, executive summary narrative, domain findings + capability findings rows.

**Use case domain coverage:**
- UC 31 (General IT Readiness): 9 domains × 6 caps — Strategy & Governance, Security, People, Applications, Data, DevOps, Innovation, Operations, AI & Cognitive Systems
- UC 27 (Operating Model): 7 domains, all caps (Strategy & Governance=16, People=17, Applications=11, Security=5, DevOps=3, Operations=2, AI=1)
- UC 30 (AI Readiness): 8 domains, all caps (AI & Cognitive Systems=10, Data=12, People=7, Security=5, + 4 others)
- UC 32 (Datacenter Transformation): 6 domains, all caps (Security=18, Applications=4, Data=3, People=3, + 2 others)

### Pending Work
- `src/pages/simulation.py` — impact heatmap (domain × capability grid). `Next_ScenarioImpactCapability` is empty; `Next_ScenarioCapabilityChange` has data
- `Next_ValueTheme` table is empty — value theme assignment for roadmap steps not yet implemented
- Dashboard awareness of completed assessments — summary widget not yet built
- Roadmap persistence to DB (currently session-only)
- Word/PowerPoint export of full assessment report (findings + recommendations + roadmap)

---

## Coding Conventions

### Never Do
- Do not use an ORM — all SQL is written directly in `sql_templates.py` or inline in page/engine files
- Do not put Streamlit widgets inside `st.components.v1.html()` components
- Do not use `localStorage` or `sessionStorage` in any HTML component
- Do not modify the legacy schema tables (`Domain`, `SubDomain`, `Capability`, `CapabilityLevel`, `UseCaseCapabilities`)
- Do not use `st.experimental_*` APIs — use current Streamlit stable API

### Always Do
- Filter `Next_CapabilityLevel` with `WHERE level_name IS NOT NULL`
- Use `json.dumps()` / `json.loads()` for all structured data stored in TEXT columns
- Use `_call_with_retry()` for all Anthropic API calls
- Strip markdown fences before parsing JSON from AI responses
- Keep AI prompts in `ai_client.py` — not in page files
- Keep DB query helpers in `sql_templates.py` — not in page files
- Use `st.session_state.setdefault()` before reading session state keys

### SQL Conventions
- Always use `Next_` prefix tables for framework data
- Parameterised queries only — never f-string SQL with user input
- Multi-row inserts via `write_many()` with `executemany`
- Always check for `CHECK` constraints — `impact_weight BETWEEN 1 AND 5`

---

## Environment Setup

**The app runs exclusively in Docker. There is no local `.venv`.** All dependencies are installed inside the container image defined by `Dockerfile`.

```bash
# .env (never commit) — lives at project root, mounted into container
TMM_DB_PATH=/data/e2caf.db          # container-internal path
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514   # optional override

# Run the app (only supported method)
docker compose up --build            # ALWAYS use --build — code changes are not picked up otherwise
docker compose up --build -d         # detached mode

# Stop
docker compose down
```

**Important:** `docker compose restart` does NOT pick up code changes — it reuses the cached image. Always use `docker compose up --build`.

The `.claude/launch.json` "Docker Compose" config is the correct launch configuration. The "Streamlit (local)" config will fail — there is no local Python environment with dependencies installed.

---

## Active Client Engagements (for context)

| Client | Engagement | Notes |
|---|---|---|
| Viennalife | Private cloud modernisation | 4 RFP streams (WP1–WP4); WP5 removed in v0.2 |
| UBS | VMware Modernisation (VME) | VMware exit planning |
| Massey University (UoO) | Edge-to-Cloud adoption | HERM–E2CAF crosswalk produced; assessment id=2 in DB |
| Salam Monetization Services | Monetisation platform | |
| Dubai Police | SRI regulation posture assessment | |

---

## Key People

| Name | Role | Relevance |
|---|---|---|
| Vernon Rauch | Senior Hybrid Cloud Business Consultant & Chief Technologist, HPE CPS/A&PS | Project owner |

---

## Session Handoff Protocol

At the end of a productive session, create or update `docs/session_notes.md` with:
1. What was completed this session (files changed, DB changes made)
2. What is in progress / partially done
3. Exact next action to take at the start of the next session
4. Any decisions made that should be reflected back into this CLAUDE.md

---

*This file is the source of truth for Claude Code context. Keep it current.*
