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
  games.csv                 All games 2021–2026, one row per game (scores, teams, week, venue)
  team_standings.csv        Season standings 2021–2025 (division rank, record, points, playoff result)
  weekly_team_results.csv   2025 season unpivoted to one row per team per game (for trend lines)
  player_stats.csv          2025 season player stats: passing/rushing/receiving/defense/kicking + fantasy points

scripts/
  fetch_games.py            Pulls games.csv + standings.csv from nflverse/nfldata, writes the processed files above
  fetch_player_stats.py     Pulls ESPN's player stat leaderboard + team rosters, computes fantasy points

docs/
  tableau_guide.md          Data model, join keys, and a suggested dashboard build-out for Tableau
```

The processed CSVs are committed to the repo, so you can open them directly
in Tableau without running anything. Re-run the scripts later to refresh
with new data (e.g. once the 2026 season starts).

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
```

To pull a different season, edit `SEASON`/`CURRENT_SEASON` at the top of
each script.

## Building the Tableau dashboard

See `docs/tableau_guide.md` for the data model (join keys between the four
CSVs), field notes, and a suggested set of sheets/dashboards to build for
team performance, player stats, game results, and fantasy football.
