# ScoutIQ — AI soccer scouting assistant

ScoutIQ helps clubs with limited scouting resources find affordable players who fit a tactical brief.
Describe what you need in plain English. ScoutIQ turns it into a **validated structured query**, ranks
players with **deterministic Python** (transparent, role-specific weighted percentiles), and shows the
evidence behind every recommendation: filters, weights, each metric's contribution, strengths,
trade-offs, missing data and provenance.

A Meta model (via the **Meta Model API**) interprets requests and follow-ups and writes short summaries
from the computed numbers. It never does the ranking maths. Without an API key, ScoutIQ runs in a clearly
labelled **demo mode** that uses a deterministic parser and template summaries. The whole workflow still works.

> **Data:** real players and real event data from the **Premier League 2015/16** season (StatsBomb Open
> Data, all 380 matches), joined to **Transfermarkt market-value estimates** and dates of birth from the
> CC0 `transfermarkt-datasets` project. This is a historical season. ScoutIQ shows what the approach does;
> it is not a live transfer tool.

---

## Quick start

Requirements: Python 3.11+ (3.12 tested), Node 20+ (23 tested), `npm`. `uv` is optional.

```bash
# 1. Backend
cd scoutiq/backend
python3 -m venv .venv                     # or: uv venv --python 3.12 .venv
.venv/bin/pip install -r requirements.txt # or: uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest -q             # 70 tests
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# 2. Frontend (new terminal)
cd scoutiq/frontend
npm install
npm run dev          # http://localhost:3000  (proxies /api/* to :8000)
```

```bash
# 3. Optional: end-to-end smoke test against the running servers
cd scoutiq/backend
.venv/bin/python scripts/smoke_test.py --base http://localhost:3000
```

The SQLite database (`backend/data/scoutiq.db`, ~150 KB) is committed, so steps 1–2 need no network
apart from package installs. To enable the Meta model, copy `.env.example` to `.env` and set `META_API_KEY`
(see below). Then restart the backend.

### Rebuilding the data (reproducible ingestion)

```bash
cd scoutiq/backend
.venv/bin/python scripts/ingest.py                 # full build: downloads ~110 MB (cached gzip in data/raw/)
.venv/bin/python scripts/ingest.py --no-valuations # stats only: ages and budgets are disabled
```

The script downloads the StatsBomb match, event and lineup JSON for competition 2 / season 27 and the
`players` and `player_valuations` tables from transfermarkt-datasets. It aggregates per-player counts from
raw events, joins the two sources, and writes the `players` and `metadata` tables. Re-runs use the
local cache.

---

## Environment variables

All of these are read by the **backend only**. The browser talks only to the Next.js server, which proxies
`/api/*`, so no key ever reaches the client.

| Variable | Default | Purpose |
|---|---|---|
| `META_API_BASE_URL` | `https://api.meta.ai/v1` | Meta Model API base URL (OpenAI-compatible). |
| `META_API_KEY` | *(empty)* | Bearer key. **Empty means demo mode.** |
| `META_MODEL` | `muse-spark-1.3` | Model ID. Meta's docs list this as recommended for new work. |
| `META_REASONING_EFFORT` | `low` | Sent as `reasoning_effort`. Leave empty to omit it. |
| `META_TIMEOUT_SECONDS` | `25` | Per-request timeout before falling back to demo behaviour. |
| `SCOUTIQ_DEMO_MODE` | *(empty)* | `1` forces demo mode even when a key is set (offline demos). |
| `SCOUTIQ_RATE_LIMIT_PER_MINUTE` | `30` | POST requests per client IP per minute. |
| `SCOUTIQ_DB_PATH` | `backend/data/scoutiq.db` | SQLite path. |
| `SCOUTIQ_BACKEND_URL` | `http://127.0.0.1:8000` | *(frontend server)* Where `/api/*` is proxied. |

`.env` is loaded from the repo root or `backend/`. Real environment variables take precedence.

