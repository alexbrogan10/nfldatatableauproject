# NFL Data → Tableau Project

Ready-to-import NFL datasets covering team standings, game results, and
player/fantasy stats, built for a Tableau dashboard. Data is pulled from
free, public sources — no API keys required.

The 2025 season is the most recently *completed* NFL season (the 2026
season schedule exists but hasn't been played yet), so player stats and
"current" standings are pinned to 2025. Game and standings history goes
back to 2021 for trend analysis, and includes the 2026 schedule for
upcoming games.

## What's here

```
data/processed/
  games.csv                          All games 2021–2026, one row per game (scores, teams, week, venue)
  team_standings.csv                 Season standings 2021–2025 (division rank, record, points, playoff result)
  weekly_team_results.csv            2025 season unpivoted to one row per team per game (for trend lines)
  player_stats.csv                   2025 season player stats: passing/rushing/receiving/defense/kicking + fantasy points
  player_stats_data_dictionary.csv   What every player_stats.csv column means
  teams.csv                          Team abbreviation -> full name/conference/division lookup

scripts/
  fetch_games.py               Pulls games.csv + standings.csv from nflverse/nfldata, writes games/standings/weekly/teams
  fetch_player_stats.py        Pulls ESPN's player stat leaderboard + team rosters, computes fantasy points
  build_tableau_workbook.py    Generates NFL_Dashboard_Starter.twb from the processed CSVs

docs/
  tableau_guide.md          Data model, join keys, calculated-field recipes, and a suggested dashboard build-out

NFL_Dashboard_Starter.twb   Tableau workbook with all 5 CSVs pre-connected (no worksheets built yet)
```

The processed CSVs are committed to the repo, so you can open them directly
in Tableau without running anything. Re-run the scripts later to refresh
with new data (e.g. once the 2026 season starts) — if you do, also re-run
`build_tableau_workbook.py` to regenerate the starter workbook.

## Data sources

- **Games & standings**: [nflverse/nfldata](https://github.com/nflverse/nfldata) — a community-maintained,
  freely licensed NFL dataset (schedules back to 1999, standings back to 2002).
- **Player stats**: ESPN's public stats API (`site.web.api.espn.com`), the same
  data that powers espn.com/nfl/stats. Unauthenticated, no key needed.
- **Fantasy points**: computed locally using standard scoring rules (see
  `docs/tableau_guide.md` for the exact formula) — ESPN doesn't provide this directly.

## Regenerating the data

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_games.py
python scripts/fetch_player_stats.py
python scripts/build_tableau_workbook.py
```

To pull a different season, edit `SEASON`/`CURRENT_SEASON` at the top of
each script.

## Building the Tableau dashboard

Open `NFL_Dashboard_Starter.twb` in Tableau Desktop/Public to start from the
five CSVs already connected with correct column types, or connect them
manually — either way, see `docs/tableau_guide.md` for the data model (join
keys between the CSVs), ready-to-paste calculated fields, and a suggested
set of sheets/dashboards to build for team performance, player stats, game
results, and fantasy football.
