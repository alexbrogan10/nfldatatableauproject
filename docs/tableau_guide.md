# Tableau Build Guide

## 1. Connect the data

Open Tableau Desktop (or Tableau Public) → **Connect → Text File** → select
each CSV in `data/processed/`. Add all four as separate connections in one
data source (Tableau will let you relate/join them — see below) or keep them
as separate data sources per dashboard, whichever you prefer.

| File | Grain | Rows |
|---|---|---|
| `games.csv` | one row per game | ~1,700 |
| `team_standings.csv` | one row per team per season | 192 |
| `weekly_team_results.csv` | one row per team per game, 2025 only | 570 |
| `player_stats.csv` | one row per player, 2025 season totals | ~2,175 |

## 2. Join / relate keys

- `team_standings.team` ↔ `weekly_team_results.team` ↔ `player_stats.team` — all use the
  same 2–3 letter team abbreviation (e.g. `PHI`, `KC`). Use Tableau's **Relationships**
  (not a hard join) if combining standings with player stats, since they're at
  different grains (team-season vs. player-season).
- `games.game_id` = `weekly_team_results.game_id` if you want to bring in venue/weather
  fields from `games.csv` into the per-team view.
- `player_stats` has no direct key into `games`/`standings` other than `team` + `season` —
  it's season totals, not game-by-game, so don't try to join it at the game grain.

Simplest approach: build most sheets from a single CSV, and only relate
across files where you specifically need cross-cutting fields (e.g. "top
fantasy scorer per division" would relate `player_stats` to `team_standings`
on `team`).

## 3. Key fields per file

**`games.csv`** — `season`, `week`, `game_type` (REG/WC/DIV/CONF/SB), `away_team`,
`home_team`, `away_score`, `home_score`, `result` (home margin), `completed`
(boolean — filter to `True` for played games, `False` to show the upcoming
schedule), `roof`/`surface`/`stadium` for venue analysis.

**`team_standings.csv`** — `season`, `conf`, `division`, `team`, `wins`/`losses`/`ties`,
`pct`, `div_rank`, `scored`/`allowed`/`net` (points), `sos`/`sov` (strength of
schedule/victory), `seed` (playoff seed, blank if missed playoffs), `playoff`
(how far they went, e.g. `LostDV`, `WonSB`).

**`weekly_team_results.csv`** — `week`, `team`, `opponent`, `team_score`/`opp_score`,
`win`/`loss`/`tie` (booleans), `point_diff`, `cum_wins`/`cum_losses`/`cum_point_diff`
(running totals through the season — use these directly for a win-progression
line chart, no table calc needed).

**`player_stats.csv`** — `name`, `team`, `position`, then stat columns prefixed by
category: `passing_*`, `rushing_*`, `receiving_*`, `defensive_*`,
`defensiveinterceptions_*`, `scoring_*`, `returning_*`, `kicking_*`, `punting_*`.
Fantasy totals: `fantasy_points_standard`, `fantasy_points_half_ppr`,
`fantasy_points_ppr`.

Fantasy scoring formula used (standard categories, no distance-based FG
bonus): passing yards ÷ 25 + passing TD × 4 − INT × 2, rushing yards ÷ 10 +
rushing TD × 6, receiving yards ÷ 10 + receiving TD × 6 (+ receptions × 1 for
PPR / × 0.5 for half-PPR), fumbles lost × −2, return TD × 6, FG made × 3, XP
made × 1.

Note: `team` and `position` are blank for ~300 players who logged games in
2025 but are no longer on an active 32-team roster (cut, retired, practice
squad only) — ESPN's roster endpoint only reflects current rosters.

## 4. Suggested dashboards

**Team Performance** (source: `team_standings.csv` + `weekly_team_results.csv`)
- Division standings table: `division` → `team`, sorted by `wins`, colored by `pct`
- Win/loss trend: line chart of `cum_wins` by `week`, one line per `team`, filter to a division/conference
- Points for vs. points against: scatter plot, `scored` (x) vs `allowed` (y), sized by `wins`, one dot per team
- Season-over-season trend: `wins` by `season`, one line per team (needs `team_standings.csv` across all years)

**Game Results** (source: `games.csv`)
- Schedule/results table filtered to `completed = False` for "what's coming up"
- Score margin distribution: histogram of `result`
- Home vs. away win rate: bar chart split by `location`
- Games by `roof`/`surface` type

**Player Stats** (source: `player_stats.csv`)
- Passing leaderboard: bar chart of `passing_passingYards`, filtered `position = QB`
- Rushing/receiving leaders: same pattern with `rushing_rushingYards` / `receiving_receivingYards`
- Efficiency scatter: `passing_passingAttempts` (x) vs `passing_QBRating` (y), sized by `passing_passingTouchdowns`
- Defensive leaders: `defensive_totalTackles` + `defensive_sacks` combo chart

**Fantasy Football** (source: `player_stats.csv`)
- Top overall: bar chart of `fantasy_points_ppr`, top 25, colored by `position`
- Positional rankings: same chart filtered per `position` with a parameter to switch position
- Standard vs. PPR comparison: dual-axis or scatter of `fantasy_points_standard` vs `fantasy_points_ppr` to spot volume-catch players
- Value finder: `fantasy_points_ppr` per game (`fantasy_points_ppr / general_gamesPlayed`) vs total, to separate high-floor from boom/bust players

## 5. Filters/parameters worth adding

- `season` filter (works on `games.csv`/`team_standings.csv`, since they span 2021–2026)
- `position` parameter for the player stats dashboards
- `game_type` filter (REG/WC/DIV/CONF/SB) to separate regular season from playoffs
- A PPR-format parameter (Standard / Half / Full) driving a calculated field that picks the right `fantasy_points_*` column