### Meta model integration (verified against official docs, Oct 2026)

From the official Meta Model API docs ([chat completions](https://dev.meta.ai/docs/protocols/chat-completions),
[structured output](https://dev.meta.ai/docs/structured-output), [models](https://dev.meta.ai/docs/models)):

- `POST {META_API_BASE_URL}/chat/completions` with `Authorization: Bearer <key>`. The API is OpenAI-compatible.
- `response_format: {"type": "json_schema", "json_schema": {"name", "schema"}}` constrains the output.
  The JSON comes back as a string in `choices[0].message.content`.
- The `developer` role is preferred over `system`, `max_completion_tokens` is used, and `temperature` is left
  at its default, as the docs recommend for Muse Spark.

### Alternative: Meta open-weights models on Modal Endpoints

Modal Endpoints serve Meta's open-weights models (the Modal Library lists, for example, Muse Spark Open
and Muse Glimmer 30B) through an OpenAI-compatible Chat Completions API, so the same adapter works:

1. In the Modal dashboard, create an Endpoint for a Meta model at <https://modal.com/endpoints>.
2. Create a proxy token with `modal workspace proxy-tokens create`.
3. Set these in `.env`:
   ```
   META_API_BASE_URL=<your-endpoint-url>/v1
   META_API_KEY=wk-<token-id>.ws-<token-secret>   # ID and secret joined with a period
   META_MODEL=<model name from the endpoint's request example, or GET /v1/models>
   META_REASONING_EFFORT=                          # leave empty for open-weights servers
   ```

If a server rejects the `developer` role or the newer parameters (HTTP 400/422), the adapter retries once
with `system`, `max_tokens` and no `reasoning_effort`. Modal's docs don't say whether `json_schema` output is
enforced, but ScoutIQ validates every reply anyway: invalid output falls back to the demo parser with a
visible warning. Dedicated endpoints that scale to zero can cold-start slowly, so raise
`META_TIMEOUT_SECONDS` (to 60, for example) for the first request.

The adapter (`backend/app/llm.py`) uses plain `httpx`, with no SDK dependency. I verified the endpoint
returns `401 invalid_api_key` without credentials. **Generation with a real key was not tested** because
none was available during the build.

---

## Architecture

```
Browser ──► Next.js (App Router, TS, Tailwind)  ──/api/* proxy──►  FastAPI (Python)
                                                                       │
             ┌─────────────────────────────────────────────────────────┤
             │  parser.py   deterministic NL → StructuredQuery (demo / fallback)
             │  llm.py      Meta Model API adapter → JSON → StructuredQuery (validated)
             │  schemas.py  StructuredQuery: role, maximum_age, minimum_minutes,
             │              maximum_market_value_eur, metric_weights, result_limit (extra=forbid)
             │  scoring.py  filters → percentiles → weighted score → contributions,
             │              strengths/trade-offs, missing data, value heuristic (LRU-cached)
             │  explain.py  template summaries + evidence payload for the model
             │  data.py     SQLite → in-memory table, cached sorted arrays for percentiles
             └─ data/scoutiq.db  ◄── scripts/ingest.py (StatsBomb + transfermarkt-datasets)
```

**Request flow.** `POST /api/search {text}` → the deterministic parser always runs first (it also rejects
unsupported roles) → if a key is configured, the Meta model returns JSON → strict validation (unknown
fields or metrics, out-of-range values and malformed JSON are rejected) → on any failure, the demo parser's
result is used and a visible warning is shown → `scoring.rank()` → response. Summaries load separately
(`POST /api/summaries`), so the shortlist appears immediately. Model summaries that mention injuries,
personality, leadership, contracts, transfer availability and similar topics are discarded and replaced
with templates.

**Endpoints:** `GET /api/config`, `POST /api/search`, `POST /api/rank` (edited filters), `POST /api/refine`
(follow-ups), `POST /api/summaries`, `GET /api/health`, plus OpenAPI docs at `/api/docs`.

**Security and robustness.** Model output is only parsed as JSON and validated; it is never executed and
never becomes SQL (the DB is opened read-only and is never queried with model text). User text is limited
to 500 characters, wrapped in delimiters and labelled as data in the prompts. The API has per-IP rate
limiting, model timeouts, and generic error messages that never echo upstream bodies or keys. React
escapes all rendered text (no `dangerouslySetInnerHTML`), and security headers are set.

### Scoring method

1. **Filter:** role, `minutes ≥ minimum_minutes`, `age ≤ maximum_age` (age as of 2016-01-01) and
   `value ≤ budget`. Players with unknown age or value are excluded *only* when that filter is active, and
   the exclusion counts are shown.
2. **Percentiles:** mid-rank percentile of each metric among **same-role players with 900+ minutes** in the
   dataset. These are dataset-relative, and the UI labels them that way.
3. **Score** = Σ wᵢ·pctᵢ / Σ wᵢ over the metrics the player actually has. Weights are normalised to 1.
   If a metric is missing (for example, pass completion below 50 attempts), its weight is redistributed
   and **coverage** (the share of requested weight with data) is disclosed on the card and in the drawer.
4. **Contribution** of each metric = effective weight × percentile. The contributions sum to the score.
5. **"Potentially undervalued" heuristic:** only when ≥60% of the role pool has valuations. Within valued
   role players who meet the minutes filter, the score percentile and the value percentile are compared;
   a gap of ≥30 points with a score at or above the 60th percentile is flagged. The UI and the drawer say
   that this is a dataset-relative heuristic, not proof of a market inefficiency.

**Profiles** (starting weights): ball-progressing midfielder, defensive midfielder, creative winger and
goal-scoring striker (see `backend/app/catalog.py`).

**Metric definitions** (StatsBomb 120×80 pitch): progressive pass or carry = completed open-play
pass, or a carry, starting outside the defending 40% (x ≥ 48) that moves the ball ≥25% closer to goal
and ≥5 yards forward, or enters the box. Tackles = tackle duels won. Interceptions = successful
interceptions. xA = xG of non-penalty shots assisted. Goals and xG exclude penalties. Every metric is a
per-90 rate except pass completion %.

---

## Two-minute demo script

Meta mode and demo mode weight the first example slightly differently, so the shortlist order can
differ: Lanzini is #1 in demo mode and #3 in Meta mode, behind Coquelin and Romeu. Every step below works
in both modes.

| Time | Action | What to say |
|---|---|---|
| 0:00 | Open `http://localhost:3000`. Point at the **Demo mode / Meta model** badge and the dataset line. | "ScoutIQ finds affordable players for a brief. This is real Premier League 2015/16 event data, a historical season." |
| 0:15 | Click the first example: *"Find three midfielders under age 25 … below €15 million."* | "The request becomes a validated query: role, age ≤ 24, budget €15M, and weights that favour progression and defending." |
| 0:35 | Point at the chips (filters, profile, exclusion counts) and the three cards (fit score, percentile bars with weights). | "Ranking is plain Python: weighted, dataset-relative percentiles. No AI in the maths." |
| 0:50 | Click **Why this player?** on Manuel Lanzini. Scroll through the score build-up table, strengths/trade-offs, value context and source. | "Every point of the score is traceable. Here's the trade-off: tackles at the 21st percentile. And here's what we *can't* claim." |
| 1:15 | **Add to comparison**, close, click **+ Compare** on one more card (Jonjo Shelvey in demo mode; Oriol Romeu in Meta mode, flagged *potentially undervalued*). | "A €5M player whose output ranks well above his price within this dataset, and the heuristic explains exactly why." |
| 1:25 | Click the refine chip **Increase the budget to €25 million**. | "Follow-ups edit the query. The budget change brings in N'Golo Kanté." |
| 1:35 | **+ Compare** Kanté → **Compare 3**. | "Side by side: Kanté sits at the 99th percentile for interceptions and recoveries, Lanzini leads on progressive carries." |
| 1:50 | Close, click **Prioritize defensive contribution**, and note the *Changed* line and the history breadcrumb. | "The brief stays transparent through every refinement." |

---

## Completed features

- Natural-language search → strict `StructuredQuery`. The Meta Model API path uses `json_schema` output,
  and a deterministic parser handles demo mode and fallback.
- Follow-up refinement (prioritise or deprioritise metric groups; change budget absolutely or by a
  relative amount; change age, minutes, number of results or role), with a visible change list and a
  clickable history.
- Deterministic filtering and ranking, role-specific profiles, weight normalisation, missing-metric
  renormalisation with coverage disclosure, per-metric contributions, strengths and trade-offs, a
  small-sample warning, and the value heuristic gated on coverage.
- Budget filtering is disabled automatically (with an explanation) when no valuation data exists.
- UI: search page with three working examples; results page with editable filters, weight sliders,
  profile presets, ranked cards and summaries; "Why this player?" drawer; comparison view for up to
  three players; loading skeletons; empty state with one-click relaxations; error banners; visible
  provenance everywhere. Responsive from 375 px up.
- Reproducible ingestion script and committed SQLite DB. `.env.example`. Unit, API and smoke tests.

## Checks run

- `pytest`: **70 passed**. Covers filter correctness and boundaries, the hand-calculated score, weight
  normalisation, missing-data renormalisation, schema validation (13 invalid cases), the demo parser,
  follow-up updates, and model failures (HTTP 401/500, timeout, connection error, malformed or non-object
  JSON, extra fields, unknown metrics), the API fallback paths, input limits and rate limiting.
- `scripts/smoke_test.py` through the Next.js proxy: **17/17 PASS** (search → shortlist → evidence →
  compare → refine).
- Manual browser run in the in-app browser at desktop and 375×812 mobile: search, results, drawer, compare,
  refine, empty state, and the API-down error state. No horizontal overflow at mobile width.
- `tsc --noEmit`, `eslint` and `next build` are clean.
- A live call to `https://api.meta.ai/v1/chat/completions` without a key returned 401, which confirms the
  endpoint. With an invalid key, the app falls back to demo parsing and template summaries and shows warnings.

## Limitations

- **One historical season (2015/16).** Ages are as of 2016-01-01, and values are the latest Transfermarkt
  estimate between 2015-07-01 and 2016-06-30, so they can reflect end-of-season breakouts. Nothing here
  describes current form, contracts or availability.
- **Valuations are community estimates**, not fees. 284 of 319 players were matched to Transfermarkt by
  club and fuzzy name. A few (for example, Fernandinho) are unmatched and appear with "age unknown" or
  "value n/a".
- **Progressive actions use ScoutIQ's own documented rule**, so values won't match FBref or Opta numbers.
  Position groups come from where each player's events were logged (≥50% of events in the role).
- **Small samples:** single-season per-90 rates are noisy, so players under 1,500 minutes are flagged.
- **Statistics are not tactical fit.** The app says so throughout. It covers no defenders or goalkeepers
  yet, and no league- or team-strength adjustment.
- **Meta model generation not exercised with a real key** during the build (none available). The request
  format follows the official docs and is covered by mocked tests.
- **Attribution:** StatsBomb asks publishers to credit them and use their logo from the
  [media pack](https://statsbomb.com/media-pack/). The UI credits them in text; add the logo before any
  public release.
- The rate limiter and caches are in-memory (one process). That suits local demos but not multi-instance
  deployment.

## Data sources and licences

- **StatsBomb Open Data:** <https://github.com/statsbomb/open-data>. Free for research and analysis, with
  attribution to StatsBomb.
- **transfermarkt-datasets** by David Cariboo: <https://github.com/dcaribou/transfermarkt-datasets>,
  CC0-1.0. The underlying values are Transfermarkt community estimates.
