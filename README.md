# ScoutIQ

An AI scouting assistant that helps clubs with small budgets find players who fit a tactical brief.

Type a request like *"Find three midfielders under 25 who progress the ball well, contribute defensively,
and are valued below €15 million."* ScoutIQ turns it into structured filters, ranks players with plain
Python statistics, and shows the evidence behind every pick. You can then compare up to three players and
refine the search with follow-ups such as *"Increase the budget to €25 million."*

A Meta model interprets requests and writes short summaries. **It never does the ranking.** Without an
API key, ScoutIQ runs in a labelled demo mode that uses a rule-based parser instead.

**Data:** real players from the **Premier League 2015/16** season ([StatsBomb Open Data](https://github.com/statsbomb/open-data),
all 380 matches), with market-value estimates from [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) (CC0).
It's a historical season, so treat ScoutIQ as a demonstration, not a live transfer tool.

## Run it

Requires Python 3.11+ and Node 20+.

```bash
git clone https://github.com/palashpawar/scoutiq.git && cd scoutiq

# Backend (terminal 1)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000

# Frontend (terminal 2)
cd frontend
npm install && npm run dev
```

Open http://localhost:3000. The database is included, so no data download is needed.

## Connect a Meta model (optional)

Copy `.env.example` to `.env`, fill in one of the options below, and restart the backend.

**Modal Endpoints** (Meta open-weights models such as Muse Spark Open):
```
META_API_BASE_URL=<your-endpoint-url>/v1
META_API_KEY=wk-<token-id>.ws-<token-secret>
META_MODEL=meta-models/Muse-Spark-Open-816B-A42B
META_REASONING_EFFORT=low
```
Create the endpoint at [modal.com/endpoints](https://modal.com/endpoints) and the token with
`modal workspace proxy-tokens create`.

**Meta Model API** ([dev.meta.ai](https://dev.meta.ai)):
```
META_API_BASE_URL=https://api.meta.ai/v1
META_API_KEY=LLM_...
META_MODEL=muse-spark-1.3
```

Keys stay on the backend; the browser never sees them. Other settings, including timeouts, rate limits
and forcing demo mode, are documented in `.env.example`.

## How it works

1. **Interpret:** the model (or the demo parser) converts the request into a strict JSON query: role,
   maximum age, minimum minutes, budget, metric weights and number of results. Anything invalid falls
   back to the demo parser with a visible warning. Model output is never executed or used as SQL.
2. **Rank:** Python filters players, converts each statistic into a percentile among same-role players
   with 900+ minutes, and computes a weighted score. If a metric is missing, its weight is redistributed
   and the card says so.
3. **Explain:** each player's "Why this player?" panel shows the filters, weights, each metric's
   contribution to the score, strengths, trade-offs, missing data and sources. Summaries are written
   only from these numbers. Any summary that mentions injuries, personality or transfer availability is
   replaced with a template.

A player is flagged **potentially undervalued** when their score ranks at least 30 percentile points
above their market value within this dataset. It's a simple heuristic, not proof of a bargain.

Supported roles are central midfielder, winger and striker, with four starting profiles:
ball-progressing midfielder, defensive midfielder, creative winger and goal-scoring striker.

**Code:** `frontend/` is Next.js, TypeScript and Tailwind. `backend/app/` is FastAPI: `scoring.py` ranks,
`llm.py` calls the model, `parser.py` is the demo parser, and `schemas.py` validates queries.

## Two-minute demo

1. Click the first example search (midfielders under 25, below €15M).
2. Open **Why this player?** on Manuel Lanzini and walk through how his score is built.
3. Add Lanzini and one other player to the comparison.
4. Click **Increase the budget to €25 million**. N'Golo Kanté joins the shortlist; add him too.
5. Open **Compare 3**, then try **Prioritize defensive contribution**.

The shortlist order can differ slightly between demo mode and Meta mode.

## Tests

```bash
cd backend
.venv/bin/python -m pytest -q                                # unit and API tests
.venv/bin/python scripts/smoke_test.py --base http://localhost:3000   # end-to-end, servers running
```

To rebuild the database from the original sources (~110 MB download), run `.venv/bin/python scripts/ingest.py`.

## Limitations

- One historical season. Ages are as of January 2016, and values are Transfermarkt community estimates,
  not transfer fees.
- 35 of 319 players couldn't be matched to Transfermarkt, so they show "age unknown" or "value n/a".
- Progressive passes and carries use ScoutIQ's own definition, so they won't match FBref or Opta figures.
- Single-season statistics are noisy and can't establish tactical fit. Defenders and goalkeepers aren't
  supported yet.

## Credits

Event data provided by [StatsBomb](https://github.com/statsbomb/open-data). Market values from
[transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) (CC0).
